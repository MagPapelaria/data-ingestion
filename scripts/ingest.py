# plugins/pedidos_utils.py
import requests
import psycopg2
import os
import logging
from datetime import datetime

# Configuração do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Função para conectar ao banco de dados
def conectar_banco():
    try:
        conn = psycopg2.connect(
            dbname= os.getenv('DB_NAME'),
            user= os.getenv('DB_USER'),
            password= os.getenv('DB_PASSWORD'),
            host= os.getenv('DB_HOST'),
            port= os.getenv('DB_PORT'),
        )
        logging.info('Conexão com banco de dados feita com sucesso!')
        return conn
    except Exception as e:
        logging.error(f'Erro ao conectar ao banco: {e}')
        return None

# Função para inserir os pedidos no banco de dados
def inserir_pedido(conn, numero_pedido, status, franqueado, fornecedor, data_pedido, valor_pedido):
    try:
        with conn.cursor() as cursor:
            query = """
            INSERT INTO pedidos (numero_pedido, status, franqueado, fornecedor, data_pedido, valor_pedido)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (numero_pedido) DO NOTHING;
            """
            cursor.execute(query, (numero_pedido, status, franqueado, fornecedor, data_pedido, valor_pedido))
        conn.commit()
        logging.info(f'Pedido {numero_pedido} inserido com sucesso!')
    except Exception as e:
        logging.error(f'Erro ao inserir pedido {numero_pedido}: {e}')

# Função principal para buscar e processar pedidos
def processar_pedidos():
    url = 'https://app.centraldofranqueado.com.br/api/v2/pedidos/'
    hoje = datetime.today().strftime('%Y-%m-%d')
    headers = {'x-api-key': os.getenv('API_KEY')}
    
    params = {'periodo': hoje}

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        dados_pedidos = response.json()

        if isinstance(dados_pedidos, list):
            conn = conectar_banco()
            if conn:
                for pedido in dados_pedidos:
                    numero_pedido = pedido['codigo']
                    status = pedido['situacao']['descricao']
                    franqueado = pedido['franqueado']['nome']
                    fornecedor = pedido['fornecedor']['nome']
                    data_pedido = datetime.strptime(pedido['dataCriacao'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%d-%m-%Y')
                    valor_pedido = sum(item['quantidadeProdutos'] * item['valorUnitario'] for item in pedido['itensPedido'])

                    inserir_pedido(conn, numero_pedido, status, franqueado, fornecedor, data_pedido, valor_pedido)

                conn.close()
                logging.info('Conexão com banco de dados fechada.')
            else:
                logging.error('Não foi possível conectar ao banco.')
        else:
            logging.error("A resposta da API não é uma lista de pedidos.")
    else:
        logging.error(f"Erro na requisição: {response.status_code}")
        logging.error(response.text)