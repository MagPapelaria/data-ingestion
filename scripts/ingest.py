import requests
import psycopg2
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from psycopg2 import pool
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

# Configuração do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Lista dos meses
meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# Função para configurar o pool de conexões
def conectar_banco():
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            1, 20,  # Mínimo de 1 e máximo de 20 conexões
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
        )
        conn = connection_pool.getconn()
        logging.info('Conexão com banco de dados feita com sucesso!')
        return conn
    except Exception as e:
        logging.error(f'Erro ao conectar ao banco: {e}')
        return None

# Função para inserir os pedidos em batch no banco de dados
def inserir_pedidos_batch(conn, pedidos):
    try:
        with conn.cursor() as cursor:
            query = """
            INSERT INTO pedidos (numero_pedido, status, franqueado, fornecedor, data_pedido, mes_pedido, valor_pedido)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (numero_pedido) DO NOTHING;
            """
            cursor.executemany(query, pedidos)
        conn.commit()
        logging.info(f'{len(pedidos)} pedidos inseridos com sucesso!')
    except Exception as e:
        logging.error(f'Erro ao inserir pedidos em batch: {e}', exc_info=True)

# Função principal para buscar e processar pedidos
def processar_pedidos():
    url = 'https://app.centraldofranqueado.com.br/api/v2/pedidos/'
    headers = {'x-api-key': os.getenv('API_KEY')}
    
    # Fornece a data para API
    params = {'periodo': "2025-02-10"}

    # Configuração de retry para a requisição HTTP
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)

    # Usando requests.Session() para reutilizar conexões
    with requests.Session() as session:
        session.mount("https://", adapter)

        try:
            response = session.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                try:
                    dados_pedidos = response.json()
                    if not isinstance(dados_pedidos, list):
                        logging.error("A resposta da API não é uma lista de pedidos.")
                        return
                except ValueError:
                    logging.error("Erro ao decodificar a resposta JSON da API.")
                    return

                conn = conectar_banco()
                if conn:
                    pedidos_para_inserir = []
                    for pedido in dados_pedidos:
                        try:
                            numero_pedido = pedido['codigo']
                            status = pedido['situacao']['descricao']
                            franqueado = pedido['franqueado']['nome']
                            fornecedor = pedido['fornecedor']['nome']
                            data_pedido = datetime.strptime(pedido['dataCriacao'], '%Y-%m-%dT%H:%M:%S.%fZ')
                            
                            # Extrair o mês e obter o nome do mês
                            mes_pedido = meses[data_pedido.month - 1]
                            
                            valor_pedido = sum(item['quantidadeProdutos'] * item['valorUnitario'] for item in pedido['itensPedido'])
                            pedidos_para_inserir.append((numero_pedido, status, franqueado, fornecedor, data_pedido, mes_pedido, valor_pedido))
                        except KeyError as e:
                            logging.error(f"Erro ao processar pedido: campo {e} não encontrado.")
                            continue

                    if pedidos_para_inserir:
                        inserir_pedidos_batch(conn, pedidos_para_inserir)
                    conn.close()
                    logging.info('Conexão com banco de dados fechada.')
                else:
                    logging.error('Não foi possível conectar ao banco.')
            else:
                logging.error(f"Erro na requisição: {response.status_code}")
                logging.error(response.text)
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro na requisição HTTP: {e}")

# Executar a função principal
if __name__ == "__main__":
    processar_pedidos()
