"""Работа с датами и часовыми поясами."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings

_settings = get_settings()
APP_TZ = ZoneInfo(_settings.app_timezone)

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def local_today() -> date:
    return datetime.now(APP_TZ).date()

def earliest_pickup_date() -> date:
    """BR-03: не раньше локальной даты + 2 календарных дня."""
    return local_today() + timedelta(days=2)

def is_pickup_date_valid(d: date) -> bool:
    return d >= earliest_pickup_date()
