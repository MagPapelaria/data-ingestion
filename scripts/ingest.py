import os
import logging
import requests
import psycopg2
from psycopg2 import pool, extras
from datetime import datetime
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Tuple, Optional, Dict, Any
import unicodedata
# Carrega variáveis de ambiente
load_dotenv()

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Lista de meses em português
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]


def conectar_banco() -> Optional[psycopg2.extensions.connection]:
    """
    Cria e retorna uma conexão com o banco de dados utilizando pool.
    """
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=int(os.getenv('DB_POOL_MIN', 1)),
            maxconn=int(os.getenv('DB_POOL_MAX', 5)),
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
        )
        logging.info('Conexão com o banco criada com sucesso.')
        return connection_pool.getconn()
    except Exception as e:
        logging.error(f'Erro ao conectar no banco: {e}')
        return None


def extrair_dados_pedido(pedido: Dict[str, Any]) -> Optional[Tuple]:
    """
    Extrai os dados necessários de um pedido da API.
    """
    try:
        numero_pedido = pedido['codigo']
        status_bruto = pedido['situacao']['descricao']
        status = status_bruto.upper()
        franqueado = pedido['franqueado']['nome']

        # Limpa o nome do fornecedor e coloca em caps
        fornecedor_bruto = pedido['fornecedor']['nome']
        fornecedor = fornecedor_bruto.split('-')[-1].strip().upper()
        fornecedor = unicodedata.normalize("NFKD", fornecedor).encode("ASCII", "ignore").decode("ASCII")

        data_pedido = datetime.strptime(pedido['dataCriacao'], '%Y-%m-%dT%H:%M:%S.%fZ')
        mes_pedido = MESES[data_pedido.month - 1]
        valor_pedido = sum(item['quantidadeProdutos'] * item['valorUnitario'] for item in pedido['itensPedido'])

        return (numero_pedido, status, franqueado, fornecedor, data_pedido, mes_pedido, valor_pedido)

    except KeyError as e:
        logging.warning(f'Campo ausente ao processar pedido: {e}')
        return None


def inserir_pedidos_batch(conn, pedidos: List[Tuple]) -> int:
    """
    Insere pedidos no banco em lote.
    """
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
        logging.error(f'Erro ao inserir pedidos: {e}')
        conn.rollback()
        return 0


def atualizar_status_pedidos(conn, pedidos: List[Tuple]) -> int:
    """
    Atualiza o status dos pedidos já existentes.
    """
    try:
        with conn.cursor() as cursor:
            for pedido in pedidos:
                numero_pedido, status = str(pedido[0]), pedido[1]  # <-- garante que é string
                cursor.execute("""
                    UPDATE pedidos
                    SET status = %s
                    WHERE numero_pedido = %s;
                """, (status, numero_pedido))
        
        conn.commit()
        logging.info(f"Status dos pedidos atualizado com sucesso.")
        return len(pedidos)

    except Exception as e:
        logging.error(f"Erro ao atualizar status dos pedidos: {e}")
        conn.rollback()
        return 0


def processar_pedidos() -> None:
    """
    Busca e processa os pedidos da API.
    """
    url = 'https://app.centraldofranqueado.com.br/api/v2/pedidos/'
    headers = {'x-api-key': os.getenv('API_KEY')}
    params = {'periodo': '2025-04-21'}

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
            response = session.get(url, headers=headers, params=params, timeout=int(os.getenv('REQUEST_TIMEOUT', 10)))
            response.raise_for_status()

            dados_pedidos = response.json()

            if not isinstance(dados_pedidos, list):
                logging.warning('Resposta da API não é uma lista.')
                return

            pedidos_processados = [extrair_dados_pedido(p) for p in dados_pedidos]
            pedidos_processados = [p for p in pedidos_processados if p]

            pedidos_inseridos = 0
            status_atualizados = 0

            with conectar_banco() as conn:
                if not conn:
                    logging.error('Não foi possível conectar ao banco.')
                    return

                if pedidos_processados:
                    pedidos_inseridos = inserir_pedidos_batch(conn, pedidos_processados)
                    status_atualizados = atualizar_status_pedidos(conn, pedidos_processados)

            logging.info(f'Total de pedidos inseridos: {pedidos_inseridos}')
            logging.info(f'Total de status atualizados: {status_atualizados}')

        except requests.exceptions.RequestException as e:
            logging.error(f'Erro na requisição HTTP: {e}')


if __name__ == '__main__':
    processar_pedidos()
