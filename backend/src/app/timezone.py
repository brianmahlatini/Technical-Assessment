"""Timezone conversion helpers for pharmacy business rules.

Why this file exists:
    The assessment stores timestamps in UTC, but the rolling 30-day dispense
    rule must be evaluated in the pharmacy business timezone. Keeping the
    conversion logic here avoids scattering timezone assumptions through
    services, repositories, tests, and seed scripts.

Design note:
    South Africa currently uses UTC+02:00 year-round. The standard library
    fixed-offset timezone keeps this project dependency-light while still making
    every persisted/comparison timestamp timezone-aware.
"""

import datetime as dt

# Timezone utilities for pharmacy business rules.
#
# All persisted timestamps are UTC-aware, while rolling-window calculations are
# intentionally evaluated in Africa/Johannesburg as required by the brief.
JOHANNESBURG = dt.timezone(dt.timedelta(hours=2))
UTC = dt.UTC


def to_utc(value: dt.datetime) -> dt.datetime:
    """Normalise an aware or naive timestamp to UTC for storage and comparison."""
    # Naive datetimes are interpreted as local Johannesburg business time
    # because form controls and some seed/test inputs may not include an offset.
    if value.tzinfo is None:
        value = value.replace(tzinfo=JOHANNESBURG)

    # Convert all aware values to UTC so database comparisons use one canonical
    # timeline and do not mix local offsets with UTC values.
    return value.astimezone(UTC)


def thirty_day_window_utc(end_utc: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    """Return the inclusive 30-day business window ending at `end_utc`."""
    # Convert to local business time before subtracting days so the window
    # matches the rule the pharmacy cares about, not merely raw UTC arithmetic.
    local_end = to_utc(end_utc).astimezone(JOHANNESBURG)

    # A 30-day lookback includes dispenses from the local instant exactly 30
    # days before the requested dispense through the requested local instant.
    local_start = local_end - dt.timedelta(days=30)

    # Services query UTC columns, so convert both local window boundaries back
    # to UTC before returning them.
    return local_start.astimezone(UTC), local_end.astimezone(UTC)

