import json
import time
import threading
import os
from kombu.utils.url import safequote
from celery import Celery
from redis_clinet import r
from config import Config

app = Celery('crawler')
print("broker_url           :", app.conf.broker_url)
print("task_always_eager    :", app.conf.task_always_eager)
print("transport options    :", app.conf.broker_transport_options.get("predefined_queues"))


app.conf.broker_url = f'sqs://'
app.conf.broker_transport_options = {
    'region': os.environ.get('AWS_REGION', 'eu-north-1'),
    'visibility_timeout': 3600,
    'predefined_queues': {
        'crawler': {
            'url': os.environ['SQS_QUEUE_URL'],

        },
        'indexer': {
            'url': os.environ['SQS_INDEXER_QUEUE_URL'],

        },
        
    }
}

app.conf.result_backend = None
app.conf.task_ignore_result = True     


def _hb_loop(redis_key: str, member: str, stop_event: threading.Event,
             interval: int = 2) -> None:
    """
    Internal loop that updates the score of `member` in ZSET `redis_key`
    every `interval` seconds until `stop_event` is set.
    """
    while not stop_event.wait(interval):
        r.zadd(redis_key, {member: time.time()})

def start_heartbeat(redis_key: str, member: str,
                    interval: int = 2) -> tuple[threading.Event, threading.Thread]:
    """
    Helper called **inside the Celery task**.  It:
      1. Immediately writes the first heartbeat, so the master can see the
         task even if it dies within < interval seconds.
      2. Spawns a daemon thread that keeps the heartbeat fresh.
    Returns (stop_event, thread) so the caller can shut it down in 'finally'.
    """
    # ❶ INITIAL BEAT
    r.zadd(redis_key, {member: time.time()})

    # ❷ Threaded updates
    stop_event = threading.Event()
    t = threading.Thread(
        target=_hb_loop,
        args=(redis_key, member, stop_event, interval),
        daemon=True                 # make the thread daemonic
    )
    t.start()
    return stop_event, t


@app.task(name='crawl_page', queue='crawler')
def crawl_page(url: str, depth: int):
    """
    Celery task that wraps CrawlerNode.crawl.
    Adds proper heartbeat handling and cleanup.
    """
    from crawler_node import CrawlerNode

    crawler = CrawlerNode()
    crawler_id = f"crawler_{crawl_page.request.id}"

    # Remember what this task is working on (for fail-over)
    r.hset("pending_urls_to_crawl", crawler_id, f"{url}|{depth}")

    # Start heartbeat
    stop_evt, hb_thread = start_heartbeat("active_crawlers", crawler_id,
                                          interval=Config.HEARTBEAT_INTERVAL)

    try:
        result = crawler.crawl(url, depth)
        r.hset("finished_crawls", crawler_id, "done")
        r.set(f"crawl_result:{crawler_id}", json.dumps(result))
        return result

    except Exception as exc:
        r.hset("finished_crawls", crawler_id, "error")
        r.set(f"crawl_result:{crawler_id}",
              json.dumps({"error": str(exc), "depth": depth}))
        raise

    finally:
        # Stop heartbeat and clean Redis bookkeeping
        stop_evt.set()
        hb_thread.join()                    # wait for thread to finish
        r.zrem("active_crawlers", crawler_id)
        r.hdel("pending_urls_to_crawl", crawler_id)


@app.task(name='index_content', queue='indexer')
def index_content(url: str, depth: int, text: str):
    from indexer_node import IndexerNode

    indexer = IndexerNode()
    indexer_id = f"indexer_{index_content.request.id}"

    r.hset("pending_urls_to_index", indexer_id, f"{url}|{depth}")

    stop_evt, hb_thread = start_heartbeat("active_indexers", indexer_id,
                                          interval=Config.HEARTBEAT_INTERVAL)

    try:
        return indexer.add_to_index(url, text)

    finally:
        stop_evt.set()
        hb_thread.join()
        r.zrem("active_indexers", indexer_id)
        r.hdel("pending_urls_to_index", indexer_id) 
