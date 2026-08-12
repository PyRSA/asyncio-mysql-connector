# ChangeLog

## 0.2

### 0.2.14

- Set the PEP 249 module globals `apilevel`, `threadsafety` and `paramstyle`, and export the
  exception classes from `asyncmy` (#77).
- Expose the server's SQLSTATE on exceptions as `MySQLError.sqlstate`; `args` is unchanged (#138).
- Fix `ssl=True` silently connecting in plaintext: it now builds a default TLS context, and an
  ssl argument that is neither `True`, a dict, nor an `ssl.SSLContext` raises `ValueError`
  instead of disabling TLS (#90).
- `Connection.cursor()` is now awaitable, so aiomysql's `cur = await conn.cursor()` spelling
  works; `conn.cursor()` and `async with conn.cursor()` are unaffected (#145).
- Add `Gtid.__hash__` / `GtidSet.__hash__` — defining `__eq__` had made `Gtid` unhashable, which
  made `GtidSet` (and therefore GTID replication) unusable (#59).
- Add `connect(sock=...)`: speak MySQL over a socket the caller has already connected. Combined
  with `ssl` the TLS handshake runs before the MySQL handshake instead of being negotiated
  in-protocol, which is what connectors fronting the server with a TLS proxy need (#71).
- Mark the connection secure after the TLS handshake. `_secure` was only set for unix sockets, so
  `caching_sha2_password` full authentication over TLS took the RSA branch instead of sending the
  password in the clear, and the server rejected it with `1045 Access denied` (#117).

### 0.2.13

- Add server-side prepared statements (binary protocol): `stmt = await conn.prepare(sql)`,
  `await stmt.execute(args)`. Parameters are sent in binary form (no client-side escaping)
  and results are parsed from the binary protocol — no text parsing for numeric/temporal
  columns. Large scans are ~35% faster than the text protocol; on the cross-language
  benchmark asyncmy's binary scan is now the fastest, ahead of go-sql-driver and mysql_async.
- Add transparent statement cache: `connect(stmt_cache_size=N)` makes plain
  `cursor.execute("... %s ...", args)` run as cached server-side prepared statements
  (binary protocol) with silent text-protocol fallback for unpreparable queries.
  Opt-in because FLOAT columns return the exact stored value under the binary protocol.
- Replace StreamReader with a custom `asyncio.BufferedProtocol`: incoming bytes land
  directly in the parse buffer (zero-copy receive, no per-read Future round-trips).
- Cache prepared-statement column metadata: repeated executes skip re-parsing column
  definition packets entirely (C-level packet skipping).
- SSCursor now bulk-parses buffered rows (unbuffered scans ~10% faster on top of 0.2.12's 2.8x).
- DictCursor builds row dicts at C level.
- Fix `LOAD DATA LOCAL INFILE` sending (`await` on a non-coroutine) and add write backpressure.
- Build Linux aarch64 wheels.
- Negotiate `CLIENT_DEPRECATE_EOF`: one packet less per result set and per prepare
  (both MySQL 5.7.5+ and MariaDB support it; legacy EOF path kept for older servers).
- MariaDB: support `COM_STMT_BULK_EXECUTE` — `executemany` binds all rows in binary
  form in one round-trip when `stmt_cache_size` is enabled (automatic text fallback);
  also available explicitly via `stmt.execute_bulk(rows)`.
- Fix `conftest.py` ignoring a non-default `MYSQL_PORT`.

### 0.2.12

- Major performance improvement: buffered packet reading, C-level bulk row parsing,
  pointer-based protocol reads, direct cell decoding via CPython C-API, zero-decode
  numeric/temporal columns, escape fast path. Large result sets are 5-15x faster;
  asyncmy now ranks #1 in all benchmarks, details see [benchmark/README.md](benchmark/README.md).
- Fix `OKPacketWrapper.message` containing 2 stray bytes (read_struct position bug).
- Fix `LoadLocalPacketWrapper` missing attribute declarations (LOAD DATA LOCAL crash).
- Fix potential integer overflow of `rowcount`/`insert_id` on unbuffered cursors and Windows.
- Benchmark suite now uses warmup + best-of-3 methodology.
- Security: remove unsafe `escape_dict` — dict keys could reach SQL unescaped (CVE-2025-65896). (#134, #135, thanks @Cycloctane)
- Fix `AttributeError: 'Connection' object has no attribute 'ssl'` in `sha256_password` auth branch. (#147, #148, thanks @shychee)
- Support MySQL 8.0.19+ `INSERT ... AS alias ON DUPLICATE KEY UPDATE` syntax in `executemany`. (#116, #120, thanks @MarkReedZ)
- Pool closes idle/recycled connections with QUIT instead of aborting the TCP stream. (#112, #113, thanks @Cycloctane)
- Fix `OverflowError` when escaping ints outside the signed 64-bit range, e.g. unsigned BIGINT `2**64-1`. (#35, #127)
- Close connection when a query is cancelled mid-read to prevent stale results leaking into pooled reuse. (#107, #108)
- Use `setuptools` instead of deprecated `distutils` in build. (#106, thanks @tijuca)

### 0.2.11

- Fix `'Connection' object has no attribute '_auth_plugin_name'` (#86)

### 0.2.10

- Fix ssl context pass bool.
- Fix missing `*.whl` for Python 3.12 (#94)
- Fix SSL handshake error with MySQL server v8.0.34+. (#80)

### 0.2.9

- Added support for SSL context creation via `ssl` parameter using a dictionary containing `mysql_ssl_set` parameters. (
  #64)
- Fix bug with fallback encoder in the `escape_item()` function. (#65)

### 0.2.8

- Fix sudden loss of float precision. (#56)
- Fix pool `echo` parameter not apply to create connection. (#62)
- Fix replication reconnect.

### 0.2.7

- Fix `No module named 'asyncmy.connection'`.

### 0.2.6

- Fix raise_mysql_exception (#28)
- Implement `read_timeout` and remove `write_timeout` parameters (#44)

### 0.2.5

- Revert `TIME` return `datetime.time` object. (#37)

### 0.2.4

- Fix `escape_string` for enum type. (#30)
- `TIME` return `datetime.time` object.

### 0.2.3

- Fix `escape_sequence`. (#20)
- Fix `connection.autocommit`. (#21)
- Fix `_clear_result`. (#22)

### 0.2.2

- Fix bug. (#18)
- Fix replication error.

### 0.2.1

- Fix `binlogstream` await. (#12)
- Remove `loop` argument. (#15)
- Fix `unix_socket` connect. (#17)

### 0.2.0

- Fix `cursor.close`.

## 0.1

### 0.1.9

- Force int `pool_recycle`.
- Fix `echo` option.
- Fix bug replication and now don't need to connect manual.

### 0.1.8

- Fix pool recycle. (#4)
- Fix async `fetchone`, `fetchall`, and `fetchmany`. (#7)

### 0.1.7

- Fix negative pk. (#2)

### 0.1.6

- Bug fix.

### 0.1.5

- Remove `byte2int` and `int2byte`.
- Fix warning for sql_mode.

### 0.1.4

- Add replication support.

### 0.1.3

- Fix pool.

### 0.1.2

- Fix build error.

### 0.1.1

- Fix build error.

### 0.1.0

- Release first version.
