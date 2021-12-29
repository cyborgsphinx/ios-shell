import pytest
import datetime

import ios_shell.utils as utils


@pytest.mark.parametrize(
    "time",
    [
        "UTC 2015/03/16 10:36:00.000",
        "UTC 2015/03/16",
    ],
)
def test_utils_to_iso_produces_usable_datetime(time):
    time_info = utils.to_iso(time)
    assert time_info.year == 2015
    assert time_info.month == 3
    assert time_info.day == 16
    assert time_info.tzinfo is not None


def test_utils_to_iso_produces_none_for_empty_string():
    time_info = utils.to_iso("")
    assert time_info is None

@pytest.mark.parametrize(
    "tzname,expected_offset",
    [
        ("UTC",  0),
        ("GMT",  0),
        ("ADT", -3),
        ("MDT", -6),
        ("MST", -7),
        ("PDT", -7),
        ("PST", -8),
    ]
)
def test_utils_to_iso_converts_time_zones_correctly(tzname, expected_offset):
    time_info = utils.to_iso(tzname + " 2015/03/16 00:00:00")
    assert time_info.tzinfo is not None
    assert time_info.tzinfo.utcoffset(time_info) == datetime.timedelta(hours=expected_offset)
