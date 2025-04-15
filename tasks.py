# tasks.py
import json
from celery import Celery
from config import Config   
import time
import threading
from redis_clinet import r
app = Celery('crawler', broker=Config.REDIS_URL)

def send_heartbeat(id, name, stop_event ,interval=2):
    while not stop_event.wait(interval):
        r.zadd(name, {id: time.time()})

@app.task(name='crawl_page')
def crawl_page(url, depth):
    from crawler_node import CrawlerNode
    crawler = CrawlerNode()
    crawler_id = f"crawler_{crawl_page.request.id}"
    r.hset("pending_urls_to_crawl", crawler_id, f"{url}|{depth}")
    # Create an event to signal when the task is complete.
    stop_event = threading.Event()
    name = "active_crawlers"
    # Start the heartbeat thread.
    heartbeat_thread = threading.Thread(
        target=send_heartbeat,
        args=(crawler_id, name ,stop_event, 2)
    )
    heartbeat_thread.start()
    try:
        result = crawler.crawl(url, depth)
        # Once finished, store the result in Redis.
        r.hset("finished_crawls", crawler_id, "done")
        r.set(f"crawl_result:{crawler_id}", json.dumps(result))
        return result
    except Exception as e:
        r.hset("finished_crawls", crawler_id, "error")
        r.set(f"crawl_result:{crawler_id}", json.dumps({"error": str(e), "depth": depth}))
        raise
    finally:
        stop_event.set()
        heartbeat_thread.join()
        r.zrem("active_crawlers", crawler_id)
        r.hdel("pending_urls_to_crawl", crawler_id)

@app.task(name='index_content')
def index_content(url, depth,text):
    from indexer_node import IndexerNode
    indexer = IndexerNode()
    indexer_id = f"indexer_{index_content.request.id}"
    r.hset("pending_urls_to_index", indexer_id, f"{url}|{depth}")
    # Create an event to signal when the task is complete.
    stop_event = threading.Event()
    name = "active_indexers"
    # Start the heartbeat thread.
    heartbeat_thread = threading.Thread(
        target=send_heartbeat,
        args=(indexer_id,name,stop_event, 2)
    )
    heartbeat_thread.start()
    try:
        return indexer.add_to_index(url, text)
    finally:
        # Signal the heartbeat thread to stop and wait for it.
        stop_event.set()
        heartbeat_thread.join()
        # Clean up Redis state.
        r.zrem("active_indexers", indexer_id)
        r.hdel("pending_urls_to_index", indexer_id) 
