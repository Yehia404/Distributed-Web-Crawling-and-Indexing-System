import json
import logging
import os
import re
from collections import defaultdict, Counter
from config import Config

import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IndexerNode:
    def __init__(self):
        # Inverted index where each word maps to a dict: {url: frequency}
        self.index = defaultdict(dict)
        # Initialize components for text normalization
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words("english"))
        self.load_index()


    def load_index(self):
        """Load the existing index from file."""
        try:
            if os.path.exists(Config.INDEX_FILE) and os.path.getsize(Config.INDEX_FILE) > 0:
                with open(Config.INDEX_FILE, 'r') as f:
                    loaded_index = json.load(f)
                    # Convert loaded dictionary into a defaultdict if needed
                    self.index = defaultdict(dict, loaded_index)
                    logger.info("Loaded index from file.")
            else:
                logger.info("No existing index found or file is empty. Starting fresh.")
                self.save_index()
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            self.save_index()
            
    def save_index(self):
        """Save the index to file."""
        try:
            os.makedirs(os.path.dirname(Config.INDEX_FILE), exist_ok=True)
            with open(Config.INDEX_FILE, 'w') as f:
                # Convert defaultdict to a normal dict for JSON storage.
                json.dump(dict(self.index), f, indent=2)
            logger.info("Index saved successfully.")
        except Exception as e:
            logger.error(f"Error saving index: {e}")
            
    def tokenize_and_normalize(self, text):
        """
        Tokenize text using regular expressions,
        remove punctuation, convert to lower case,
        remove stop-words, and apply stemming.
        Returns the list of normalized tokens.
        """
        # Use regex to extract words (alphanumeric and underscore)
        tokens = re.findall(r'\w+', text.lower())
        normalized_tokens = []
        for token in tokens:
            if token not in self.stop_words:
                stemmed = self.stemmer.stem(token)
                normalized_tokens.append(stemmed)
        return normalized_tokens
        
    def add_to_index(self, url, text):
        """
        Add or update the index with content from the given URL.
        Tracks term frequencies so that ranking can be applied.
        """
        try:
            tokens = self.tokenize_and_normalize(text)
            # Compute token frequency in this document
            token_freqs = Counter(tokens)
            # For each token, update the inverted index with the frequency for this URL.
            for token, freq in token_freqs.items():
                self.index[token][url] = freq
            self.save_index()
            logger.info(f"Indexed content from: {url}")
            return True
        except Exception as e:
            logger.error(f"Error indexing content from {url}: {e}")
            return False
        
    def search(self, query):
        """
        Search for URLs matching the query.
        Uses the same normalization for the query and scores documents
        based on the sum of frequencies for each appearing token.
        Supports only AND queries (words must appear in the document).
        Does not support phrase queries or advanced ranking.
        """
        query_tokens = self.tokenize_and_normalize(query)
        if not query_tokens:
            return []
        
        # Gather the posting lists for each token
        results_per_token = []
        for token in query_tokens:
            if token in self.index:
                results_per_token.append(self.index[token])
            else:
                # If any token is not found, no document satisfies an AND query.
                return []
                
        # Intersect the URLs that appear for all tokens.
        # Start with the set of URLs for the first query token.
        common_urls = set(results_per_token[0].keys())
        for postings in results_per_token[1:]:
            common_urls.intersection_update(postings.keys())
            
        # Now compute a simple relevance score: sum of term frequencies
        doc_scores = {}
        for url in common_urls:
            score = 0
            for token in query_tokens:
                score += self.index[token].get(url, 0)
            doc_scores[url] = score
            
        # Sort results by score (higher score means more relevance)
        sorted_results = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        ranked_urls = [url for url, score in sorted_results]
        logger.info(f"Search for '{query}' returned: {ranked_urls}")
        return ranked_urls

    def print_index_stats(self):
        """Print statistics about the index."""
        print("\nIndex Statistics:")
        print(f"Total unique words in index: {len(self.index)}")
        all_urls = set()
        for postings in self.index.values():
            all_urls.update(postings.keys())
        print(f"Total URLs indexed: {len(all_urls)}")
        print("\nSample of indexed content:")
        for token in list(self.index.keys())[:5]:
            print(f"Token '{token}' found in: {self.index[token]}")