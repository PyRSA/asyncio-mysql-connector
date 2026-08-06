"""
New benchmark suite for asyncmy - focused on realistic scenarios.

This benchmark suite tests:
1. Large result set fetching (data processing efficiency)
2. Concurrent queries (async advantage)
3. Connection pool performance
4. Batch operations (bulk inserts/updates)
5. Mixed workload scenarios

All tests use realistic patterns, not artificial loops.
"""
import os

# Database connection configuration
connection_kwargs = dict(
    host=os.getenv("MYSQL_HOST") or "localhost",
    port=int(os.getenv("MYSQL_PORT") or 3306),
    user=os.getenv("MYSQL_USER") or "root",
    password=os.getenv("MYSQL_PASS") or "123456",
    db="test",  # aiomysql uses 'db' instead of 'database'
    autocommit=True,
)

# Test data configuration
ROW_COUNT = 100000  # Total rows for testing
BATCH_SIZE = 10000  # Batch size for operations
CONCURRENT_COUNT = 50  # Number of concurrent operations (limited by MySQL max_connections)

# Measurement configuration
WARMUP_RUNS = 1  # Runs discarded before measuring (JIT caches, buffer pool, auth cache)
MEASURED_RUNS = 3  # Measured runs; the fastest one is reported


def best_result(fn, warmup=WARMUP_RUNS, runs=MEASURED_RUNS):
    """Run `fn` with warmup, then return its best (fastest) result.

    `fn` must return either an elapsed float or a tuple whose first item is
    the elapsed time.
    """
    for _ in range(warmup):
        fn()
    results = [fn() for _ in range(runs)]
    if isinstance(results[0], tuple):
        return min(results, key=lambda r: r[0])
    return min(results)
