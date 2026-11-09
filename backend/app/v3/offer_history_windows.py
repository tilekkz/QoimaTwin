"""Every full local window must be unambiguous, eight UTC hours and before cutoff."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.v3.offer_history_models import OfferHistoryChoices


def _instant(day: date, seconds: int, zone: ZoneInfo) -> datetime:
    naive = datetime.combine(day, time()) + timedelta(seconds=seconds)
    local = naive.replace(tzinfo=zone)
    if local.utcoffset() != local.replace(fold=1).utcoffset():
        raise ValueError("Ambiguous or nonexistent local observation boundary")
    utc = local.astimezone(UTC)
    if utc.astimezone(zone).replace(tzinfo=None) != naive:
        raise ValueError("Nonexistent local observation boundary")
    return utc


def observation_windows(value: OfferHistoryChoices) -> tuple[tuple[str, str, str], ...]:
    try:
        zone = ZoneInfo(value.timezone_name)
        cutoff = _instant(value.test_day, 0, zone)
        result = []
        for offset in range(56):
            day = value.test_day - timedelta(days=56 - offset)
            start = _instant(day, value.window_start_second, zone)
            end = _instant(day, value.window_end_second, zone)
            if end - start != timedelta(hours=8) or end >= cutoff:
                raise ValueError("Observation must be eight UTC hours and close before cutoff")
            result.append((day.isoformat(), start.isoformat(), end.isoformat()))
        return tuple(result)
    except (ZoneInfoNotFoundError, OverflowError) as error:
        raise ValueError("Unknown timezone or invalid observation date range") from error
