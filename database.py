import os

import mysql.connector

import config

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')


def get_db_connection():
    return mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
    )


def init_db():
    """Create the database and tables from schema.sql.

    Connects without choosing a database first, so this also works on a fresh
    MySQL install where the job_tracker database doesn't exist yet.
    """
    with open(SCHEMA_PATH) as f:
        schema_sql = f.read()
    connection = mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
    )
    cursor = connection.cursor()
    try:
        # Run one statement at a time (skipping blank pieces).
        for statement in schema_sql.split(';'):
            if statement.strip():
                cursor.execute(statement)
        connection.commit()
    finally:
        cursor.close()
        connection.close()
