from __future__ import annotations

import struct

import pytest

from asyncmy import errors


def _err_packet(errno: int, sqlstate: str | None, message: str) -> bytes:
    """Build an ERR_Packet body as the server sends it."""
    packet = b"\xff" + struct.pack("<H", errno)
    if sqlstate is not None:
        packet += b"#" + sqlstate.encode()
    return packet + message.encode()


def test_sqlstate_is_parsed():
    with pytest.raises(errors.ProgrammingError) as exc_info:
        errors.raise_mysql_exception(_err_packet(1146, "42S02", "Table 'db.tbl' doesn't exist"))
    assert exc_info.value.sqlstate == "42S02"


def test_sqlstate_is_none_when_absent():
    with pytest.raises(errors.MySQLError) as exc_info:
        errors.raise_mysql_exception(_err_packet(1064, None, "syntax error"))
    assert exc_info.value.sqlstate is None


def test_args_unchanged_by_sqlstate():
    """args stays (errno, message) — the SQLSTATE must not leak into it."""
    with pytest.raises(errors.MySQLError) as exc_info:
        errors.raise_mysql_exception(_err_packet(1146, "42S02", "nope"))
    assert exc_info.value.args == (1146, "nope")


def test_sqlstate_defaults_to_none_when_raised_client_side():
    assert errors.OperationalError(2013, "Lost connection").sqlstate is None
