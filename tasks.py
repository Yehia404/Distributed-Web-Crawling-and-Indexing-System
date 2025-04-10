# tasks.py
from celery import Celery
from config import Config

app = Celery('crawler', broker=Config.REDIS_URL)

@app.task(name='crawl_page')
def crawl_page(url):
    from crawler_node import CrawlerNode
    crawler = CrawlerNode()
    return crawler.crawl(url)

@app.task(name='index_content')
def index_content(url, text):
    from indexer_node import IndexerNode
    indexer = IndexerNode()
    return indexer.add_to_index(url, text)