import asyncio

import pytest

import asyncmy
from asyncmy import connect
from asyncmy.connection import Connection
from conftest import connection_kwargs

PASSWORD = connection_kwargs["password"]
NO_PASSWORD = {k: v for k, v in connection_kwargs.items() if k != "password"}


@pytest.mark.asyncio
async def test_sync_creator():
    connection = await connect(password_creator=lambda: PASSWORD, **NO_PASSWORD)
    async with connection.cursor() as cursor:
        await cursor.execute("SELECT 1")
        assert await cursor.fetchone() == (1,)
    await connection.ensure_closed()


@pytest.mark.asyncio
async def test_async_creator():
    async def creator():
        return PASSWORD

    connection = await connect(password_creator=creator, **NO_PASSWORD)
    async with connection.cursor() as cursor:
        await cursor.execute("SELECT 1")
        assert await cursor.fetchone() == (1,)
    await connection.ensure_closed()


@pytest.mark.asyncio
async def test_creator_returning_an_awaitable():
    """A creator wrapping an async client may hand back a Task, not a coroutine."""

    async def fetch():
        return PASSWORD

    connection = await connect(
        password_creator=lambda: asyncio.ensure_future(fetch()), **NO_PASSWORD
    )
    await connection.ensure_closed()


@pytest.mark.asyncio
async def test_creator_returning_bytes():
    connection = await connect(password_creator=lambda: PASSWORD.encode(), **NO_PASSWORD)
    await connection.ensure_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, 1234, object()])
async def test_creator_returning_an_unusable_value(value):
    connection = Connection(password_creator=lambda: value, **NO_PASSWORD)
    with pytest.raises(ValueError, match="must return str or bytes"):
        await connection.connect()


@pytest.mark.asyncio
async def test_creator_takes_precedence_over_password():
    connection = Connection(
        password="wrong-password", password_creator=lambda: PASSWORD, **NO_PASSWORD
    )
    await connection.connect()
    assert connection._connected
    await connection.ensure_closed()


@pytest.mark.asyncio
async def test_creator_called_once_per_connection():
    """The point of the hook: it runs for every connection, not just the first."""
    calls = []

    def creator():
        calls.append(1)
        return PASSWORD

    for _ in range(3):
        connection = await connect(password_creator=creator, **NO_PASSWORD)
        await connection.ensure_closed()
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_pool_refreshes_credentials_per_connection():
    calls = []

    def creator():
        calls.append(1)
        return PASSWORD

    pool = await asyncmy.create_pool(minsize=2, maxsize=2, password_creator=creator, **NO_PASSWORD)
    async with pool.acquire() as connection, connection.cursor() as cursor:
        await cursor.execute("SELECT 1")
    pool.close()
    await pool.wait_closed()

    assert len(calls) >= 2


@pytest.mark.asyncio
async def test_ping_reconnect_refreshes_credentials():
    """A pooled connection that reconnects must not reuse an expired token."""
    passwords = [PASSWORD, PASSWORD]

    def creator():
        return passwords.pop(0)

    connection = await connect(password_creator=creator, **NO_PASSWORD)
    assert len(passwords) == 1
    # Kill the connection underneath so the ping fails and reconnects.
    connection._transport.close()
    await connection.ping(reconnect=True)
    assert passwords == []
    async with connection.cursor() as cursor:
        await cursor.execute("SELECT 1")
        assert await cursor.fetchone() == (1,)
    await connection.ensure_closed()
