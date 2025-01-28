import requests
import psycopg2
import os
import logging
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from dotenv import load_dotenv

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuração do dotenv
load_dotenv()

# Funções de transformação (do arquivo transform.py)
def formatar_data(data):
    try:
        return datetime.fromisoformat(data[:-1]).strftime('%Y-%m-%d')
    except ValueError:
        raise ValueError(f"Formato de data inválido: {data}")

def extrair_nome_franqueado(franqueado):
    return franqueado['nome']

def extrair_nome_fornecedor(fornecedor):
    return fornecedor['nome']

def limpar_dados(pedidos):
    logging.info("Iniciando a limpeza e transformação dos dados.")
    dados_limpos = []
    try:
        for pedido in pedidos:
            dados_limpos.append({
                'número_do_pedido': pedido['codigo'],
                'status': pedido['situacao']['descricao'],
                'franqueado': extrair_nome_franqueado(pedido['franqueado']),
                'fornecedor': extrair_nome_fornecedor(pedido['fornecedor']),
                'data_do_pedido': formatar_data(pedido['dataCriacao']),
            })
        logging.info("Transformação concluída com sucesso.")
    except Exception as e:
        logging.exception("Erro ao transformar os dados.")
    return dados_limpos

# Funções de carregamento (do arquivo load.py)
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

# Função principal (do arquivo principal.py)
def ingest_data_caf():
    url = os.getenv("URL")
    headers = {
        'x-api-key': os.getenv("API_KEY")
    }

    hoje = datetime.today().strftime('%Y-%m-%d')

    params = {
        'periodo': hoje,
    }

    logging.info("Iniciando a extração de dados da API.")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            pedidos = response.json()
            logging.info("Dados extraídos com sucesso.")
            
            pedidos_limpos = limpar_dados(pedidos)
            logging.info("Dados transformados com sucesso.")
            
            load_dados(pedidos_limpos)
            logging.info("Dados carregados no banco com sucesso.")
        else:
            logging.error(f"Erro ao acessar a API: {response.status_code}, {response.text}")
    except Exception as e:
        logging.exception(f"Erro durante a extração de dados: {e}")

# Configuração do DAG no Airflow
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

with DAG(
    'ingest_data_caf',
    default_args=default_args,
    description='Pipeline que pega dados do CAF e sobe no banco de dados',
    schedule_interval='59 23 * * *',
    start_date=datetime(2025, 1, 28),
    catchup=False, 
) as dag:

    ingest_data_caf_task = PythonOperator(
        task_id='ingest_data_caf_task',
        python_callable=ingest_data_caf
    )

    ingest_data_caf_task
