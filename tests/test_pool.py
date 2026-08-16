import asyncio

import pytest
from conftest import connection_kwargs

import asyncmy
from asyncmy.connection import Connection


@pytest.mark.asyncio
async def test_pool(pool):
    assert pool.minsize == 1
    assert pool.maxsize == 10
    assert pool.size == 1
    assert pool.freesize == 1


@pytest.mark.asyncio
async def test_pool_cursor(pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1")
            ret = await cursor.fetchone()
            assert ret == (1,)


@pytest.mark.asyncio
async def test_acquire(pool):
    conn = await pool.acquire()
    assert isinstance(conn, Connection)
    assert pool.freesize == 0
    assert pool.size == 1
    assert conn.connected
    await pool.release(conn)
    assert pool.freesize == 1
    assert pool.size == 1


@pytest.mark.asyncio
async def test_wait_closed_wakes_on_in_transaction_release():
    """Releasing the last connection while it is inside a transaction must
    wake a parked wait_closed(), see #154."""
    pool = await asyncmy.create_pool(minsize=0, maxsize=4, autocommit=True, **connection_kwargs)
    conn = await pool.acquire()
    await conn.begin()
    async with conn.cursor() as cursor:
        await cursor.execute("SELECT 1")
        await cursor.fetchall()

    pool.close()
    waiter = asyncio.create_task(pool.wait_closed())
    await asyncio.sleep(0.1)  # let wait_closed() park on the condition
    assert not waiter.done()

    await pool.release(conn)
    await asyncio.wait_for(waiter, timeout=5)
    assert pool.size == 0


@pytest.mark.asyncio
async def test_wait_closed_wakes_on_disconnected_release():
    """Releasing a no-longer-connected connection must also wake wait_closed()."""
    pool = await asyncmy.create_pool(minsize=0, maxsize=4, autocommit=True, **connection_kwargs)
    conn = await pool.acquire()
    conn.close()

    pool.close()
    waiter = asyncio.create_task(pool.wait_closed())
    await asyncio.sleep(0.1)
    assert not waiter.done()

    await pool.release(conn)
    await asyncio.wait_for(waiter, timeout=5)
    assert pool.size == 0
