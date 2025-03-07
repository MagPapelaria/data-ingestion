import requests
import psycopg2
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from psycopg2 import pool, extras
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Tuple, Optional

load_dotenv()

# Configuração do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Lista dos meses
meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# Função para extrair dados de um pedido
def extrair_dados_pedido(pedido: dict) -> Optional[Tuple]:
    """
    Extrai os dados relevantes de um pedido da API.
    Retorna uma tupla com (numero_pedido, status, franqueado, fornecedor, data_pedido, mes_pedido, valor_pedido).
    Se algum campo obrigatório estiver faltando, retorna None.
    """
    try:
        numero_pedido = pedido['codigo']
        status = pedido['situacao']['descricao']
        franqueado = pedido['franqueado']['nome']
        fornecedor = pedido['fornecedor']['nome']
        data_pedido = datetime.strptime(pedido['dataCriacao'], '%Y-%m-%dT%H:%M:%S.%fZ')
        mes_pedido = meses[data_pedido.month - 1]
        valor_pedido = sum(item['quantidadeProdutos'] * item['valorUnitario'] for item in pedido['itensPedido'])
        return (numero_pedido, status, franqueado, fornecedor, data_pedido, mes_pedido, valor_pedido)
    except KeyError as e:
        logging.error(f"Erro ao processar pedido: campo {e} não encontrado.")
        return None

# Função para configurar o pool de conexões
def conectar_banco():
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=int(os.getenv('DB_POOL_MIN', 1)),
            maxconn=int(os.getenv('DB_POOL_MAX', 20)),
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
def inserir_pedidos_batch(conn, pedidos: List[Tuple]):
    try:
        with conn.cursor() as cursor:
            query = """
            INSERT INTO pedidos (numero_pedido, status, franqueado, fornecedor, data_pedido, mes_pedido, valor_pedido)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (numero_pedido) DO NOTHING;
            """
            cursor.executemany(query, pedidos)
        conn.commit()
        pedidos_inseridos = len(pedidos)
        logging.info(f'{pedidos_inseridos} pedidos inseridos com sucesso!')
        return pedidos_inseridos
    except Exception as e:
        logging.error(f'Erro ao inserir pedidos em batch: {e}', exc_info=True)
        return 0

# Função para atualizar os status diretamente na tabela 'pedidos'
def atualizar_status_pedidos(conn, pedidos: List[Tuple]):
    try:
        with conn.cursor() as cursor:
            # Preparar dados para atualização
            dados_update = [(p[1], str(p[0])) for p in pedidos]

            # Query para atualizar vários pedidos de uma vez
            update_query = """
            UPDATE pedidos
            SET status = atualizado.status
            FROM (VALUES %s) AS atualizado (status, numero_pedido)
            WHERE pedidos.numero_pedido = atualizado.numero_pedido
            AND pedidos.status != atualizado.status;
            """

            # Executar a atualização
            extras.execute_values(cursor, update_query, dados_update, template="(%s, %s)")
            conn.commit()

            # Contar quantos pedidos foram atualizados
            quantidade_atualizados = cursor.rowcount  # Usando rowcount para obter o número de linhas afetadas

            logging.info(f'{quantidade_atualizados} pedidos tiveram seu status atualizado.')
            return quantidade_atualizados

    except Exception as e:
        logging.error(f'Erro ao atualizar status dos pedidos: {e}', exc_info=True)
        return 0

# Função principal para buscar e processar pedidos
def processar_pedidos():
    url = 'https://app.centraldofranqueado.com.br/api/v2/pedidos/'
    headers = {'x-api-key': os.getenv('API_KEY')}
    params = {'periodo': datetime.today().strftime('%Y-%m-%d')}

    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)

    with requests.Session() as session:
        session.mount("https://", adapter)

        try:
            response = session.get(url, params=params, headers=headers, timeout=int(os.getenv('REQUEST_TIMEOUT', 10)))
            response.raise_for_status()

            dados_pedidos = response.json()
            if not isinstance(dados_pedidos, list):
                logging.error("A resposta da API não é uma lista de pedidos.")
                return

            conn = conectar_banco()
            if not conn:
                logging.error('Não foi possível conectar ao banco.')
                return

            pedidos_para_inserir = []
            for pedido in dados_pedidos:
                dados = extrair_dados_pedido(pedido)  # Extrai os dados do pedido
                if dados:  # Se os dados foram extraídos com sucesso
                    pedidos_para_inserir.append(dados)

            pedidos_inseridos = 0
            if pedidos_para_inserir:
                pedidos_inseridos = inserir_pedidos_batch(conn, pedidos_para_inserir)
                status_atualizados = atualizar_status_pedidos(conn, pedidos_para_inserir)

            conn.close()
            logging.info(f'Conexão com banco de dados fechada.')
            logging.info(f'Total de pedidos inseridos: {pedidos_inseridos}')
            logging.info(f'Total de status atualizados: {status_atualizados}')

        except requests.exceptions.RequestException as e:
            logging.error(f"Erro na requisição HTTP: {e}")

# Executar a função principal
if __name__ == "__main__":
    processar_pedidos()