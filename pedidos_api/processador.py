import logging
from db import get_conn, put_conn, inserir_pedidos_batch, atualizar_status_pedidos
from api import buscar_pedidos
from utils import extrair_dados_pedido

logger = logging.getLogger(__name__)

def processar_pedidos():
    pedidos_json = buscar_pedidos('2025-04-28')

    if not isinstance(pedidos_json, list):
        logger.warning("Resposta da API não é uma lista.")
        return

    pedidos = [extrair_dados_pedido(p) for p in pedidos_json]
    pedidos = [p for p in pedidos if p]

    if not pedidos:
        logger.info("Nenhum pedido processado.")
        return

    conn = get_conn()
    if not conn:
        logger.error("Não foi possível obter conexão com o banco.")
        return

    try:
        inseridos = inserir_pedidos_batch(conn, pedidos)
        atualizados = atualizar_status_pedidos(conn, pedidos)

        logger.info(f"Pedidos inseridos: {inseridos}")
        logger.info(f"Status atualizados: {atualizados}")
    finally:
        put_conn(conn)
