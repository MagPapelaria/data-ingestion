import os
import requests
from dotenv import load_dotenv

def processa_chamados():
    load_dotenv()

    url = 'https://app.centraldofranqueado.com.br/api/v2/pedidos/'
    headers = {'x-api-key': os.getenv('API_KEY')}
    params = {'status': 'opened',
              }

    response = requests.get(url, headers=headers, params=params)
    
    # Garante que a resposta foi bem-sucedida
    response.raise_for_status()
    
    # Retorna os dados crus da API (formato JSON como vem)
    return response.json()

chamados = processa_chamados()
print(chamados)