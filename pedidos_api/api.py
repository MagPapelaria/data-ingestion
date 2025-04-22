import os
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def buscar_pedidos(periodo: str):
    url = 'https://app.centraldofranqueado.com.br/api/v2/pedidos/'
    headers = {'x-api-key': os.getenv('API_KEY')}
    params = {'periodo': periodo}

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
            return response.json()
        except requests.RequestException as e:
            logger.error(f'Erro ao buscar pedidos da API: {e}')
            return []
