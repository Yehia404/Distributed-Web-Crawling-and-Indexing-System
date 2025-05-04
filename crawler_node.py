# crawler_node.py
import requests
from bs4 import BeautifulSoup
import logging
import hashlib
import time
from datetime import datetime
import os
from urllib.parse import urljoin, urlparse
import urllib.robotparser
from config import Config
from redis_clinet import r
import boto3

s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "eu-north-1"))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrawlerNode:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': Config.USER_AGENT})
        self.robots_cache = {}
        
    def check_robots_txt(self, url):
        """Check if URL is allowed by robots.txt"""
        parsed_url = urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        
        if robots_url not in self.robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
                self.robots_cache[robots_url] = rp
            except Exception as e:
                logger.error(f"Error reading robots.txt: {e}")
                return True
                
        return self.robots_cache[robots_url].can_fetch(Config.USER_AGENT, url)

    def crawl(self, url, depth=0):
        """Crawl a single URL and return content, new URLs and the current crawl depth."""
        logger.info(f"Starting to crawl: {url} at depth {depth}")
        if not self.check_robots_txt(url):
            logger.info(f"URL not allowed by robots.txt: {url}")
            return {
                'url': url,
                'status': 'disallowed',
                'error': 'Disallowed by robots.txt',
                'new_urls': [],
                'content_length': 0,
                'depth': depth
            }
            
        time.sleep(Config.CRAWL_DELAY)
        
        try:
            logger.info(f"Fetching {url}")
            response = self.session.get(url, timeout=5)
            response.raise_for_status()
            parsed = urlparse(url)
            netloc = parsed.netloc
            soup = BeautifulSoup(response.text, 'html.parser')
            s3.put_object(
            Bucket=os.environ['S3_BUCKET'],
            Key=f"crawled/{netloc}/{hashlib.sha1(url.encode()).hexdigest()}.html",
            Body=response.text,
            Metadata={
                'source-url': url,
                'crawl-time': datetime.utcnow().isoformat()
            }
        )
            # Extract text content
            texts = []
            for tag in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6','span']:
                texts.extend([elem.get_text().strip() for elem in soup.find_all(tag)])
            text = ' '.join(texts)
            
            # Extract links
            links = []
            for a in soup.find_all('a', href=True):
                link = urljoin(url, a['href'])
                if link.startswith(('http://', 'https://')):
                    if urlparse(link).netloc == urlparse(url).netloc:
                        links.append(link)
            
            logger.info(f"Successfully crawled {url}. Found {len(links)} links and {len(text)} characters of text")
            # Send to indexer
            s3_key= f"crawled/{netloc}/{hashlib.sha1(url.encode()).hexdigest()}.txt"
            s3.put_object(
                Bucket=os.environ['S3_BUCKET'],
                Key=s3_key,
                Body=text.encode(),        
                ContentType="text/plain"
            )
            from tasks import index_content
            index_content.delay(url, depth ,s3_key)
            
            return {
                'url': url,
                'status': 'success',
                'new_urls': links[:5],  # Limit new URLs for testing
                'content_length': len(text),
                'depth': depth
            }
            
        except Exception as e:
            logger.error(f"Failed to crawl {url}: {e}")
            return {
                'url': url,
                'status': 'error',
                'error': str(e),
                'depth': depth
            }