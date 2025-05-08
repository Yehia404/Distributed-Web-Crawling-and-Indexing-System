import redis,ssl
from config import Config 

r = redis.StrictRedis(host=Config.REDIS_HOST,port=Config.REDIS_PORT,ssl=True,ssl_cert_reqs=ssl.CERT_NONE,ssl_check_hostname=False,decode_responses=True)