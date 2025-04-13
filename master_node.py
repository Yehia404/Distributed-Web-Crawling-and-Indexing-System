# master_node.py
import logging
import time
from collections import defaultdict
from tasks import app, crawl_page

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MasterNode:
    def __init__(self):
        self.active_crawlers = set()
        self.url_queue = set()
        self.crawled_urls = set()
        self.crawler_status = defaultdict(dict)
        
    def add_seed_urls(self, urls):
        """Add new seed URLs to the crawl queue."""
        for url in urls:
            if url not in self.crawled_urls:
                self.url_queue.add(url)
                logger.info(f"Added seed URL: {url}")

    def distribute_tasks(self):
        """Distribute crawling tasks to available workers."""
        while self.url_queue:
            url = self.url_queue.pop()
            # Send task to Celery queue
            crawl_page.delay(url)
            self.crawled_urls.add(url)
            logger.info(f"Assigned URL to crawler: {url}")

    def monitor_crawlers(self):
        """Monitor crawler health through heartbeats."""
        current_time = time.time()
        for crawler_id, status in self.crawler_status.items():
            last_heartbeat = status.get('last_heartbeat', 0)
            if current_time - last_heartbeat > 30:  # 30 seconds timeout
                logger.warning(f"Crawler {crawler_id} appears to be dead")
                self.handle_crawler_failure(crawler_id)

    def handle_crawler_failure(self, crawler_id):
        """Handle crawler failure by reassigning its tasks."""
        if crawler_id in self.active_crawlers:
            self.active_crawlers.remove(crawler_id)
            # Reassign any pending tasks
            pending_urls = self.crawler_status[crawler_id].get('pending_urls', [])
            self.url_queue.update(pending_urls)
            logger.info(f"Reassigned {len(pending_urls)} URLs from failed crawler {crawler_id}")

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
            master.monitor_crawlers()
            print(master.active_crawlers)
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down master node...")

if __name__ == '__main__':
    main()