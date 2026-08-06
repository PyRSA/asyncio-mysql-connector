# Cross-language benchmark: asyncmy vs native Go/Rust drivers

Compares asyncmy against the mainstream native MySQL drivers of Go and Rust on
identical data, identical queries, with full type materialization in every
language (ints, floats, strings, and real datetime/date/duration objects — no
scanning into raw strings).

## Results

Apple M4 Max, MySQL 9.7.1 on localhost, warmup + best-of-N:

| Scenario | Go (go-sql-driver v1.10) | asyncmy text | asyncmy binary (`conn.prepare`) | Rust (mysql_async 0.36) |
| --- | --- | --- | --- | --- |
| 50k-row mixed-type full scan | 0.032s | 0.037s | **0.023s** | 0.048s |
| Pooled 20×200 point queries | 0.076s | 0.093s (0.067s with uvloop) | 0.084s (**0.062s** with uvloop) | **0.048s** |

With `stmt_cache_size` set, plain `cursor.execute("%s")` code gets the binary
path transparently: 0.025s scans and 0.064s pooled point queries (uvloop)
with zero code changes.

Takeaways:

- With the binary protocol (server-side prepared statements, added in 0.2.13)
  asyncmy's large scan is the **fastest of the three languages** — integers
  arrive as little-endian bytes and datetimes as packed fields, so text
  parsing disappears entirely.
- Even the text-protocol scan sits between the native drivers: ~12% behind
  go-sql-driver and ~25% ahead of mysql_async.
- On point-query throughput Rust still leads; the remaining asyncmy gap is
  event-loop scheduling cost (uvloop closes much of it), not protocol parsing.

## Fairness notes

- All three scan the same `test.bench` table (10 columns: int/bigint/double/
  decimal/varchar×2/datetime(6)/date/time) created by `python_bench.py`.
- DECIMAL and TIME are scanned as `String` in Go/Rust; Python constructs
  `Decimal`/`timedelta` objects (slightly more work on the Python side).
- Go goes through `database/sql`; the raw driver would be marginally faster.
- Rust uses `mysql_async` (the mainstream async driver, same category as
  asyncmy); `sqlx` and the sync `mysql` crate were not measured.
- Point queries: Go/Rust use prepared statements (binary protocol); asyncmy
  uses client-side interpolation (text protocol).

## Reproduce

```bash
# 1. create data + run the Python side (needs a local MySQL, root/123456)
python python_bench.py

# 2. Go
cd go && go run .

# 3. Rust
cd rust && cargo run --release
```
