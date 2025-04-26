import json
import logging
import os
import re
from collections import defaultdict, Counter
from config import Config
import datetime
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IndexerNode:
    def __init__(self):
        # Initialize components for text normalization
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words("english"))
        self.load_index()
        self.os_client = OpenSearch(
            hosts=[{'host': os.environ['OPENSEARCH_HOST'], 'port': 443}],
            http_auth=AWS4Auth(
                os.environ['AWS_ACCESS_KEY_ID'],
                os.environ['AWS_SECRET_ACCESS_KEY'],
                os.environ['AWS_REGION'],
                'es',
            ),
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )
            
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
        tokens = self.tokenize_and_normalize(text)
        document = {
            'url': url,
            'content': text,
            'tokens': tokens,
            'timestamp': datetime.utcnow()
        }
        self.os_client.index(
            index='web-crawl',
            body=document,
            id=url
        )
        
    def search(self, query):
        tokens = self.tokenize_and_normalize(query)
        response = self.os_client.search({
            "query": {
                "match": {
                    "tokens": " ".join(tokens)
                }
            }
        })
        return [hit['_source']['url'] for hit in response['hits']['hits']]

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