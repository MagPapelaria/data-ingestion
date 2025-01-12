import psycopg2
from dotenv import load_dotenv
import os
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def conectar_banco():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"), 
            user=os.getenv("DB_USER"), 
            password=os.getenv("DB_PASSWORD"),  
            host=os.getenv("DB_HOST"),  
            port=os.getenv("DB_PORT")
        )
        logging.info("Conexão com o banco de dados bem-sucedida.")
        return conn
    except Exception as e:
        logging.exception("Erro ao conectar ao banco de dados.")
        return None

def verificar_pedido_existente(conn, numero_pedido):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM pedidos WHERE numero_pedido = %s::VARCHAR", (str(numero_pedido),))
        existe = cursor.fetchone()
        cursor.close()
        return existe is not None
    except Exception as e:
        logging.exception(f"Erro ao verificar se o pedido {numero_pedido} já existe.")
        return False

def inserir_pedidos_no_bd(pedidos):
    conn = conectar_banco()
    if conn is not None:
        try:
            cursor = conn.cursor()
            pedidos_adicionados = []

            for pedido in pedidos:
                if not verificar_pedido_existente(conn, pedido['número_do_pedido']):
                    cursor.execute(""" 
                        INSERT INTO pedidos (numero_pedido, status, franqueado, fornecedor, data_pedido)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (pedido['número_do_pedido'], pedido['status'], pedido['franqueado'], pedido['fornecedor'], pedido['data_do_pedido']))
                    pedidos_adicionados.append(str(pedido['número_do_pedido']))

            conn.commit()
            cursor.close()
            conn.close()

            if pedidos_adicionados:
                logging.info(f"Pedidos adicionados: {', '.join(pedidos_adicionados)}")
            else:
                logging.info("Nenhum pedido novo foi adicionado.")
        except Exception as e:
            logging.exception("Erro ao inserir pedidos no banco de dados.")
    else:
        logging.error("Falha na conexão com o banco.")

def load_dados(pedidos_limpos):
    logging.info("Iniciando o carregamento dos dados no banco de dados.")
    inserir_pedidos_no_bd(pedidos_limpos)
