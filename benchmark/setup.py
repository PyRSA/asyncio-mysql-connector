"""
Database setup and data generation for benchmarks.
"""
import MySQLdb
from benchmark import connection_kwargs, ROW_COUNT


def setup_database():
    """Create table and populate with test data."""
    # First connect without database to create it
    kwargs = connection_kwargs.copy()
    db_name = kwargs.pop('db')
    conn = MySQLdb.connect(**kwargs)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
    conn.close()

    # Now connect to the created database
    conn = MySQLdb.connect(**connection_kwargs)
    cur = conn.cursor()

    # Create table
    cur.execute("DROP TABLE IF EXISTS test.benchmark_data")
    cur.execute(
        """CREATE TABLE test.benchmark_data (
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
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
    )

    print(f"Populating table with {ROW_COUNT} rows...")

    # Prepare data
    data = []
    for i in range(ROW_COUNT):
        data.append((
            i % 10000,  # user_id (creates duplicates for realistic queries)
            f"user_{i}",
            f"user_{i}@example.com",
            "2024-01-01 00:00:00",
            "2024-01-01 00:00:00",
            round(i * 0.123, 2),
            1 if i % 3 == 0 else 0,
            f"Sample data for row {i}" * 5,  # ~100 bytes of text
        ))

    # Batch insert
    batch_size = 10000
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        cur.executemany(
            """INSERT INTO test.benchmark_data
               (user_id, username, email, created_at, updated_at, score, is_active, data)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            batch
        )
        print(f"  Inserted {min(i + batch_size, len(data))}/{len(data)} rows")

    conn.commit()
    cur.close()
    conn.close()

    print("Database setup complete!")


def cleanup_database():
    """Drop the test table."""
    conn = MySQLdb.connect(**connection_kwargs)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS test.benchmark_data")
    cur.close()
    conn.close()
    print("Database cleanup complete!")


if __name__ == "__main__":
    setup_database()
