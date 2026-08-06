import datetime
from decimal import Decimal

import pytest

import asyncmy
from conftest import connection_kwargs


@pytest.mark.asyncio
async def test_transparent_stmt_cache():
    conn = await asyncmy.connect(stmt_cache_size=8, **connection_kwargs)
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT %s + %s", (40, 2))
            assert (await cur.fetchone()) == (42,)
            assert len(conn._stmt_cache) == 1
            # cache hit
            await cur.execute("SELECT %s + %s", (1, 2))
            assert (await cur.fetchone()) == (3,)
            assert len(conn._stmt_cache) == 1
            # %% literal passthrough
            await cur.execute("SELECT %s LIKE '%%bc'", ("abc",))
            assert (await cur.fetchone()) == (1,)
            # dict args fall back to the text protocol
            await cur.execute("SELECT %(a)s + 1", {"a": 9})
            assert (await cur.fetchone()) == (10,)
            # multi-statement is unpreparable: silent text fallback
            await cur.execute("SELECT %s; SELECT 2", (1,))
            assert (await cur.fetchone()) == (1,)
            assert await cur.nextset()
            assert (await cur.fetchall()) == ((2,),)
            # typed round-trip through the transparent binary path
            await cur.execute(
                "SELECT CAST(%s AS DATETIME(6)), CAST(%s AS DECIMAL(10,2))",
                (datetime.datetime(2022, 5, 6, 7, 8, 9, 100), Decimal("3.14")),
            )
            assert (await cur.fetchone()) == (
                datetime.datetime(2022, 5, 6, 7, 8, 9, 100),
                Decimal("3.14"),
            )
            # LRU eviction respects the capacity
            for k in range(12):
                await cur.execute(f"SELECT {k} + %s", (1,))
            assert len(conn._stmt_cache) <= 8
    finally:
        await conn.ensure_closed()


@pytest.mark.asyncio
async def test_stmt_cache_disabled_by_default(connection):
    async with connection.cursor() as cur:
        await cur.execute("SELECT %s", (1,))
        assert (await cur.fetchone()) == (1,)
    assert len(connection._stmt_cache) == 0
