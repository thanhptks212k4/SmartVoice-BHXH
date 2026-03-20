import redis
import json
from config.config import settings

class RedisManager:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )

    def listen_tasks(self, queue_name):
        return self.client.brpop(queue_name, timeout=0)

    def publish(self, channel, data):
        self.client.publish(channel, json.dumps(data))

redis_manager = RedisManager()