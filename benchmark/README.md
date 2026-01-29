# asyncmy Benchmark Suite

Comprehensive performance benchmarks for `asyncmy`, comparing against `mysqlclient`, `pymysql`, and `aiomysql`.

## Test Environment

- **CPU:** Apple Mac Studio (M4 Max)
- **Memory:** 64GB
- **Python:** 3.14
- **MySQL:** 9.6.0
- **Test Data:** 100,000 rows with realistic schema

## Performance Summary

| Test                                 | Winner         | asyncmy Rank | Notes                                 |
| ------------------------------------ | -------------- | ------------ | ------------------------------------- |
| **Large Result Set** (50k rows)      | mysqlclient    | #2/4         | ~0.090s - 2x faster than aiomysql     |
| **Concurrent Queries** (50 queries)  | Variable       | #1-2/2       | Very close to aiomysql                |
| **Connection Pool** (2k queries)     | 🏆 **asyncmy** | **#1/2**     | Consistently 22-28% faster            |
| **Batch Insert** (10k rows)          | Variable       | #1-4/4       | Results vary significantly            |

## Key Insights

- ✅ **Connection Pool**: asyncmy consistently shows 22-28% better throughput than aiomysql
- ✅ **Large Result Set**: asyncmy is 2x faster than pymysql/aiomysql, close to mysqlclient
- ⚡ **Concurrent Queries**: asyncmy and aiomysql are comparable (within margin of error)
- ⚡ **Batch Insert**: Results vary by run; all libraries perform similarly

## Recent Optimizations (v0.2.12)

Five major performance improvements were implemented:

1. **Buffer Management** - Eliminated redundant memory copies in packet reading (fast path optimization)
2. **DateTime Parsing** - Replaced regex with fast string slicing for datetime/date/time conversions
3. **Row Parsing** - Pre-allocated lists and C-level indexing replacing Python list.append()
4. **Protocol Parsing** - Inlined `read_length_coded_string` with fast path for common cases (length < 251)
5. **Batch Operations** - Pre-process values and use list accumulation + join for executemany

These optimizations resulted in:

- **asyncmy consistently leads in connection pool benchmarks** (22-28% faster)
- **Large result set parsing improved** - now 2x faster than aiomysql
- **Close to mysqlclient performance** in data-intensive workloads

## Test Scenarios

### 1. Large Result Set (`large_resultset.py`)

Tests the efficiency of fetching and processing large datasets in a single query.

**What it measures:**

- Packet reading efficiency (optimized buffer management)
- Data parsing speed (optimized datetime conversion)
- Memory efficiency

**Test:** Fetch 50,000 rows with all column types (int, varchar, datetime, decimal, text)

**Results (typical):**

```text
1. mysqlclient      0.085s  (1.00x vs best)
2. asyncmy          0.090s  (0.94x vs best)
3. pymysql          0.165s  (0.52x vs best)
4. aiomysql         0.170s  (0.50x vs best)
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
1. asyncmy/aiomysql  ~0.015s - Results vary, both libraries perform similarly
```

**Note:** Synchronous libraries (mysqlclient, pymysql) cannot efficiently handle this scenario without threads. The difference between asyncmy and aiomysql is within margin of error.

### 3. Connection Pool (`pool.py`)

Tests connection pool performance with concurrent query load.

**What it measures:**

- Connection acquisition/release efficiency
- Connection reuse patterns
- Pool management under concurrent access

**Test:** Execute 2,000 queries using a connection pool (5-20 connections)

**Results (typical):**

```text
1. asyncmy          ~0.190s  (1.00x vs best) ⭐ WINNER - ~10,500 queries/sec
2. aiomysql         ~0.240s  (0.78x vs best) - ~8,300 queries/sec
```

**Insight:** asyncmy's connection pool consistently shows **22-28% better throughput** than aiomysql across multiple runs.

### 4. Batch Insert (`batch_insert.py`)

Tests bulk insert performance using `executemany()`.

**What it measures:**

- Batch operation efficiency
- SQL statement building
- Network/protocol overhead

**Test:** Insert 10,000 rows using `executemany()`

**Results (variable):**

```text
Results vary significantly between runs. All libraries perform similarly,
with rankings changing between mysqlclient, pymysql, asyncmy, and aiomysql.
Typical throughput: 80,000-110,000 rows/sec for all libraries.
```

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
2. Run all 4 benchmark tests
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
ROW_COUNT = 100000           # Total test rows
BATCH_SIZE = 10000          # Batch operation size
CONCURRENT_COUNT = 50       # Number of concurrent operations
```

## Performance Tips

Based on benchmark results, asyncmy performs best when:

1. **Using connection pools** - asyncmy's pool implementation is highly optimized (22-28% faster than aiomysql)
2. **Fetching large result sets** - Use asyncmy for queries returning 1,000+ rows (2x faster than aiomysql)
3. **Processing datetime-heavy data** - Optimized datetime parsing provides significant gains
4. **Handling concurrent workloads** - Async architecture allows efficient I/O interleaving

## Comparison with Other Libraries

### vs mysqlclient (sync)

- ✅ **Competitive** for large result sets (only 5-10% slower)
- ✅ **Better** for concurrent workloads (asyncmy uses async I/O)
- ⚡ **Similar** for batch inserts (results vary)

### vs pymysql (sync)

- ✅ **2x faster** for large result sets
- ✅ **Much better** for concurrent workloads
- ✅ **Better** connection pool (asyncmy has native pool)

### vs aiomysql (async)

- ✅ **2x faster** for large result sets (optimized parsing)
- ✅ **22-28% faster** connection pool throughput (consistent)
- ⚡ **Comparable** for concurrent queries (within margin of error)
- ⚡ **Similar** for batch inserts (results vary)

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
from benchmark import connection_kwargs

async def test_asyncmy():
    # Your test implementation
    start = time.time()
    # ... test code ...
    elapsed = time.time() - start
    return elapsed

def run_benchmark():
    results = {}
    loop = asyncio.new_event_loop()

    # Run tests and collect results
    results['asyncmy'] = loop.run_until_complete(test_asyncmy())

    # Return sorted results
    return sorted(results.items(), key=lambda x: x[1])
```

## License

[Apache-2.0](../LICENSE)
