import sqlite3
from pathlib import Path


def create_demo(path):
    path = Path(path)
    if path.exists():
        raise FileExistsError('Refusing to overwrite an existing database')
    with sqlite3.connect(path) as conn:
        conn.executescript('''
        CREATE TABLE customers (id INTEGER PRIMARY KEY, region TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, status TEXT);
        INSERT INTO customers VALUES (1,'West'),(2,'East'),(3,'West');
        INSERT INTO orders VALUES (1,1,100,'paid'),(2,2,80,'paid'),
                                  (3,1,50,'refunded'),(4,3,120,'paid');
        ''')
