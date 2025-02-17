import requests
import psycopg2
import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv  

load_dotenv()

# Configuração do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Função para conectar ao banco de dados
def conectar_banco():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
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
        logging.error(f'Erro ao inserir pedido {numero_pedido}: {e}', exc_info=True)

# Função principal para buscar e processar pedidos
def processar_pedidos():
    url = 'https://app.centraldofranqueado.com.br/api/v2/pedidos/'
    headers = {'x-api-key': os.getenv('API_KEY')}
    
    # Exemplo: buscar pedidos dos últimos 30 dias
    data_atual = datetime.today().strftime('%Y-%m-%d')
    params = {'periodo':data_atual}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
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
                try:
                    for pedido in dados_pedidos:
                        try:
                            numero_pedido = pedido['codigo']
                            status = pedido['situacao']['descricao']
                            franqueado = pedido['franqueado']['nome']
                            fornecedor = pedido['fornecedor']['nome']
                            data_pedido = datetime.strptime(pedido['dataCriacao'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%d-%m-%y')
                            valor_pedido = sum(item['quantidadeProdutos'] * item['valorUnitario'] for item in pedido['itensPedido'])

                            inserir_pedido(conn, numero_pedido, status, franqueado, fornecedor, data_pedido, valor_pedido)
                        except KeyError as e:
                            logging.error(f"Erro ao processar pedido: campo {e} não encontrado.")
                            continue
                finally:
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