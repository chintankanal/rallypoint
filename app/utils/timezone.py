from datetime import date, datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")


def end_of_day_ist(d: date) -> datetime:
    """Return 23:59:59 IST on the given date, as a UTC-aware datetime."""
    ist_eod = datetime.combine(d, time(23, 59, 59), tzinfo=IST)
    return ist_eod.astimezone(UTC)


def now_ist() -> datetime:
    return datetime.now(tz=IST)


def today_ist() -> date:
    return now_ist().date()
