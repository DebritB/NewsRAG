"""Amazon Bedrock embedding generation using Titan v2 and Claude for classification"""
import boto3
import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

class BedrockEmbeddings:
    """Generate embeddings using Amazon Bedrock Titan Embed Text v2"""
    
    def __init__(self, region_name: str = 'us-east-1'):
        """
        Initialize Bedrock client
        
        Args:
            region_name: AWS region for Bedrock (default: us-east-1)
        """
        self.client = boto3.client('bedrock-runtime', region_name=region_name)
        self.model_id = 'amazon.titan-embed-text-v2:0'
        self.claude_model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
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
        Use Bedrock Claude to classify article into one of 4 categories
        
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
        
        prompt = f"""Classify this news article into ONE of these categories: sports, lifestyle, music, or finance.

Title: {title}
Content: {content_preview}

If the article clearly fits one of these categories, respond with ONLY the category name in lowercase (sports, lifestyle, music, or finance).
If the article does NOT fit any of these categories, respond with ONLY the word: none

Examples:
- Sports article → sports
- Health/travel/fashion article → lifestyle
- Concert/album article → music
- Stock/economy article → finance
- Politics/crime/weather article → none

Category:"""

        for attempt in range(max_retries):
            try:
                response = self.client.invoke_model(
                    modelId=self.claude_model_id,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 10,
                        "temperature": 0,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    })
                )
                
                response_body = json.loads(response['body'].read())
                category = response_body['content'][0]['text'].strip().lower()
                
                # Validate category
                valid_categories = ['sports', 'lifestyle', 'music', 'finance']
                if category in valid_categories:
                    logger.debug(f"Claude classified as: {category}")
                    return category
                elif category == 'none':
                    logger.debug("Claude: no matching category")
                    return None
                else:
                    logger.warning(f"Unexpected Claude response: {category}, treating as no match")
                    return None
                    
            except Exception as e:
                if 'ThrottlingException' in str(e) and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Claude throttled, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    logger.error(f"Error in Claude classification: {str(e)}")
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
