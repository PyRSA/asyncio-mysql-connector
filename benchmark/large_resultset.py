"""
Benchmark 1: Large Result Set Fetching

Tests the efficiency of fetching and processing large result sets.
This measures:
- Packet reading efficiency (optimized with buffer management)
- Data parsing speed (optimized with datetime conversion)
- Memory efficiency
"""
import asyncio
import time

import aiomysql
import asyncmy
import MySQLdb
import pymysql

from benchmark import connection_kwargs


async def test_asyncmy(limit=50000):
    """Fetch large result set with asyncmy"""
    conn = await asyncmy.connect(**connection_kwargs)
    async with conn.cursor() as cur:
        start = time.time()
        await cur.execute(
            "SELECT * FROM benchmark_data WHERE is_active = 1 LIMIT %s",
            (limit,)
        )
        rows = await cur.fetchall()
        elapsed = time.time() - start

    await conn.ensure_closed()
    return elapsed, len(rows)


async def test_aiomysql(limit=50000):
    """Fetch large result set with aiomysql"""
    conn = await aiomysql.connect(**connection_kwargs)
    async with conn.cursor() as cur:
        start = time.time()
        await cur.execute(
            "SELECT * FROM benchmark_data WHERE is_active = 1 LIMIT %s",
            (limit,)
        )
        rows = await cur.fetchall()
        elapsed = time.time() - start

    conn.close()
    return elapsed, len(rows)


def test_mysqlclient(limit=50000):
    """Fetch large result set with mysqlclient"""
    conn = MySQLdb.connect(**connection_kwargs)
    cur = conn.cursor()

    start = time.time()
    cur.execute(
        "SELECT * FROM benchmark_data WHERE is_active = 1 LIMIT %s",
        (limit,)
    )
    rows = cur.fetchall()
    elapsed = time.time() - start

    cur.close()
    conn.close()
    return elapsed, len(rows)


def test_pymysql(limit=50000):
    """Fetch large result set with pymysql"""
    conn = pymysql.connect(**connection_kwargs)
    cur = conn.cursor()

    start = time.time()
    cur.execute(
        "SELECT * FROM benchmark_data WHERE is_active = 1 LIMIT %s",
        (limit,)
    )
    rows = cur.fetchall()
    elapsed = time.time() - start

    cur.close()
    conn.close()
    return elapsed, len(rows)


def run_benchmark():
    """Run the large result set benchmark"""
    print("\n" + "="*60)
    print("Benchmark 1: Large Result Set (fetch 50k rows)")
    print("="*60)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    results = {}

    print("\nTesting mysqlclient...")
    elapsed, count = test_mysqlclient()
    results['mysqlclient'] = elapsed
    print(f"  Time: {elapsed:.3f}s, Rows: {count}")

    print("\nTesting pymysql...")
    elapsed, count = test_pymysql()
    results['pymysql'] = elapsed
    print(f"  Time: {elapsed:.3f}s, Rows: {count}")

    print("\nTesting asyncmy...")
    elapsed, count = loop.run_until_complete(test_asyncmy())
    results['asyncmy'] = elapsed
    print(f"  Time: {elapsed:.3f}s, Rows: {count}")

    print("\nTesting aiomysql...")
    elapsed, count = loop.run_until_complete(test_aiomysql())
    results['aiomysql'] = elapsed
    print(f"  Time: {elapsed:.3f}s, Rows: {count}")

    # Print rankings
    print("\n" + "-"*60)
    print("Rankings:")
    sorted_results = sorted(results.items(), key=lambda x: x[1])
    for i, (name, time_val) in enumerate(sorted_results, 1):
        speedup = sorted_results[0][1] / time_val
        print(f"  {i}. {name:15s} {time_val:6.3f}s  ({speedup:.2f}x vs best)")

    return sorted_results


if __name__ == "__main__":
    run_benchmark()
