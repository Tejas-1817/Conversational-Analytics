"""RQ worker entry point. Run with: python -m app.worker"""
from redis import Redis
from rq import Queue, Worker

from app.config import get_settings

if __name__ == "__main__":
    connection = Redis.from_url(get_settings().redis_url)
    worker = Worker([Queue("ingestion", connection=connection)], connection=connection)
    worker.work(with_scheduler=False)
