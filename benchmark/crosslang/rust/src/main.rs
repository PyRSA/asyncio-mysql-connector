use mysql_async::prelude::*;
use std::time::Instant;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let url = "mysql://root:123456@127.0.0.1:3306/test?pool_min=10&pool_max=10";
    let pool = mysql_async::Pool::new(url);

    // --- large result set scan, warmup + best of 5 ---
    let mut conn = pool.get_conn().await?;
    let mut best = f64::MAX;
    for iter in 0..6 {
        let start = Instant::now();
        let rows: Vec<(
            i64, i64, i64, f64, String, String, String,
            time::PrimitiveDateTime, time::Date, time::Duration,
        )> = conn.query("SELECT * FROM test.bench").await?;
        let el = start.elapsed().as_secs_f64();
        assert_eq!(rows.len(), 50000);
        if iter > 0 && el < best { best = el; }
    }
    println!("rust_select_all_mixed_50k\t{:.4}", best);
    drop(conn);

    // --- pool concurrency: 20 tasks x 200 point queries, acquire per query ---
    let mut best2 = f64::MAX;
    for iter in 0..4 {
        let start = Instant::now();
        let mut handles = vec![];
        for _ in 0..20 {
            let pool = pool.clone();
            handles.push(tokio::spawn(async move {
                for _ in 0..200 {
                    let mut c = pool.get_conn().await.unwrap();
                    let _v: Option<i64> = c
                        .exec_first("SELECT a FROM test.bench WHERE id=?", (1,))
                        .await
                        .unwrap();
                }
            }));
        }
        for h in handles { h.await?; }
        let el = start.elapsed().as_secs_f64();
        if iter > 0 && el < best2 { best2 = el; }
    }
    println!("rust_pool_20x200\t{:.4}", best2);

    pool.disconnect().await?;
    Ok(())
}
