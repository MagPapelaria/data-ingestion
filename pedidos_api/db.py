import os
import logging
import psycopg2
from psycopg2 import pool, extras
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

connection_pool = None

def inicializar_pool():
    global connection_pool
    if not connection_pool:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=int(os.getenv('DB_POOL_MIN', 1)),
            maxconn=int(os.getenv('DB_POOL_MAX', 5)),
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
        )
        logger.info('Pool de conexões criado com sucesso.')

def get_conn():
    if connection_pool is None:
        inicializar_pool()
    return connection_pool.getconn()

def put_conn(conn):
    if connection_pool:
        connection_pool.putconn(conn)

def inserir_pedidos_batch(conn, pedidos):
    try:
        with conn.cursor() as cur:
            extras.execute_values(
                cur,
                """
                INSERT INTO pedidos (numero_pedido, status, franqueado, fornecedor, data_pedido, mes_pedido, valor_pedido)
                VALUES %s
                ON CONFLICT (numero_pedido) DO NOTHING;
                """,
                pedidos
            )
            conn.commit()
            return cur.rowcount
    except Exception as e:
        logger.error(f'Erro ao inserir pedidos: {e}')
        conn.rollback()
        return 0

def atualizar_status_pedidos(conn, pedidos):
    try:
        with conn.cursor() as cur:
            for pedido in pedidos:
                cur.execute("""
                    UPDATE pedidos
                    SET status = %s
                    WHERE numero_pedido = %s;
                """, (pedido[1], str(pedido[0])))
        conn.commit()
        return len(pedidos)
    except Exception as e:
        logger.error(f"Erro ao atualizar status dos pedidos: {e}")
        conn.rollback()
        return 0
