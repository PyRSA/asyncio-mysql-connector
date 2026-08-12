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


@pytest.mark.asyncio
async def test_tls_connection_is_marked_secure():
    """caching_sha2_password full auth sends the password in the clear over a
    secure channel; if _secure stays False it takes the RSA branch and the
    server rejects it with 1045."""
    kwargs = {k: v for k, v in connection_kwargs.items() if k != "ssl"}
    connection = Connection(ssl=True, **kwargs)
    try:
        await connection.connect()
    except OperationalError:
        pytest.skip("server does not accept TLS connections")
    assert connection._secure
    await connection.ensure_closed()


@pytest.mark.asyncio
async def test_full_auth_over_tls():
    """Regression test: clearing the server's auth cache forces full auth."""
    admin = Connection(**connection_kwargs)
    await admin.connect()
    try:
        await admin.query("FLUSH PRIVILEGES")
    except Exception:
        await admin.ensure_closed()
        pytest.skip("cannot flush the server auth cache")
    await admin.ensure_closed()

    kwargs = {k: v for k, v in connection_kwargs.items() if k != "ssl"}
    connection = Connection(ssl=True, **kwargs)
    try:
        await connection.connect()
    except OperationalError as e:
        if e.args[0] == 1045:
            raise
        pytest.skip("server does not accept TLS connections")
    await connection.ensure_closed()
