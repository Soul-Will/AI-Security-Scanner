from arq import Worker

from src.shared_services.arq_tasks import test_task
from src.shared_services.redis import redis_settings


class WorkerSettings:
    functions = [
        test_task,
    ]

    redis_settings = redis_settings