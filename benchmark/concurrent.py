"""
Benchmark 2: Concurrent Queries

Tests the efficiency of running multiple queries concurrently.
This is where async libraries shine - they can interleave I/O operations.

Synchronous libraries are not included as they cannot execute truly concurrent queries
without threads/processes.
"""
import asyncio
import time

import aiomysql
import asyncmy

from benchmark import best_result, connection_kwargs, CONCURRENT_COUNT


async def test_asyncmy(num_queries=CONCURRENT_COUNT):
    """Run concurrent queries with asyncmy (each query gets its own connection)"""
    async def single_query(query_id):
        conn = await asyncmy.connect(**connection_kwargs)
        try:
            async with conn.cursor() as cur:
                user_id = query_id % 10000
                await cur.execute(
                    "SELECT * FROM benchmark_data WHERE user_id = %s LIMIT 10",
                    (user_id,)
                )
                return await cur.fetchall()
        finally:
            await conn.ensure_closed()

    start = time.time()
    tasks = [single_query(i) for i in range(num_queries)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    return elapsed, len(results)


async def test_aiomysql(num_queries=CONCURRENT_COUNT):
    """Run concurrent queries with aiomysql (each query gets its own connection)"""
    async def single_query(query_id):
        conn = await aiomysql.connect(**connection_kwargs)
        try:
            async with conn.cursor() as cur:
                user_id = query_id % 10000
                await cur.execute(
                    "SELECT * FROM benchmark_data WHERE user_id = %s LIMIT 10",
                    (user_id,)
                )
                return await cur.fetchall()
        finally:
            conn.close()

    start = time.time()
    tasks = [single_query(i) for i in range(num_queries)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    return elapsed, len(results)


def run_benchmark():
    """Run the concurrent queries benchmark"""
    print("\n" + "="*60)
    print(f"Benchmark 2: Concurrent Queries ({CONCURRENT_COUNT} queries)")
    print("="*60)
    print("Note: Only async libraries tested (sync libs can't do this efficiently)")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    results = {}

    print("\nTesting asyncmy...")
    elapsed, count = best_result(lambda: loop.run_until_complete(test_asyncmy()))
    results['asyncmy'] = elapsed
    print(f"  Time: {elapsed:.3f}s, Queries: {count}")
    print(f"  Throughput: {count/elapsed:.0f} queries/sec")

    print("\nTesting aiomysql...")
    elapsed, count = best_result(lambda: loop.run_until_complete(test_aiomysql()))
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
