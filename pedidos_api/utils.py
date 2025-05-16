import unicodedata
from datetime import datetime

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

def extrair_dados_pedido(pedido):
    try:
        numero_pedido = pedido['codigo']
        status = pedido['situacao']['descricao'].upper().encode("ASCII", "ignore").decode("ASCII")
        franqueado = pedido['franqueado']['nome']

        fornecedor_bruto = pedido['fornecedor']['nome']
        fornecedor = fornecedor_bruto.split('-')[-1].strip().upper()
        fornecedor = unicodedata.normalize("NFKD", fornecedor).encode("ASCII", "ignore").decode("ASCII")

        data_pedido = datetime.strptime(pedido['dataCriacao'], '%Y-%m-%dT%H:%M:%S.%fZ')
        mes_pedido = MESES[data_pedido.month - 1]

        valor_pedido = sum(item['quantidadeProdutos'] * item['valorUnitario'] for item in pedido['itensPedido'])

        return (numero_pedido, status, franqueado, fornecedor, data_pedido, mes_pedido, valor_pedido)
    except KeyError as e:
        print(f"Erro ao extrair dados do pedido: campo ausente {e}")
        return None
