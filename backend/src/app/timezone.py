import datetime as dt
from typing import Tuple

# Timezone utilities for pharmacy business rules.
#
# All persisted timestamps are UTC-aware, while rolling-window calculations are
# intentionally evaluated in Africa/Johannesburg as required by the brief.
JOHANNESBURG = dt.timezone(dt.timedelta(hours=2))
UTC = dt.timezone.utc


def to_utc(value: dt.datetime) -> dt.datetime:
    # Normalise an aware or naive timestamp to UTC for storage and comparison.
    if value.tzinfo is None:
        value = value.replace(tzinfo=JOHANNESBURG)
    return value.astimezone(UTC)


def thirty_day_window_utc(end_utc: dt.datetime) -> Tuple[dt.datetime, dt.datetime]:
    # Return the inclusive 30-day business window ending at end_utc.
    local_end = to_utc(end_utc).astimezone(JOHANNESBURG)
    local_start = local_end - dt.timedelta(days=30)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)

