import os
import logging
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

connection_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=int(os.getenv('DB_POOL_MIN', 1)),
    maxconn=int(os.getenv('DB_POOL_MAX', 5)),
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST'),
    port=os.getenv('DB_PORT'),
)

def get_conn():
    try:
        return connection_pool.getconn()
    except Exception as e:
        logging.error(f"Erro ao obter conexão: {e}")
        return None

def put_conn(conn):
    try:
        connection_pool.putconn(conn)
    except Exception as e:
        logging.warning(f"Erro ao devolver conexão: {e}")
