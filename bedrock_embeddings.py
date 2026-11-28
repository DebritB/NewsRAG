"""Amazon Bedrock embedding generation using Titan v2, and an LLM (Converse API) for classification"""
import boto3
import json
import logging
import os
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

class BedrockEmbeddings:
    """Generate embeddings using Amazon Bedrock Titan Embed Text v2"""
    
    def __init__(self, region_name: Optional[str] = None):
        """
        Initialize Bedrock client

        Args:
            region_name: AWS region for Bedrock (default: the Lambda's own region, AWS_REGION)
        """
        region_name = region_name or os.environ.get('AWS_REGION', 'ap-southeast-2')
        self.client = boto3.client('bedrock-runtime', region_name=region_name)
        self.model_id = 'amazon.titan-embed-text-v2:0'
        # Chat model for classification (any Bedrock model that supports the Converse API)
        self.llm_model_id = os.environ.get('LLM_MODEL_ID', 'zai.glm-5')
        self.dimensions = 1024  # Titan v2 produces 1024-dimensional vectors
        
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text with retry logic
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector (1024 dimensions)
        """
        import time
        max_retries = 5
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Truncate text if too long (Titan v2 max: 8192 tokens ≈ 30k chars)
                if len(text) > 30000:
                    text = text[:30000]
                
                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps({
                        "inputText": text
                    })
                )
                
                response_body = json.loads(response['body'].read())
                embedding = response_body['embedding']
                
                logger.debug(f"Generated embedding with {len(embedding)} dimensions")
                return embedding
                
            except Exception as e:
                if 'ThrottlingException' in str(e) and attempt < max_retries - 1:
                    # Exponential backoff
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Throttled, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    logger.error(f"Error generating embedding: {str(e)}")
                    raise
    
    def classify_category(self, title: str, content: str) -> Optional[str]:
        """
        Use the Bedrock LLM (Converse API) to classify article into one of 4 categories

        Args:
            title: Article title
            content: Article content (first 1000 chars)
            
        Returns:
            Category string (sports/lifestyle/music/finance) or None if no match
        """
        import time
        max_retries = 4
        base_delay = 3
        
        # Truncate content for efficiency
        content_preview = content[:1000] if content else ""
        
        system_prompt = (
            "You are a news classifier. Reply with ONLY one lowercase word from this list: "
            "sports, finance, music, lifestyle, none. No explanation, no punctuation.\n"
            "Guide: sports article -> sports; health/travel/fashion -> lifestyle; "
            "concert/album -> music; stocks/economy -> finance; politics/crime/weather/anything else -> none."
        )
        user_prompt = f"Title: {title}\nContent: {content_preview}\nCategory:"

        for attempt in range(max_retries):
            try:
                response = self.client.converse(
                    modelId=self.llm_model_id,
                    system=[{"text": system_prompt}],
                    messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                    # Room for models that reason before answering; non-reasoning models use ~2 tokens
                    inferenceConfig={"maxTokens": 400},
                )

                # Reasoning models may return a reasoning block first: take the first text block
                blocks = response['output']['message']['content']
                raw = next((b['text'] for b in blocks if 'text' in b), '')
                # Normalise replies like "Sports." or "\n\nsports" to the first lowercase word
                words = re.findall(r'[a-z]+', raw.lower())
                category = words[0] if words else ''

                valid_categories = ['sports', 'lifestyle', 'music', 'finance']
                if category in valid_categories:
                    logger.debug(f"LLM classified as: {category}")
                    return category
                elif category == 'none':
                    logger.debug("LLM: no matching category")
                    return None
                else:
                    logger.warning(f"Unexpected LLM response: {raw[:50]!r}, treating as no match")
                    return None

            except Exception as e:
                if 'ThrottlingException' in str(e) and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"LLM throttled, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    logger.error(f"Error in LLM classification: {str(e)}")
                    # On error, return None (don't store article)
                    return None
        
        return None
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        for i, text in enumerate(texts):
            try:
                embedding = self.generate_embedding(text)
                embeddings.append(embedding)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Generated {i + 1}/{len(texts)} embeddings")
                    
            except Exception as e:
                logger.error(f"Failed to generate embedding for text {i}: {str(e)}")
                # Return zero vector on failure
                embeddings.append([0.0] * self.dimensions)
                
        return embeddings
