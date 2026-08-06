# asyncmy Benchmark Suite

Comprehensive performance benchmarks for `asyncmy`, comparing against `mysqlclient`, `pymysql`, and `aiomysql`.

## Test Environment

- **CPU:** Apple Mac Studio (M4 Max)
- **Memory:** 64GB
- **Python:** 3.14
- **MySQL:** 9.7.1 (localhost)
- **Test Data:** 100,000 rows with realistic schema

## Methodology

Every test runs a warmup pass first (to populate the MySQL buffer pool, auth
cache, and driver-internal caches), then reports the **best of 3 measured
runs**. This is handled by `best_result()` in `benchmark/__init__.py`.

## Performance Summary

| Test                                     | Winner         | asyncmy Rank | Notes                                        |
| ---------------------------------------- | -------------- | ------------ | -------------------------------------------- |
| **Large Result Set** (33k rows)          | 🏆 **asyncmy** | **#1/4**     | 2.1x faster than mysqlclient (a C sync lib)  |
| **Concurrent Queries** (50 connections)  | 🏆 **asyncmy** | **#1/2**     | 1.6x faster than aiomysql                    |
| **Connection Pool** (2k queries)         | 🏆 **asyncmy** | **#1/2**     | 2x aiomysql's throughput                     |
| **Batch Insert** (10k rows)              | 🏆 **asyncmy** | **#1/4**     | ~91k rows/sec, fastest of all four           |

## Key Insights

- ✅ **Large Result Set**: asyncmy is now the fastest driver, period — 2.1x faster
  than mysqlclient and 5.2x faster than aiomysql/pymysql
- ✅ **Connection Pool**: ~17,000 queries/sec, double aiomysql's throughput
- ✅ **Concurrent Queries**: fastest connection setup + query round-trip
- ✅ **Batch Insert**: fastest `executemany()` of all four drivers

## Recent Optimizations

The protocol core was rebuilt around direct C-level parsing:

1. **Buffered packet reading** — packets are consumed from a receive buffer
   filled by large socket reads, instead of two `await`s per packet. A 33k-row
   result set now costs a handful of event-loop round-trips instead of ~66,000.
2. **Bulk row parsing** — all complete row packets sitting in the buffer are
   parsed in one C loop (`parse_rows_from_buffer`), creating no intermediate
   packet objects.
3. **Pointer-based protocol reads** — integers and length-encoded values are
   read directly from raw memory; no `struct.unpack` calls remain on the hot path.
4. **Direct cell decoding** — string cells decode straight from the receive
   buffer via `PyUnicode_DecodeUTF8`/`PyUnicode_DecodeASCII`; rows are built
   with `PyTuple_New`/`PyTuple_SET_ITEM`.
5. **Zero-decode numeric & temporal columns** — `int`/`float` parse directly
   from bytes; DATETIME/DATE/TIME values are parsed byte-by-byte in C and
   constructed through the CPython datetime C-API (no regex, no str detour).
6. **Escape fast path** — strings/bytes without special characters skip the
   translation table entirely.
7. **Leaner cursors** — `fetchone/fetchmany/fetchall` no longer allocate an
   `asyncio.Future` per call.
8. **Compiler tuning** — `-O3` with `cdivision`, `initializedcheck=False`, and
   bounds-check-free parsing code.

Measured impact (driver-level micro-benchmarks, 50k rows, best-of-N):

| Workload                    | Before  | After   | Speedup |
| --------------------------- | ------- | ------- | ------- |
| Mixed-type full scan        | 221.5ms | 32.5ms  | 6.8x    |
| Integer columns scan        | 114.2ms | 19.4ms  | 5.9x    |
| String columns scan         | 88.1ms  | 11.7ms  | 7.5x    |
| Datetime columns scan       | 244.6ms | 16.1ms  | 15.2x   |
| SSCursor (unbuffered) scan  | 111.0ms | 39.5ms  | 2.8x    |
| Pooled small queries        | 229.0ms | 185.4ms | 1.24x   |

## Test Scenarios

### 1. Large Result Set (`large_resultset.py`)

Tests the efficiency of fetching and processing large datasets in a single query.

**What it measures:**

- Packet reading efficiency (buffered bulk reads)
- Data parsing speed (C-level row/datetime parsing)
- Memory efficiency

**Test:** Fetch ~33,000 rows with all column types (int, varchar, datetime, decimal, text)

**Results (typical):**

```text
1. asyncmy          0.031s  (1.00x vs best)
2. mysqlclient      0.066s  (0.47x vs best)
3. pymysql          0.155s  (0.20x vs best)
4. aiomysql         0.161s  (0.19x vs best)
```

### 2. Concurrent Queries (`concurrent.py`)

Tests async libraries' ability to run multiple queries concurrently.

**What it measures:**

- Connection handling under concurrent load
- Async I/O efficiency
- Query interleaving capabilities

**Test:** Execute 50 concurrent SELECT queries (each query gets its own connection)

**Results (typical):**

```text
1. asyncmy          0.006s  (~8,600 queries/sec)
2. aiomysql         0.009s  (~5,500 queries/sec)
```

**Note:** Synchronous libraries (mysqlclient, pymysql) cannot efficiently handle this scenario without threads.

### 3. Connection Pool (`pool.py`)

Tests connection pool performance with concurrent query load.

**What it measures:**

- Connection acquisition/release efficiency
- Connection reuse patterns
- Pool management under concurrent access

**Test:** Execute 2,000 queries using a connection pool (5-20 connections)

**Results (typical):**

```text
1. asyncmy          0.117s  (1.00x vs best) ⭐ WINNER - ~17,000 queries/sec
2. aiomysql         0.235s  (0.50x vs best) - ~8,500 queries/sec
```

**Insight:** asyncmy's connection pool consistently delivers **~2x aiomysql's throughput**.

### 4. Batch Insert (`batch_insert.py`)

Tests bulk insert performance using `executemany()`.

**What it measures:**

- Batch operation efficiency
- SQL statement building
- Network/protocol overhead

**Test:** Insert 10,000 rows using `executemany()`

**Results (typical):**

```text
1. asyncmy          0.110s  (~91,000 rows/sec)
2. pymysql          0.128s  (~78,000 rows/sec)
3. aiomysql         0.129s  (~77,000 rows/sec)
4. mysqlclient      0.153s  (~65,000 rows/sec)
```

**Note:** This workload is largely bound by the MySQL server; rankings between
the runner-ups can shift between runs, but asyncmy has been consistently fastest.

## Running the Benchmarks

### Prerequisites

1. MySQL server running and accessible
2. Python ≥ 3.9 with required packages installed

### Setup

```bash
# Set database connection parameters
export MYSQL_HOST=localhost
export MYSQL_USER=root
export MYSQL_PASS=password

# Optional: specify port (default: 3306)
export MYSQL_PORT=3306
```

### Run All Benchmarks

```bash
# Run complete benchmark suite
python -m benchmark.run_all
```

This will:

1. Create test database and populate with 100,000 rows
2. Run all 4 benchmark tests (warmup + best-of-3 each)
3. Generate a summary report
4. Clean up test data

### Run Individual Tests

```bash
# Test large result set performance
python -m benchmark.large_resultset

# Test concurrent query performance
python -m benchmark.concurrent

# Test connection pool performance
python -m benchmark.pool

# Test batch insert performance
python -m benchmark.batch_insert
```

## Test Data Schema

The benchmark uses a realistic table schema:

```sql
CREATE TABLE benchmark_data (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    score DECIMAL(10,2) NOT NULL,
    is_active TINYINT NOT NULL,
    data TEXT,
    PRIMARY KEY (id),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## Benchmark Configuration

Default settings (can be modified in `benchmark/__init__.py`):

```python
ROW_COUNT = 100000          # Total test rows
BATCH_SIZE = 10000          # Batch operation size
CONCURRENT_COUNT = 50       # Number of concurrent operations
WARMUP_RUNS = 1             # Discarded warmup runs per test
MEASURED_RUNS = 3           # Measured runs; fastest is reported
```

## Performance Tips

Based on benchmark results, asyncmy performs best when:

1. **Fetching large result sets** — the C-level bulk row parser makes reads the
   fastest of any Python MySQL driver tested, sync or async
2. **Processing datetime-heavy data** — temporal columns parse in C directly
   from the wire bytes
3. **Using connection pools** — ~2x aiomysql's pooled throughput
4. **Handling concurrent workloads** — async architecture plus cheap per-query
   overhead

## Comparison with Other Libraries

### vs mysqlclient (sync, C extension)

- ✅ **2.1x faster** for large result sets
- ✅ **Better** for concurrent workloads (asyncmy uses async I/O)
- ✅ **Faster** batch inserts

### vs pymysql (sync, pure Python)

- ✅ **5x faster** for large result sets
- ✅ **Much better** for concurrent workloads
- ✅ **Better** connection pool (asyncmy has native pool)

### vs aiomysql (async)

- ✅ **5.2x faster** for large result sets (C-level bulk parsing)
- ✅ **2x** connection pool throughput
- ✅ **1.6x faster** concurrent queries
- ✅ **Faster** batch inserts

## Contributing

To add new benchmarks:

1. Create a new file: `benchmark/your_benchmark.py`
2. Implement test functions following the existing pattern
3. Add a `run_benchmark()` function that returns sorted results
4. Import and call your test in `benchmark/run_all.py`

Example template:

```python
"""
Benchmark: Your Test Name

Description of what this test measures.
"""
import asyncio
import time
from benchmark import best_result, connection_kwargs

async def test_asyncmy():
    # Your test implementation
    start = time.time()
    # ... test code ...
    elapsed = time.time() - start
    return elapsed

def run_benchmark():
    results = {}
    loop = asyncio.new_event_loop()

    # Run tests and collect results (warmup + best-of-3)
    results['asyncmy'] = best_result(lambda: loop.run_until_complete(test_asyncmy()))

    # Return sorted results
    return sorted(results.items(), key=lambda x: x[1])
```

## License

[Apache-2.0](../LICENSE)
