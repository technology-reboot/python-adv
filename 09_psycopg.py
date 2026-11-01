"""Session 9 - Psycopg 3: raw SQL, parameters, transactions, pool. NEEDS Postgres.

Start Postgres once (needs Docker):
    docker run -d --name pg -e POSTGRES_USER=orders -e POSTGRES_PASSWORD=orders ^
        -e POSTGRES_DB=orders -p 5432:5432 postgres:16

Run (from the codealong folder):  python day2/09_psycopg.py
"""
import os  # read environment variables

import psycopg  # PostgreSQL driver (v3)
from psycopg.rows import dict_row  # row factory that returns dicts instead of tuples
from dotenv import load_dotenv  # loads variables from a .env file
from psycopg_pool import ConnectionPool  # reusable pool of connections

load_dotenv()  # searches upward from this file, so codealong/.env is found
DSN = os.environ["PG_DSN"]  # connection string from .env (KeyError if missing)

# SQL text (can't hold Python comments): drops and recreates a demo table with a CHECK rule price >= 0
SCHEMA = """
DROP TABLE IF EXISTS demo_items;
CREATE TABLE demo_items (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    stock INT NOT NULL
);
"""

if __name__ == "__main__":  # demo only when run directly
    # 1. connection as context manager = auto commit on success, rollback on error
    with psycopg.connect(DSN) as conn:  # open connection, commit when block ends
        conn.execute(SCHEMA)  # create the table

        # 2. ALWAYS pass values as parameters (%s), never f-strings -> no SQL injection
        conn.execute("INSERT INTO demo_items (name, price, stock) VALUES (%s, %s, %s)", ("Lamp", "17.70", 5))  # insert one row
        with conn.cursor() as cur:  # cursor needed for executemany
            cur.executemany(  # run the same statement for many rows
                "INSERT INTO demo_items (name, price, stock) VALUES (%s, %s, %s)",  # parameterised SQL
                [("Pen", "2.50", 100), ("Desk", "199.99", 2)],  # one tuple of values per row
            )

    # 3. rows as dicts
    with psycopg.connect(DSN, row_factory=dict_row) as conn:  # rows come back as dicts
        for row in conn.execute("SELECT * FROM demo_items WHERE price < %s ORDER BY id", (50,)):  # cheap items only
            print(row)  # e.g. {'id': 1, 'name': 'Lamp', ...}

    # 4. transaction: both updates happen or neither does
    try:
        with psycopg.connect(DSN) as conn:  # one transaction for the whole block"
            conn.execute("UPDATE demo_items SET stock = stock - 1 WHERE name = %s", ("Lamp",))  # succeeds
            conn.execute("UPDATE demo_items SET price = -1 WHERE name = %s", ("Pen",))  # violates CHECK
    except psycopg.errors.CheckViolation:  # database rejected the negative price
        print("rolled back - Lamp stock is unchanged")  # the first update was undone too
    with psycopg.connect(DSN) as conn:  # fresh connection to verify
        print("Lamp stock:", conn.execute("SELECT stock FROM demo_items WHERE name='Lamp'").fetchone()[0])  # still 5

    # 5. the classic injection bug, shown safely
    evil = "x' OR '1'='1"  # malicious input
    
    with psycopg.connect(DSN) as conn:
        unsafe = conn.execute(f"SELECT count(*) FROM demo_items WHERE name = '{evil}'").fetchone()[0]  # input becomes SQL -> matches all rows
        safe = conn.execute("SELECT count(*) FROM demo_items WHERE name = %s", (evil,)).fetchone()[0]  # input treated as plain data -> 0 rows
        print(f"f-string matched {unsafe} rows (BAD), parameterised matched {safe} rows (GOOD)")  # compare results

    # 6. connection pool: reuse connections instead of reconnecting for every request
    with ConnectionPool(DSN, min_size=1, max_size=4) as pool:  # keep 1-4 open connections
        with pool.connection() as conn:  # borrow one, returned automatically
            print("pooled count:", conn.execute("SELECT count(*) FROM demo_items").fetchone()[0])  # query via pooled connection

    # 7. COPY: fastest way to bulk load / export rows (much quicker than many INSERTs)
    with psycopg.connect(DSN) as conn:  # commit when block ends
        with conn.cursor() as cur:  # copy is a cursor method
            with cur.copy("COPY demo_items (name, price, stock) FROM STDIN") as copy:  # stream rows into the table
                copy.write_row(("Mug", "6.25", 40))  # one row per call, values converted for you
                for i in range(3):  # any iterable of rows works
                    copy.write_row((f"Bulk{i}", "1.00", i))  # more rows, same single COPY
            print("loaded rows, table now has", cur.execute("SELECT count(*) FROM demo_items").fetchone()[0])  # verify

            with cur.copy("COPY (SELECT name, price FROM demo_items ORDER BY id) TO STDOUT") as copy:  # stream rows out
                for name, price in copy.rows():  # each row is parsed back into a tuple of text values
                    print("exported:", name, price)  # values arrive as strings unless you call copy.set_types()
