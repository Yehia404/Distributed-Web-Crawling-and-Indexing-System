# config.py
import os

class Config:
    # Base directory for the project
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Redis configuration
    REDIS_HOST = os.environ.get('REDIS_HOST', 'my-redis.xxxxxx.ng.0001.use1.cache.amazonaws.com')
    REDIS_PORT = 6379
    REDIS_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
    
    # Crawler settings
    CRAWL_DELAY = 1  # seconds
    MAX_RETRIES = 3
    HEARTBEAT_INTERVAL = 30  # seconds
    MAX_CRAWLERS = 7
    
    # Index file location
    INDEX_DIR = os.path.join(BASE_DIR, 'data')
    INDEX_FILE = os.path.join(INDEX_DIR, 'index_store.json')
    
    # Politeness settings
    USER_AGENT = 'MyCustomBot/1.0'
    ROBOTS_CACHE_EXPIRE = 3600  # 1 hour