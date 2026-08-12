import pytest

import asyncmy
from asyncmy import connect
from asyncmy.errors import ProgrammingError
from conftest import connection_kwargs


async def _connect(**extra):
    # connection_kwargs already carries echo, so extra must win over it.
    return await connect(**{**connection_kwargs, **extra})


@pytest.mark.asyncio
async def test_callback_receives_query_and_duration():
    calls = []
    connection = await _connect(query_callback=lambda c, q, ms: calls.append((c, q, ms)))
    async with connection.cursor() as cursor:
        await cursor.execute("SELECT 1")
    await connection.ensure_closed()

    assert len(calls) == 1
    cursor_arg, query, elapsed = calls[0]
    assert query == "SELECT 1"
    assert isinstance(elapsed, float)
    assert elapsed >= 0
    assert isinstance(cursor_arg, asyncmy.cursors.Cursor)


@pytest.mark.asyncio
async def test_callback_measures_slow_queries():
    calls = []
    connection = await _connect(query_callback=lambda c, q, ms: calls.append((q, ms)))
    async with connection.cursor() as cursor:
        await cursor.execute("SELECT 1")
        await cursor.execute("DO SLEEP(0.2)")
    await connection.ensure_closed()

    durations = dict((q, ms) for q, ms in calls)
    assert durations["DO SLEEP(0.2)"] >= 200
    assert durations["SELECT 1"] < durations["DO SLEEP(0.2)"]


@pytest.mark.asyncio
async def test_executemany_reports_once():
    """The caller wrote one executemany; report it as one statement."""
    calls = []
    connection = await _connect(query_callback=lambda c, q, ms: calls.append(q))
    async with connection.cursor() as cursor:
        await cursor.execute("CREATE TEMPORARY TABLE test.cb_test (a int)")
        await cursor.executemany("INSERT INTO test.cb_test VALUES (%s)", [(1,), (2,), (3,)])
    await connection.ensure_closed()

    assert sum(1 for q in calls if q.startswith("INSERT")) == 1


@pytest.mark.asyncio
async def test_failed_statement_is_not_reported():
    """Like echo, which only logs after a statement succeeds."""
    calls = []
    connection = await _connect(query_callback=lambda c, q, ms: calls.append(q))
    async with connection.cursor() as cursor:
        with pytest.raises(ProgrammingError):
            await cursor.execute("SELECT 1 FROM")  # syntax error
    await connection.ensure_closed()

    assert calls == []


@pytest.mark.asyncio
async def test_no_callback_by_default():
    connection = await _connect()
    async with connection.cursor() as cursor:
        await cursor.execute("SELECT 1")
        assert await cursor.fetchone() == (1,)
    await connection.ensure_closed()


@pytest.mark.asyncio
async def test_echo_and_callback_are_independent(caplog):
    calls = []
    connection = await _connect(echo=True, query_callback=lambda c, q, ms: calls.append(q))
    with caplog.at_level("INFO", logger="asyncmy"):
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT 1")
    await connection.ensure_closed()

    assert calls == ["SELECT 1"]
    assert any("SELECT 1" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_pool_passes_callback_to_connections():
    calls = []
    pool = await asyncmy.create_pool(
        **connection_kwargs, query_callback=lambda c, q, ms: calls.append(q)
    )
    async with pool.acquire() as connection, connection.cursor() as cursor:
        await cursor.execute("SELECT 1")
    pool.close()
    await pool.wait_closed()

    assert calls == ["SELECT 1"]
