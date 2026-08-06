package main

import (
	"database/sql"
	"fmt"
	"sync"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

func main() {
	dsn := "root:123456@tcp(127.0.0.1:3306)/test?parseTime=true"
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		panic(err)
	}
	db.SetMaxOpenConns(10)
	defer db.Close()

	// --- large result set scan, best of 5 ---
	best := time.Duration(1 << 62)
	for iter := 0; iter < 6; iter++ { // first is warmup
		start := time.Now()
		rows, err := db.Query("SELECT * FROM test.bench")
		if err != nil {
			panic(err)
		}
		n := 0
		var (
			id, a   int64
			b       int64
			c       float64
			d       string
			s1, s2  string
			dt, da  time.Time
			tm      string
		)
		for rows.Next() {
			if err := rows.Scan(&id, &a, &b, &c, &d, &s1, &s2, &dt, &da, &tm); err != nil {
				panic(err)
			}
			n++
		}
		rows.Close()
		el := time.Since(start)
		if iter > 0 && el < best {
			best = el
		}
		if n != 50000 {
			panic(fmt.Sprintf("rows=%d", n))
		}
	}
	fmt.Printf("go_select_all_mixed_50k\t%.4f\n", best.Seconds())

	// --- pooled concurrency: 20 goroutines x 200 point queries ---
	best = time.Duration(1 << 62)
	for iter := 0; iter < 4; iter++ {
		start := time.Now()
		var wg sync.WaitGroup
		for w := 0; w < 20; w++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				var a int64
				for q := 0; q < 200; q++ {
					if err := db.QueryRow("SELECT a FROM test.bench WHERE id=?", 1).Scan(&a); err != nil {
						panic(err)
					}
				}
			}()
		}
		wg.Wait()
		el := time.Since(start)
		if iter > 0 && el < best {
			best = el
		}
	}
	fmt.Printf("go_pool_20x200\t%.4f\n", best.Seconds())
}
