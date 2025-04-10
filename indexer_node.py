# indexer_node.py
import json
import logging
import os
from collections import defaultdict
from config import Config
from tasks import app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IndexerNode:
    def __init__(self):
        self.index = defaultdict(list)
        self.load_index()
        
    def load_index(self):
        """Load existing index from file"""
        try:
            if os.path.exists(Config.INDEX_FILE) and os.path.getsize(Config.INDEX_FILE) > 0:
                with open(Config.INDEX_FILE, 'r') as f:
                    self.index = defaultdict(list, json.load(f))
            else:
                logger.info("No existing index found or empty file, starting fresh")
                # Create empty index file
                self.save_index()
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            # Create empty index file
            self.save_index()
            
    def save_index(self):
        """Save index to file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(Config.INDEX_FILE), exist_ok=True)
            with open(Config.INDEX_FILE, 'w') as f:
                json.dump(dict(self.index), f, indent=2)
            logger.info("Index saved successfully")
        except Exception as e:
            logger.error(f"Error saving index: {e}")
            
    def add_to_index(self, url, text):
        """Add or update URL content in the index"""
        try:
            # Simple word tokenization
            words = set(word.lower() for word in text.split())
            
            for word in words:
                if url not in self.index[word]:
                    self.index[word].append(url)
                    
            self.save_index()
            logger.info(f"Indexed content from: {url}")
            return True
        except Exception as e:
            logger.error(f"Error indexing content from {url}: {e}")
            return False
        
    def search(self, query):
        """Search the index for URLs containing all query terms"""
        query_terms = query.lower().split()
        if not query_terms:
            return []
            
        # Get URLs containing first term
        results = set(self.index.get(query_terms[0], []))
        
        # Intersect with URLs containing other terms
        for term in query_terms[1:]:
            results.intersection_update(self.index.get(term, []))
            
        return list(results)

    def print_index_stats(self):
        """Print statistics about the index"""
        print("\nIndex Statistics:")
        print(f"Total unique words: {len(self.index)}")
        print(f"Total URLs indexed: {len(set(url for urls in self.index.values() for url in urls))}")
        print("\nSample of indexed content:")
        # Print first 5 words and their URLs
        for word in list(self.index.keys())[:5]:
            print(f"Word '{word}' found in: {self.index[word]}")