# Cross-language benchmark: asyncmy vs native Go/Rust drivers

Compares asyncmy against the mainstream native MySQL drivers of Go and Rust on
identical data, identical queries, with full type materialization in every
language (ints, floats, strings, and real datetime/date/duration objects — no
scanning into raw strings).

## Results

Apple M4 Max, MySQL 9.7.1 on localhost, warmup + best-of-N:

| Scenario | Go (go-sql-driver v1.10) | asyncmy (Python) | Rust (mysql_async 0.36) |
| --- | --- | --- | --- |
| 50k-row mixed-type full scan | **0.032s** | 0.036s | 0.048s |
| Pooled 20×200 point queries | 0.076s | 0.093s | **0.048s** |

Takeaways:

- On large scans asyncmy sits between the native drivers: ~12% behind
  go-sql-driver and ~25% **ahead** of mysql_async. The parsing path is C in all
  three; the remaining gap vs Go is the cost of materializing PyObjects.
- On point-query throughput Go and Rust benefit from prepared statements +
  the binary protocol (statement cache, no escaping, no text parsing), which
  asyncmy's text-protocol path doesn't use yet — that is a protocol
  difference more than a language difference.

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
