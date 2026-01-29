"""
Benchmark 3: Connection Pool Performance

Tests connection pool management under concurrent load.
This measures:
- Connection acquisition/release efficiency
- Connection reuse
- Concurrent access handling
"""
import asyncio
import time

import aiomysql
from asyncmy.pool import create_pool

from benchmark import connection_kwargs


POOL_SIZE_MIN = 5
POOL_SIZE_MAX = 20
NUM_QUERIES = 2000


async def test_asyncmy_pool():
    """Test connection pool with asyncmy"""
    pool = await create_pool(
        minsize=POOL_SIZE_MIN,
        maxsize=POOL_SIZE_MAX,
        **connection_kwargs
    )

    async def query_with_pool(query_id):
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                user_id = query_id % 10000
                await cur.execute(
                    "SELECT * FROM benchmark_data WHERE user_id = %s LIMIT 5",
                    (user_id,)
                )
                return await cur.fetchall()

    start = time.time()
    tasks = [query_with_pool(i) for i in range(NUM_QUERIES)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    pool.close()
    await pool.wait_closed()

    return elapsed, len(results)


async def test_aiomysql_pool():
    """Test connection pool with aiomysql"""
    pool = await aiomysql.create_pool(
        minsize=POOL_SIZE_MIN,
        maxsize=POOL_SIZE_MAX,
        **connection_kwargs
    )

    async def query_with_pool(query_id):
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                user_id = query_id % 10000
                await cur.execute(
                    "SELECT * FROM benchmark_data WHERE user_id = %s LIMIT 5",
                    (user_id,)
                )
                return await cur.fetchall()

    start = time.time()
    tasks = [query_with_pool(i) for i in range(NUM_QUERIES)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    pool.close()
    await pool.wait_closed()

    return elapsed, len(results)


def run_benchmark():
    """Run the connection pool benchmark"""
    print("\n" + "="*60)
    print(f"Benchmark 3: Connection Pool ({NUM_QUERIES} queries)")
    print(f"Pool size: {POOL_SIZE_MIN}-{POOL_SIZE_MAX} connections")
    print("="*60)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    results = {}

    print("\nTesting asyncmy pool...")
    elapsed, count = loop.run_until_complete(test_asyncmy_pool())
    results['asyncmy'] = elapsed
    print(f"  Time: {elapsed:.3f}s, Queries: {count}")
    print(f"  Throughput: {count/elapsed:.0f} queries/sec")

    print("\nTesting aiomysql pool...")
    elapsed, count = loop.run_until_complete(test_aiomysql_pool())
    results['aiomysql'] = elapsed
    print(f"  Time: {elapsed:.3f}s, Queries: {count}")
    print(f"  Throughput: {count/elapsed:.0f} queries/sec")

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
