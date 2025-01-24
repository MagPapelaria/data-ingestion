import requests
from transform import limpar_dados
from load import load_dados
import os
from dotenv import load_dotenv
import logging
from datetime import datetime  # Importa o módulo datetime

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

url = os.getenv("URL")
headers = {
    'x-api-key': os.getenv("API_KEY")
}

# Obtém a data de hoje no formato "YYYY-MM-DD"
hoje = datetime.today().strftime('%Y-%m-%d')

params = {
    'periodo': hoje,  # Define o período como a data de hoje
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
