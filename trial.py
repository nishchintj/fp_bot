import os
from dotenv import load_dotenv

load_dotenv()

redis_host = os.getenv("REDIS_HOST")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_index = int(os.getenv("REDIS_INDEX", "1"))
print(redis_host)
print(redis_port)
print(redis_index)
