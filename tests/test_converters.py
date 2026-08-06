import datetime

from asyncmy.converters import convert_datetime, escape_item, escape_str


class CustomDate(datetime.date):
    pass


def test_escape_item():
    assert escape_item("\\\n\r\032\"'foobar\0", "utf-8") == "'\\\\\\n\\r\\Z\\\"\\'foobar\\0'"
    assert escape_item(datetime.date(2023, 6, 2), "utf-8") == "'2023-06-02'"
    assert escape_item(CustomDate(2023, 6, 2), "utf-8") == "'2023-06-02'"


def test_escape_str():
    assert escape_str("\\\n\r\032\"'foobar\0") == "'\\\\\\n\\r\\Z\\\"\\'foobar\\0'"

    # The encoder for the str type is a default encoder,
    # so it should accept values that are not strings as well.
    assert escape_str(datetime.date(2023, 6, 2)) == "'2023-06-02'"
    assert escape_str(CustomDate(2023, 6, 2)) == "'2023-06-02'"


def test_convert_datetime():
    assert convert_datetime("2023-06-02T23:06:20") == datetime.datetime(2023, 6, 2, 23, 6, 20)
    assert convert_datetime("2023-06-02 23:06:20") == datetime.datetime(2023, 6, 2, 23, 6, 20)

    # invalid datetime should be returned as str
    assert convert_datetime("0000-00-00 00:00:00") == "0000-00-00 00:00:00"


def test_escape_unsigned_big_int():
    # unsigned BIGINT max used to overflow the C `long long` parameter (#35)
    assert escape_item(2**64 - 1, "utf-8") == str(2**64 - 1)
    assert escape_item(-(2**63), "utf-8") == str(-(2**63))
    assert escape_item(0, "utf-8") == str(0)
