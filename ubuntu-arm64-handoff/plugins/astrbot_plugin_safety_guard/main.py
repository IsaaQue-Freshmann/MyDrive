from __future__ import annotations

import functools
import time
from datetime import datetime, timedelta, timezone

from apscheduler.triggers.cron import CronTrigger

from astrbot.api import logger, star
from astrbot.api.event import filter
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.tools.cron_tools import FutureTaskTool

MIN_INTERVAL_HOURS = 2
MIN_INTERVAL_SECONDS = MIN_INTERVAL_HOURS * 60 * 60
WARNING_TEXT = (
    "检测到疑似攻击行为，请规避。"
    f"最短周期为 {MIN_INTERVAL_HOURS} 小时，该重复任务已被拒绝。"
)
_WARN_COOLDOWN_SECONDS = 60
_last_warn: dict[str, float] = {}


def _minimum_cron_interval_seconds(cron_expression: str) -> float | None:
    try:
        trigger = CronTrigger.from_crontab(cron_expression, timezone=timezone.utc)
        now = datetime.now(timezone.utc)
        first = trigger.get_next_fire_time(None, now)
        if first is None:
            return None
        second = trigger.get_next_fire_time(first, first + timedelta(seconds=1))
        if second is None:
            return None
        return (second - first).total_seconds()
    except Exception:
        return None


def _is_safe_schedule(cron_expression: str) -> bool:
    interval = _minimum_cron_interval_seconds(cron_expression)
    return interval is not None and interval >= MIN_INTERVAL_SECONDS


async def _send_warning(event, sender_id: str) -> None:
    if event is None:
        return
    now = time.monotonic()
    if now - _last_warn.get(sender_id, 0.0) < _WARN_COOLDOWN_SECONDS:
        return
    _last_warn[sender_id] = now
    try:
        await event.send(MessageChain().message(WARNING_TEXT))
    except Exception:
        logger.exception("safety-guard | failed to send warning to QQ")


def _install_future_task_guard() -> None:
    if getattr(FutureTaskTool.call, "_safety_guard_installed", False):
        return
    original_call = FutureTaskTool.call

    @functools.wraps(original_call)
    async def guarded_call(self, context, **kwargs):
        action = str(kwargs.get("action") or "").strip().lower()
        event = getattr(getattr(context, "context", None), "event", None)
        sender_id = getattr(event, "get_sender_id", lambda: "")() if event else ""
        role = getattr(event, "role", "member") if event else "member"

        if action in {"create", "edit"}:
            schedule_changed = action == "create" or "cron_expression" in kwargs
            run_once = bool(kwargs.get("run_once", False))
            cron_expression = str(kwargs.get("cron_expression") or "").strip()

            if schedule_changed and not run_once and cron_expression:
                if not _is_safe_schedule(cron_expression):
                    logger.warning(
                        "safety-guard | blocked short-period schedule | "
                        "sender=%s action=%s cron=%r",
                        sender_id,
                        action,
                        cron_expression,
                    )
                    await _send_warning(event, sender_id or "unknown")
                    return "error: schedule rejected by the 2-hour minimum period policy."

            if role != "admin":
                logger.warning(
                    "safety-guard | blocked non-admin schedule | sender=%s action=%s",
                    sender_id,
                    action,
                )
                return (
                    "error: Permission denied. Only AstrBot administrators may "
                    "create or edit scheduled tasks."
                )

        return await original_call(self, context, **kwargs)

    guarded_call._safety_guard_installed = True
    FutureTaskTool.call = guarded_call
    logger.info("safety-guard | future_task protection installed")


class Main(star.Star):
    def __init__(self, context: star.Context, config: dict | None = None) -> None:
        super().__init__(context, config)
        _install_future_task_guard()

    @filter.on_astrbot_loaded()
    async def on_loaded(self) -> None:
        logger.info("safety-guard | loaded with 2-hour minimum schedule period")
