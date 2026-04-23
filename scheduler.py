"""Background polling scheduler that dispatches due Discord posts."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

import db
import sender

log = logging.getLogger(__name__)

POLL_SECONDS = 30


def dispatch_due() -> None:
    now = datetime.now(timezone.utc)
    try:
        claimed = db.claim_due(now)
    except Exception:
        log.exception("Failed to claim due posts")
        return

    for row in claimed:
        post_id = row["id"]
        try:
            sender.send(row["webhook_url"], row["content"], row["image_path"])
            db.mark_sent(post_id)
            log.info("Sent post %s", post_id)
        except Exception as e:
            log.exception("Failed to send post %s", post_id)
            db.mark_failed(post_id, str(e))


def start() -> BackgroundScheduler:
    recovered = db.reset_stuck_sending()
    if recovered:
        log.warning("Recovered %d post(s) stuck in 'sending' from a previous run", recovered)

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        dispatch_due,
        "interval",
        seconds=POLL_SECONDS,
        id="dispatch_due",
        next_run_time=datetime.now(timezone.utc),
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("Scheduler started (poll every %ss)", POLL_SECONDS)
    return scheduler
