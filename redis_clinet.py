import redis
from config import Config 

r = redis.StrictRedis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, decode_responses=True, ssl=True, ssl_cert_reqs=None)