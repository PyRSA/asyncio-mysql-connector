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
