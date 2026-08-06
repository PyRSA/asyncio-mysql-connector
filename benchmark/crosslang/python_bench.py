import asyncio, datetime, time
import asyncmy

KW = dict(host="127.0.0.1", port=3306, user="root", password="123456")

async def main():
    conn = await asyncmy.connect(**KW)
    async with conn.cursor() as cur:
        await cur.execute("CREATE DATABASE IF NOT EXISTS test")
        await cur.execute("DROP TABLE IF EXISTS test.bench")
        await cur.execute(
            "CREATE TABLE test.bench (id INT PRIMARY KEY AUTO_INCREMENT,"
            " a INT, b BIGINT, c DOUBLE, d DECIMAL(12,4), s1 VARCHAR(64),"
            " s2 VARCHAR(255), dt DATETIME(6), da DATE, tm TIME)")
        rows = [(i, i * 1000000007, i * 0.31415, "%d.%04d" % (i, i % 10000),
                 "user-name-%08d" % i, "payload-" + "z" * (i % 120),
                 datetime.datetime(2021, 3, 4, 5, 6, i % 60, i % 1000000),
                 datetime.date(2000 + i % 25, 1 + i % 12, 1 + i % 28),
                 datetime.timedelta(hours=i % 120, minutes=i % 60, seconds=i % 60))
                for i in range(50000)]
        await cur.executemany(
            "INSERT INTO test.bench (a,b,c,d,s1,s2,dt,da,tm) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", rows)
    await conn.commit()

    # large scan, warmup + best of 5
    async with conn.cursor() as cur:
        times = []
        for i in range(6):
            t0 = time.perf_counter()
            await cur.execute("SELECT * FROM test.bench")
            got = await cur.fetchall()
            el = time.perf_counter() - t0
            if i: times.append(el)
            assert len(got) == 50000
        print("py_select_all_mixed_50k\t%.4f" % min(times))

    # pool 20x200 point queries
    pool = await asyncmy.create_pool(minsize=10, maxsize=10, **KW)
    async def worker():
        for _ in range(200):
            async with pool.acquire() as c:
                async with c.cursor() as cu:
                    await cu.execute("SELECT a FROM test.bench WHERE id=%s", (1,))
                    await cu.fetchall()
    times = []
    for i in range(4):
        t0 = time.perf_counter()
        await asyncio.gather(*[worker() for _ in range(20)])
        el = time.perf_counter() - t0
        if i: times.append(el)
    print("py_pool_20x200\t%.4f" % min(times))
    pool.close(); await pool.wait_closed()
    await conn.ensure_closed()

asyncio.run(main())
