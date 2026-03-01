"""
Deduplication Engine - Headline similarity detection and duplicate marking
"""
import re
from typing import List, Tuple
from difflib import SequenceMatcher

from app.config import settings


class Deduplicator:
    """Article deduplication using content hashing and headline similarity"""
    
    def __init__(self):
        self.threshold = settings.DUPLICATE_THRESHOLD
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Convert to lowercase
        text = text.lower()
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
            'dare', 'ought', 'used', 'won', 'news', 'breaking', 'update', 'report'
        }
        words = [w for w in text.split() if w not in stop_words]
        return ' '.join(words)
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ratio between two texts (0.0 to 1.0)"""
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Use SequenceMatcher for similarity
        matcher = SequenceMatcher(None, norm1, norm2)
        return matcher.ratio()
    
    def word_overlap_score(self, text1: str, text2: str) -> float:
        """Calculate word overlap percentage"""
        words1 = set(self.normalize_text(text1).split())
        words2 = set(self.normalize_text(text2).split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def is_duplicate(self, headline1: str, headline2: str) -> Tuple[bool, float]:
        """Check if two headlines are duplicates based on similarity threshold"""
        # Quick check: exact match after normalization
        norm1 = self.normalize_text(headline1)
        norm2 = self.normalize_text(headline2)
        
        if norm1 == norm2:
            return True, 1.0
        
        # Calculate word overlap
        overlap = self.word_overlap_score(headline1, headline2)
        
        # If word overlap is high enough, consider it a duplicate
        if overlap >= self.threshold:
            return True, overlap
        
        # Also check sequence similarity as fallback
        seq_similarity = self.calculate_similarity(headline1, headline2)
        if seq_similarity >= self.threshold:
            return True, seq_similarity
        
        return False, max(overlap, seq_similarity)
    
    def find_duplicates(self, headlines: List[str]) -> List[Tuple[int, int, float]]:
        """Find all duplicate pairs in a list of headlines"""
        duplicates = []
        n = len(headlines)
        
        for i in range(n):
            for j in range(i + 1, n):
                is_dup, score = self.is_duplicate(headlines[i], headlines[j])
                if is_dup:
                    duplicates.append((i, j, score))
        
        return duplicates
    
    def select_canonical(self, articles: List[dict]) -> dict:
        """Select the canonical article from a group of duplicates"""
        if not articles:
            return None
        
        # Prefer articles from more reputable sources
        # Priority: Reuters > Major outlets > Others
        priority_sources = ['reuters', 'ap', 'afp', 'bbc']
        
        for priority in priority_sources:
            for article in articles:
                if priority in article.get('source_name', '').lower():
                    return article
        
        # Otherwise, return the earliest published
        return min(articles, key=lambda x: x.get('published_at') or '')


# Global deduplicator instance
deduplicator = Deduplicator()


def check_headline_similarity(headline1: str, headline2: str) -> Tuple[bool, float]:
    """Convenience function to check headline similarity"""
    return deduplicator.is_duplicate(headline1, headline2)
