import re
import ssl as ssl_module

import pytest

from asyncmy.connection import Connection
from asyncmy.errors import OperationalError
from conftest import connection_kwargs


@pytest.mark.asyncio
async def test_connect():
    connection = Connection(**connection_kwargs)
    await connection.connect()
    assert connection._connected
    assert re.match(
        r"\d+\.\d+\.\d+([^0-9].*)?",
        connection.get_server_info(),
    )
    assert connection.get_proto_info() == 10
    assert connection.get_host_info() != "Not Connected"
    await connection.ensure_closed()


@pytest.mark.asyncio
async def test_read_timeout():
    with pytest.raises(OperationalError):
        connection = Connection(read_timeout=1, **connection_kwargs)
        await connection.connect()
        async with connection.cursor() as cursor:
            await cursor.execute("DO SLEEP(3)")


@pytest.mark.asyncio
async def test_ssl_true_builds_a_context():
    """`ssl=True` must actually enable TLS, not silently fall back to plaintext."""
    connection = Connection(ssl=True)
    assert isinstance(connection._ssl_context, ssl_module.SSLContext)


@pytest.mark.asyncio
async def test_ssl_context_is_passed_through():
    context = ssl_module.create_default_context()
    assert Connection(ssl=context)._ssl_context is context


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, False])
async def test_ssl_disabled(value):
    assert Connection(ssl=value)._ssl_context is None


@pytest.mark.asyncio
async def test_ssl_rejects_unusable_value():
    """A CA path passed as a bare string used to disable TLS silently."""
    with pytest.raises(ValueError):
        Connection(ssl="/path/to/ca.pem")


@pytest.mark.asyncio
async def test_transaction(connection):
    await connection.begin()
    await connection.query(
        """INSERT INTO test.asyncmy(`decimal`, date, datetime, `float`,
         string, `tinyint`) VALUES (%s,'%s','%s',%s,'%s',%s)"""
        % (
            1,
            "2020-08-08",
            "2020-08-08 00:00:00",
            1,
            "1",
            1,
        ),
        True,
    )
    await connection.rollback()
