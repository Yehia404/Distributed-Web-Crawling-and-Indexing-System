import redis
from config import Config 
import os

r = redis.StrictRedis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, decode_responses=True, ssl=True, password=os.environ['REDIS_AUTH_TOKEN'],ssl_cert_reqs=None)