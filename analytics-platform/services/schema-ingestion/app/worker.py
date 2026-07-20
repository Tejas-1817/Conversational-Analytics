"""RQ worker entry point. Run with: python -m app.worker"""
from redis import Redis
from rq import Queue, Worker, SimpleWorker
import os

from app.config import get_settings

if __name__ == "__main__":
    connection = Redis.from_url(get_settings().redis_url)
    WorkerClass = SimpleWorker if os.name == 'nt' else Worker
    worker = WorkerClass([Queue("ingestion", connection=connection), Queue("chat", connection=connection)], connection=connection)
    worker.work(with_scheduler=False)
