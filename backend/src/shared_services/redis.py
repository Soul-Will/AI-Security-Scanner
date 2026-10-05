from arq.connections import RedisSettings


REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379


redis_settings = RedisSettings(
    host=REDIS_HOST,
    port=REDIS_PORT,
)