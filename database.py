import mysql.connector
import config
import os

def get_db_connection():
    connection = mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )
    return connection
def init_db():
    with open('schema.sql', 'r') as f:
        schema_sql = f.read()
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(schema_sql)
    connection.commit()
    cursor.close()
    connection.close()