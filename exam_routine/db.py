import getpass
import os

import mysql.connector

import config


def get_connection(password=None, with_database=True):
    """Connect to MySQL using the values in config.py.
    If DB_PASSWORD in config.py is None, the password is asked in the terminal.
    The MYSQL_PASSWORD environment variable overrides config.py (used for testing).
    """
    if password is None:
        password = os.environ.get("MYSQL_PASSWORD", config.DB_PASSWORD)
    if password is None:
        password = getpass.getpass("MySQL password: ")
    kwargs = dict(host=config.DB_HOST, user=config.DB_USER, password=password)
    if with_database:
        kwargs["database"] = config.DB_NAME
    return mysql.connector.connect(**kwargs)


if __name__ == "__main__":
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = [t[0] for t in cur.fetchall()]
    print("Connected! Tables found:", len(tables))
    print(tables)
    conn.close()
