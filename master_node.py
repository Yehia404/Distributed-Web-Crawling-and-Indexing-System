# master_node.py
import json
import logging
import time
from collections import defaultdict
from redis_clinet import r
from config import Config
from urllib.parse import urlparse
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MasterNode:
    def __init__(self):
        self.active_crawlers = set()
        self.url_queue = {}
        self.crawled_urls = set()
        self.active_indexers = set()
        r.zremrangebyrank("active_crawlers", 0, -1)
        r.zremrangebyrank("active_indexers", 0, -1)
        self.max_depth = 1 # Maximum crawl depth; None means no limit.
        self.allowed_domains = None # List of allowed domains; None means all domains allowed.
        
    def set_crawl_options(self, max_depth, allowed_domains):
        """
        Set the crawl options.
        """
        self.max_depth = max_depth
        self.allowed_domains = allowed_domains if allowed_domains and len(allowed_domains) > 0 else None
        logger.info(f"Crawl options set. Max depth: {self.max_depth}. Allowed domains: {self.allowed_domains}")

    def is_allowed_domain(self, url):
        """
        Check whether the URL's domain is within the allowed domains.
        If self.allowed_domains is None, all domains are allowed.
        """
        if not self.allowed_domains:
            return True
        domain = urlparse(url).netloc.lower()
        return any(allowed.lower() in domain for allowed in self.allowed_domains)
        
    def add_seed_urls(self, urls):
        """
        Add new seed URLs into the queue with depth 1, subject to the allowed domains.
        """
        for url in urls:
            if url in self.crawled_urls:
                logger.info(f"url: {url} already cralwed before. Aborting...")
            if url not in self.crawled_urls and self.is_allowed_domain(url):
                self.url_queue[url] = 1
                logger.info(f"Added seed URL: {url} (depth: 1)")
                
    def add_new_urls(self, new_urls, parent_depth):
        """
        Add new URLs extracted from a crawl to the URL queue.
        Each new URL's depth is parent_depth + 1.
        Enforce the max_depth limit (if set) and allowed domains.
        """
        new_depth = parent_depth + 1
        # If max_depth is set and new_depth exceeds it, do not add URLs.
        if new_depth > self.max_depth:
            return
        for url in new_urls:
            if url not in self.crawled_urls and self.is_allowed_domain(url):
                if url not in self.url_queue:
                    self.url_queue[url] = new_depth
                    logger.info(f"Queued new URL: {url} (depth: {new_depth})")
                    
    def distribute_tasks(self):
        """
        Distribute crawling tasks to available workers.
        Each task receives a URL and its current crawl depth.
        """
        from tasks import crawl_page
        while self.url_queue :
            url, depth = self.url_queue.popitem()
            try:
                result = crawl_page.delay(url, depth)
                self.crawled_urls.add(url)
                logger.info(f"Assigned URL to crawler: {url} (depth: {depth})")
            except Exception as e:
                logger.exception("Failed to publish task: %s", e)
    def monitor_finished_tasks(self):
        """
        Poll Redis for finished crawl tasks, fetch their results, 
        extract new URLs and reassign them.
        """
        # Get all keys from finished_crawls.
        finished = r.hgetall("finished_crawls")
        for crawler_id, status in finished.items():
            if isinstance(crawler_id, bytes):
                crawler_id = crawler_id.decode("utf-8")
            # Get the result stored in Redis.
            result_json = r.get(f"crawl_result:{crawler_id}")
            if result_json:
                if isinstance(result_json, bytes):
                    result_json = result_json.decode("utf-8")
                try:
                    result = json.loads(result_json)
                    # If the result indicates success and contains new_urls:
                    if result.get("status") == "success" and "new_urls" in result:
                        # Use the returned parent depth to calculate new depth.
                        parent_depth = result.get("depth", 1)
                        new_urls = result.get("new_urls", [])
                        self.add_new_urls(new_urls, parent_depth)
                        logger.info(f"Processed finished task {crawler_id}: added {len(new_urls)} new URLs.")
                    else:
                        logger.info(f"Finished task {crawler_id} with status: {result.get('status')}")
                except Exception as e:
                    logger.error(f"Error processing crawl result for {crawler_id}: {e}")
                # Clean up processed keys.
                r.hdel("finished_crawls", crawler_id)
                r.delete(f"crawl_result:{crawler_id}")
                
    def update_workers_from_redis(self):
        current_time = time.time()
        cutoff = current_time - Config.HEARTBEAT_INTERVAL
        active_c = r.zrangebyscore("active_crawlers", cutoff, float('inf'))
        self.active_crawlers = set(active_c)
        stale_crawlers = set(r.zrangebyscore("active_crawlers", '-inf', cutoff))
        active_i = r.zrangebyscore("active_indexers", cutoff, float('inf'))
        self.active_indexers = set(active_i)
        stale_indexers = set(r.zrangebyscore("active_indexers", '-inf', cutoff))
        return stale_crawlers, stale_indexers

    def monitor_workers(self):
        """Monitor workers' health via heartbeat updates from Redis."""
        stale_crawlers, stale_indexers = self.update_workers_from_redis()
        for crawler_id in stale_crawlers:
            logger.warning(f"Crawler {crawler_id} appears to be dead")
            self.handle_crawler_failure(crawler_id)
        for indexer_id in stale_indexers:
            logger.warning(f"Indexer {indexer_id} appears to be dead")
            self.handle_indexer_failure(indexer_id)
            
    def handle_crawler_failure(self, crawler_id):
        pending_entry = r.hget("pending_urls_to_crawl", crawler_id)
        if pending_entry:
            # If coming from Redis, the value might be a bytes object.
            if isinstance(pending_entry, bytes):
                pending_entry = pending_entry.decode("utf-8")
            try:
                url, depth_str = pending_entry.split("|")
                depth = int(depth_str)
            except Exception as e:
                logger.error(f"Error decoding pending entry for crawler {crawler_id}: {e}")
                url = pending_entry
                depth = 1
            # Reassign the URL with its previously stored depth.
            self.url_queue[url] = depth
            logger.info(f"Reassigned {url} with depth {depth} from failed crawler {crawler_id}")
        r.hdel("pending_urls_to_crawl", crawler_id)
        
        
    def handle_indexer_failure(self, indexer_id):
        pending_entry = r.hget("pending_urls_to_index", indexer_id)
        if pending_entry:
            # If coming from Redis, the value might be a bytes object.
            if isinstance(pending_entry, bytes):
                pending_entry = pending_entry.decode("utf-8")
            try:
                url, depth_str = pending_entry.split("|")
                depth = int(depth_str)
            except Exception as e:
                logger.error(f"Error decoding pending entry for indexer {indexer_id}: {e}")
                url = pending_entry
                depth = 1
            # Reassign the URL with its previously stored depth.
            self.url_queue[url] = depth
            logger.info(f"Reassigned {url} with depth {depth} from failed indexer {indexer_id}")
        r.hdel("pending_urls_to_index", indexer_id)

def main():
    master = MasterNode()
    # Add some real website URLs
    seed_urls = [
        "https://python.org",
        "https://docs.python.org",
        "https://pypi.org",
        "https://github.com/python",
        "https://realpython.com"
    ]
    master.add_seed_urls(seed_urls)
    
    try:
        while True:
            master.distribute_tasks()
            master.monitor_workers()
            print(master.active_crawlers)
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down master node...")

if __name__ == '__main__':
    main()