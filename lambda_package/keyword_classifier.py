"""
Keyword-based article classification with TF-IDF scoring
Provides confidence scores for each classification
"""

from typing import Dict, Tuple, Optional
import re
from collections import Counter
import math


class KeywordClassifier:
    """
    Classifies articles using TF-IDF weighted keyword matching
    Returns category and confidence score
    """
    
    def __init__(self):
        # Category keywords with weights (importance)
        self.category_keywords = {
            'sports': {
                # High-weight terms (definitive indicators)
                'cricket': 3.0, 'afl': 3.0, 'nrl': 3.0, 'rugby': 3.0,
                'football': 2.5, 'soccer': 2.5, 'tennis': 2.5, 'basketball': 2.5,
                'netball': 2.5, 'swimming': 2.5, 'athletics': 2.5, 'formula one': 3.0,
                'f1': 3.0, 'olympics': 3.0, 'championship': 2.0, 'tournament': 2.0,
                # Medium-weight terms
                'match': 1.5, 'game': 1.5, 'team': 1.5, 'player': 1.5, 'coach': 1.5,
                'goal': 1.5, 'score': 1.5, 'win': 1.0, 'loss': 1.0, 'victory': 1.5,
                'defeat': 1.5, 'stadium': 2.0, 'league': 2.0, 'season': 1.5,
                # Specific sports terms
                'wicket': 2.5, 'innings': 2.5, 'bowler': 2.5, 'batsman': 2.5,
                'try': 1.0, 'penalty': 1.0, 'referee': 1.5, 'umpire': 2.0,
            },
            
            'music': {
                # High-weight terms
                'concert': 3.0, 'album': 3.0, 'tour': 2.5, 'festival': 2.5,
                'grammy': 3.0, 'aria': 3.0, 'spotify': 2.5, 'billboard': 2.5,
                # Medium-weight terms
                'singer': 2.0, 'band': 2.0, 'musician': 2.0, 'artist': 1.5,
                'song': 2.0, 'music': 1.5, 'recording': 2.0, 'performance': 1.5,
                'single': 2.0, 'release': 1.5, 'debut': 2.0, 'soundtrack': 2.5,
                # Genre terms
                'rock': 1.5, 'pop': 1.5, 'hip hop': 2.0, 'rap': 2.0,
                'jazz': 2.0, 'classical': 2.0, 'country': 1.5,
            },
            
            'finance': {
                # High-weight terms
                'asx': 3.0, 'stock market': 3.0, 'shares': 2.5, 'dividend': 3.0,
                'rba': 3.0, 'interest rate': 3.0, 'inflation': 2.5, 'gdp': 3.0,
                'reserve bank': 3.0, 'central bank': 3.0, 'federal reserve': 3.0,
                # Medium-weight terms
                'investment': 2.0, 'investor': 2.0, 'trading': 2.0, 'market': 1.5,
                'stock': 2.0, 'share': 2.0, 'equity': 2.5, 'bond': 2.5,
                'currency': 2.0, 'dollar': 1.5, 'economy': 1.5, 'economic': 1.5,
                'financial': 2.0, 'banking': 2.0, 'bank': 1.5, 'profit': 1.5,
                'revenue': 2.0, 'earnings': 2.0, 'quarter': 1.0, 'fiscal': 2.5,
                # Crypto terms
                'bitcoin': 2.5, 'cryptocurrency': 2.5, 'crypto': 2.0, 'blockchain': 2.5,
            },
            
            'lifestyle': {
                # High-weight terms
                'fashion': 3.0, 'beauty': 2.5, 'wellness': 2.5, 'fitness': 2.5,
                'recipe': 3.0, 'travel': 2.5, 'destination': 2.5, 'vacation': 2.5,
                'health': 2.0, 'diet': 2.5, 'nutrition': 2.5, 'exercise': 2.5,
                # Medium-weight terms
                'style': 1.5, 'designer': 2.0, 'makeup': 2.5, 'skincare': 2.5,
                'restaurant': 2.0, 'food': 1.5, 'dining': 2.0, 'chef': 2.0,
                'hotel': 2.0, 'resort': 2.5, 'holiday': 2.0, 'tourism': 2.0,
                'home': 1.0, 'decor': 2.5, 'interior': 2.0, 'garden': 2.0,
                'relationship': 2.0, 'parenting': 2.5, 'family': 1.0,
            }
        }
        
        # Calculate document frequency for IDF
        self._calculate_idf()
    
    def _calculate_idf(self):
        """Calculate Inverse Document Frequency for each term"""
        # Count how many categories each term appears in
        term_doc_freq = Counter()
        for category_terms in self.category_keywords.values():
            for term in category_terms.keys():
                term_doc_freq[term] += 1
        
        # Calculate IDF: log(total_docs / doc_freq)
        total_categories = len(self.category_keywords)
        self.idf_scores = {}
        for term, freq in term_doc_freq.items():
            self.idf_scores[term] = math.log(total_categories / freq)
    
    def _extract_text_features(self, text: str) -> Dict[str, int]:
        """Extract normalized text for keyword matching"""
        if not text:
            return {}
        
        # Normalize: lowercase, remove special chars
        text = text.lower()
        text = re.sub(r'[^\w\s-]', ' ', text)
        
        # Count term frequencies
        words = text.split()
        term_freq = Counter()
        
        # Single words
        for word in words:
            term_freq[word] += 1
        
        # Bigrams (two-word phrases)
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            term_freq[bigram] += 1
        
        return dict(term_freq)
    
    def _calculate_tfidf_score(self, term_freq: Dict[str, int], 
                                category_keywords: Dict[str, float]) -> float:
        """
        Calculate TF-IDF weighted score for a category
        
        Score = Σ(TF × IDF × keyword_weight) for each matching term
        """
        score = 0.0
        matches = 0
        
        for term, keyword_weight in category_keywords.items():
            if term in term_freq:
                tf = term_freq[term]
                idf = self.idf_scores.get(term, 1.0)
                score += tf * idf * keyword_weight
                matches += 1
        
        # Normalize by number of matches to avoid category size bias
        if matches > 0:
            score = score / math.sqrt(matches)
        
        return score
    
    def classify(self, title: str, content: str = "", 
                 summary: str = "") -> Tuple[Optional[str], float]:
        """
        Classify article using TF-IDF weighted keywords
        
        Args:
            title: Article title (weighted 3x)
            content: Article content
            summary: Article summary (weighted 2x)
            
        Returns:
            Tuple of (category, confidence_score)
            - category: 'sports', 'music', 'finance', 'lifestyle', or None
            - confidence: 0.0 to 1.0, where >0.3 is considered confident
        """
        # Combine text with weights
        combined_text = (
            f"{title} " * 3 +  # Title is most important
            f"{summary} " * 2 +  # Summary is moderately important
            f"{content[:1000]}"  # First 1000 chars of content
        )
        
        # Extract term frequencies
        term_freq = self._extract_text_features(combined_text)
        
        if not term_freq:
            return None, 0.0
        
        # Calculate TF-IDF score for each category
        category_scores = {}
        total_score = 0.0
        for category in self.category_keywords.keys():
            score = self._calculate_tfidf_score(term_freq, self.category_keywords[category])
            category_scores[category] = score
            total_score += score
        
        # Find best category
        if not category_scores or total_score == 0:
            return None, 0.0
        
        best_category = max(category_scores, key=category_scores.get)
        best_score = category_scores[best_category]
        
        # Calculate percentage of total score
        score_percentage = (best_score / total_score) if total_score > 0 else 0.0
        
        # Reject if category score is less than 5% of total
        if score_percentage < 0.05:
            return None, 0.0
        
        # Normalize confidence score (divide by 5.0 as typical max score)
        # Cap at 1.0
        confidence = min(best_score / 5.0, 1.0)
        
        if confidence < 0.05:  # Very low confidence
            return None, 0.0
        
        return best_category, confidence
    
    def classify_with_details(self, title: str, content: str = "", 
                             summary: str = "") -> Dict:
        """
        Classify with detailed scoring information
        Returns dictionary with category, confidence, and all scores
        """
        category, confidence = self.classify(title, content, summary)
        
        # Get all category scores for debugging
        combined_text = f"{title} " * 3 + f"{summary} " * 2 + f"{content[:1000]}"
        term_freq = self._extract_text_features(combined_text)
        
        all_scores = {}
        for cat, keywords in self.category_keywords.items():
            all_scores[cat] = self._calculate_tfidf_score(term_freq, keywords)
        
        return {
            'category': category,
            'confidence': confidence,
            'all_scores': all_scores,
            'needs_claude': confidence < 0.3
        }
