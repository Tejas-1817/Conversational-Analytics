"""RQ worker entry point. Run with: python -m app.worker"""
from redis import Redis
from rq import Queue, Worker, SimpleWorker
import os
import uuid
import structlog

from app.config import get_settings
from app.db import session_scope
from app.models import ConversationMessage

log = structlog.get_logger()


def chat_job_exc_handler(job, exc_type, exc_value, traceback):
    """RQ exception handler: update the ConversationMessage row to status='error'
    when a chat job fails at the RQ level (timeout, crash, etc.).
    This is Layer B of the three-layer timeout defense."""
    log.error("RQ job failed", job_id=job.id, exc_type=str(exc_type), exc_value=str(exc_value))

    # Extract msg_id from the job's args — process_chat_message(tenant_id, conv_id, msg_id, raw_query)
    try:
        args = job.args
        if args and len(args) >= 3:
            msg_id = args[2]
            with session_scope() as db:
                asst_msg = db.query(ConversationMessage).filter(
                    ConversationMessage.id == msg_id
                ).first()
                if asst_msg and asst_msg.status == "processing":
                    asst_msg.status = "error"
                    asst_msg.content = "The request timed out or encountered an unexpected error. Please try again."
                    asst_msg.error = f"{exc_type.__name__}: {exc_value}"
                    db.commit()
                    log.info("Updated stuck message to error", msg_id=str(msg_id))
    except Exception as handler_exc:
        log.error("Exception handler itself failed", error=str(handler_exc))

    return True  # returning True tells RQ we handled the exception


if __name__ == "__main__":
    connection = Redis.from_url(get_settings().redis_url)
    WorkerClass = SimpleWorker if os.name == 'nt' else Worker
    queues = [Queue("ingestion", connection=connection), Queue("chat", connection=connection)]
    worker = WorkerClass(queues, connection=connection, exception_handlers=[chat_job_exc_handler])
    worker.work(with_scheduler=False)
