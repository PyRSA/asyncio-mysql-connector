"""
Benchmark 4: Batch Insert

Tests the efficiency of bulk insert operations using executemany.
"""
import asyncio
import time

import aiomysql
import asyncmy
import MySQLdb
import pymysql

from benchmark import connection_kwargs, BATCH_SIZE


def generate_test_data(count=BATCH_SIZE):
    """Generate test data for batch insert"""
    return [
        (
            i + 200000,  # user_id (offset to avoid conflicts)
            f"batch_user_{i}",
            f"batch_{i}@example.com",
            "2024-02-01 00:00:00",
            "2024-02-01 00:00:00",
            round(i * 1.23, 2),
            1,
            f"Batch test data {i}",
        )
        for i in range(count)
    ]


async def test_asyncmy(data):
    """Batch insert with asyncmy"""
    conn = await asyncmy.connect(**connection_kwargs)
    async with conn.cursor() as cur:
        # Clean up before test
        await cur.execute("DELETE FROM benchmark_data WHERE user_id >= 200000")

        start = time.time()
        await cur.executemany(
            """INSERT INTO benchmark_data
               (user_id, username, email, created_at, updated_at, score, is_active, data)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            data
        )
        elapsed = time.time() - start

    await conn.ensure_closed()
    return elapsed


async def test_aiomysql(data):
    """Batch insert with aiomysql"""
    conn = await aiomysql.connect(**connection_kwargs)
    async with conn.cursor() as cur:
        # Clean up before test
        await cur.execute("DELETE FROM benchmark_data WHERE user_id >= 200000")

        start = time.time()
        await cur.executemany(
            """INSERT INTO benchmark_data
               (user_id, username, email, created_at, updated_at, score, is_active, data)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            data
        )
        elapsed = time.time() - start

    conn.close()
    return elapsed


def test_mysqlclient(data):
    """Batch insert with mysqlclient"""
    # Filter out None values for mysqlclient
    kwargs = {k: v for k, v in connection_kwargs.items() if v is not None}
    conn = MySQLdb.connect(**kwargs)
    cur = conn.cursor()

    # Clean up before test
    cur.execute("DELETE FROM benchmark_data WHERE user_id >= 200000")

    start = time.time()
    cur.executemany(
        """INSERT INTO benchmark_data
           (user_id, username, email, created_at, updated_at, score, is_active, data)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        data
    )
    elapsed = time.time() - start

    cur.close()
    conn.close()
    return elapsed


def test_pymysql(data):
    """Batch insert with pymysql"""
    conn = pymysql.connect(**connection_kwargs)
    cur = conn.cursor()

    # Clean up before test
    cur.execute("DELETE FROM benchmark_data WHERE user_id >= 200000")

    start = time.time()
    cur.executemany(
        """INSERT INTO benchmark_data
           (user_id, username, email, created_at, updated_at, score, is_active, data)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        data
    )
    elapsed = time.time() - start

    cur.close()
    conn.close()
    return elapsed


def run_benchmark():
    """Run the batch insert benchmark"""
    print("\n" + "="*60)
    print(f"Benchmark 4: Batch Insert ({BATCH_SIZE} rows)")
    print("="*60)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Generate test data once
    data = generate_test_data()

    results = {}

    print("\nTesting mysqlclient...")
    elapsed = test_mysqlclient(data)
    results['mysqlclient'] = elapsed
    print(f"  Time: {elapsed:.3f}s")
    print(f"  Throughput: {BATCH_SIZE/elapsed:.0f} rows/sec")

    print("\nTesting pymysql...")
    elapsed = test_pymysql(data)
    results['pymysql'] = elapsed
    print(f"  Time: {elapsed:.3f}s")
    print(f"  Throughput: {BATCH_SIZE/elapsed:.0f} rows/sec")

    print("\nTesting asyncmy...")
    elapsed = loop.run_until_complete(test_asyncmy(data))
    results['asyncmy'] = elapsed
    print(f"  Time: {elapsed:.3f}s")
    print(f"  Throughput: {BATCH_SIZE/elapsed:.0f} rows/sec")

    print("\nTesting aiomysql...")
    elapsed = loop.run_until_complete(test_aiomysql(data))
    results['aiomysql'] = elapsed
    print(f"  Time: {elapsed:.3f}s")
    print(f"  Throughput: {BATCH_SIZE/elapsed:.0f} rows/sec")

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
