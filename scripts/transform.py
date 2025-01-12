import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def formatar_data(data):
    return data[:10]

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
