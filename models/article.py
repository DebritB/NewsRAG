from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class Article:
    """Unified article data model"""
    title: str
    url: str
    source: str
    published_date: datetime
    content: str
    summary: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    keywords: List[str] = None
    image_url: Optional[str] = None
    source_list: Optional[List[str]] = None  # List of all sources covering this story
    occurrence_count: Optional[int] = None    # Number of sources covering this story
    embedding: Optional[List[float]] = None   # 1024-dim vector from Bedrock Titan v2
    confidence: float = 0.0  # Confidence score for categorization (0.0-1.0)
    highlight: bool = False  # Whether this is a top-5 highlight for its category
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.source_list is None:
            self.source_list = [self.source]
        if self.occurrence_count is None:
            self.occurrence_count = 1
    
    def to_dict(self):
        """Convert article to dictionary"""
        return {
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'published_date': self.published_date,
            'content': self.content,
            'summary': self.summary,
            'author': self.author,
            'category': self.category,
            'keywords': self.keywords,
            'image_url': self.image_url,
            'source_list': self.source_list,
            'occurrence_count': self.occurrence_count,
            'embedding': self.embedding,
            'confidence': self.confidence,
            'highlight': self.highlight
        }
