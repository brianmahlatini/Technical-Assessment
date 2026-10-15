"""Timezone utility tests.

These tests protect the boundary called out in the brief: API timestamps are
stored in UTC, while business windows are calculated in Africa/Johannesburg.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.timezone import JOHANNESBURG, thirty_day_window_utc, to_utc

pytestmark = pytest.mark.no_db


def test_naive_timestamp_is_treated_as_johannesburg_local_time():
    """A caller without timezone info is interpreted as local business time."""
    result = to_utc(datetime(2025, 1, 15, 10, 0, 0))

    assert result == datetime(2025, 1, 15, 8, 0, 0, tzinfo=timezone.utc)


def test_aware_timestamp_is_normalised_to_utc():
    """An aware timestamp keeps its instant while changing to UTC."""
    result = to_utc(datetime(2025, 1, 15, 10, 0, 0, tzinfo=JOHANNESBURG))

    assert result == datetime(2025, 1, 15, 8, 0, 0, tzinfo=timezone.utc)


def test_thirty_day_window_is_calculated_in_johannesburg_time():
    """The rolling window is local-business-time first, then converted to UTC."""
    end = datetime(2025, 1, 31, 22, 30, 0, tzinfo=timezone.utc)

    start_utc, end_utc = thirty_day_window_utc(end)

    assert end_utc == end
    assert start_utc.astimezone(ZoneInfo("Africa/Johannesburg")) == datetime(2025, 1, 2, 0, 30, 0, tzinfo=JOHANNESBURG)

