"""In-process scheduler: periodically checks every company's agent config
and runs any that are due, based on run_frequency_hours / last_run_at.

This is deliberately simple (no separate worker process, no job queue) —
fine for a modest number of companies. If this needs to scale to many
tenants or tighter scheduling precision, move to Celery/RQ + Redis instead.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler

from .agent_runner import run_agent_for_company
from .db import SessionLocal
from .models import AgentConfig

CHECK_INTERVAL_MINUTES = 15

_scheduler: Optional[BackgroundScheduler] = None


def _run_due_agents():
    with SessionLocal() as db:
        configs = db.query(AgentConfig).all()
        due_company_ids = []
        for config in configs:
            if not config.last_run_at:
                due_company_ids.append(config.company_id)
                continue
            next_due = config.last_run_at + timedelta(hours=config.run_frequency_hours)
            if datetime.utcnow() >= next_due:
                due_company_ids.append(config.company_id)

    for company_id in due_company_ids:
        try:
            run_agent_for_company(company_id)
        except Exception as exc:
            # A per-company failure shouldn't take down the scheduler loop.
            print(f"[scheduler] agent run failed for company {company_id}: {exc}")


def start_scheduler():
    """Starts an in-process background scheduler. Only safe when exactly one
    process is running it — with multiple gunicorn workers, every worker
    would run its own copy and duplicate agent runs / emails. Use
    run_scheduler_forever() in a dedicated single process instead for any
    deployment with more than one web worker."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_run_due_agents, "interval", minutes=CHECK_INTERVAL_MINUTES, next_run_time=datetime.utcnow())
    _scheduler.start()
    return _scheduler


def run_scheduler_forever():
    """Blocking scheduler for a dedicated worker process/dyno — the safe
    choice once the web app runs with more than one gunicorn worker."""
    scheduler = BlockingScheduler()
    scheduler.add_job(_run_due_agents, "interval", minutes=CHECK_INTERVAL_MINUTES, next_run_time=datetime.utcnow())
    scheduler.start()
