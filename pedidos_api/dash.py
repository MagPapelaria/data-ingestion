import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from dotenv import load_dotenv
from db import get_conn, put_conn

st.set_page_config(page_title="Dashboard de Pedidos", layout="wide", initial_sidebar_state="expanded")

load_dotenv()

# Estilo CSS para tooltips personalizados (MANTIDO EXATAMENTE COMO ESTAVA)
st.markdown("""
<style>
.tooltip {
  position: relative;
  display: inline-block;
  cursor: pointer;
}
.tooltip .tooltiptext {
  visibility: hidden;
  width: 260px;
  background-color: rgba(60, 60, 60, 0.9);
  color: #fff;
  text-align: left;
  border-radius: 8px;
  padding: 10px;
  position: absolute;
  z-index: 1;
  bottom: 125%;
  left: 0%;
  opacity: 0;
  transition: opacity 0.3s;
  font-size: 13px;
}
.tooltip:hover .tooltiptext {
  visibility: visible;
  opacity: 1;
}
</style>
""", unsafe_allow_html=True)

# --- CACHE DE DADOS ---
@st.cache_data
def load_data():
    """Carrega dados do banco de dados, realiza limpeza inicial e conversões de tipo."""
    print("Executando a carga de dados do banco...")
    conn = None
    try:
        conn = get_conn()
        query = "SELECT * FROM pedidos;"
        df = pd.read_sql(query, conn)

        # Exclusão do B2B
        df['franqueado'] = df['franqueado'].astype(str)
        df = df[~df['franqueado'].str.lower().str.startswith("b2b")]

        # Conversões que não dependem de filtros são feitas aqui
        df['data_pedido'] = pd.to_datetime(df['data_pedido'])
        df['ano'] = df['data_pedido'].dt.year
        df['mes'] = df['data_pedido'].dt.month
        df['ano_mes'] = df['data_pedido'].dt.to_period('M').astype(str)
        return df
    finally:
        if conn:
            put_conn(conn)

df_original = load_data()

def calculate_monthly_trend(df):
    """Calcula a variação mês a mês na contagem de pedidos para franqueados."""
    df_trend = df.groupby(['franqueado', 'ano_mes']).agg(total_pedidos=('numero_pedido', 'count')).reset_index()
    df_trend = df_trend.sort_values(by=['franqueado', 'ano_mes'])

    # Pega os últimos dois meses para cada franqueado
    df_last_two = df_trend.groupby('franqueado').tail(2)
    # Calcula a diferença no total de pedidos entre os últimos dois meses
    df_last_two['variacao'] = df_last_two.groupby('franqueado')['total_pedidos'].diff()
    # Filtra linhas onde a variação é NaN (significa apenas um mês de dados)
    df_final = df_last_two.dropna(subset=['variacao'])
    df_final['variacao'] = df_final['variacao'].astype(int)
    return df_final[['franqueado', 'variacao']]

def export_excel(dataframe):
    """Exporta um DataFrame pandas para um arquivo Excel em bytes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        dataframe.to_excel(writer, index=False)
    output.seek(0)
    return output

# --- FILTROS SIDEBAR ---
with st.sidebar:
    st.title("Filtros do Dashboard")
    unique_franqueados = sorted(df_original["franqueado"].unique())
    franqueados = st.multiselect("Selecione Franqueados", unique_franqueados)

    unique_fornecedores = sorted(df_original["fornecedor"].unique())
    fornecedores = st.multiselect("Selecione Fornecedores", unique_fornecedores)
    
    unique_status = sorted(df_original["status"].unique())
    status = st.multiselect("Selecione Status", unique_status)

    min_date = df_original["data_pedido"].min().date()
    max_date = df_original["data_pedido"].max().date()
    data_inicio = st.date_input("Data Inicial", min_date)
    data_fim = st.date_input("Data Final", max_date)
    st.markdown("---")

    top_n = st.number_input(
        "Número de Itens nos Rankings", 
        min_value=3, max_value=30, value=10, step=1,
        help="Selecione a quantidade de itens (franqueados/fornecedores) a serem exibidos nos gráficos de ranking."
    )
    st.markdown("---")

# --- FILTRAGEM DE DADOS ---
df_filtered = df_original.copy()

if franqueados:
    df_filtered = df_filtered[df_filtered["franqueado"].isin(franqueados)]
if fornecedores:
    df_filtered = df_filtered[df_filtered["fornecedor"].isin(fornecedores)]
if status:
    df_filtered = df_filtered[df_filtered["status"].isin(status)]

df_filtered = df_filtered[
    (df_filtered['data_pedido'] >= pd.to_datetime(data_inicio)) & 
    (df_filtered['data_pedido'] <= pd.to_datetime(data_fim))
]

if df_filtered.empty:
    st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados. Por favor, ajuste os filtros.")
    st.stop()

df_active_franchisees = df_filtered[~df_filtered['franqueado'].str.contains(r'\[Excluído\]', case=False, na=False)]

# --- INDICADORES CHAVE DE DESEMPENHO (KPIs) ---
total_pedidos_kpi = len(df_filtered)
total_valor_kpi = df_filtered['valor_pedido'].sum()
active_franchisees_kpi = df_active_franchisees['franqueado'].nunique()

st.title("📦 Dashboard Analítico de Pedidos")
col1, col2, col3 = st.columns(3)
col1.metric("Total de Pedidos", f"{total_pedidos_kpi:,.0f}")
col2.metric("Valor Total", f"R$ {total_valor_kpi:,.2f}")
col3.metric("Franqueados Ativos", active_franchisees_kpi)
st.markdown("---")

# --- ABAS ---
tab1, tab2 = st.tabs(["Análise de Franqueados", "Análise Geral e Fornecedores"])

with tab1:
    st.markdown(f"""<h4>🏪 Top {top_n} Franqueados por Quantidade de Pedidos</h4>""", unsafe_allow_html=True)

    df_rank = df_active_franchisees.groupby('franqueado')['numero_pedido'].count().reset_index(name='qtd_pedidos')
    df_rank = df_rank.sort_values(by='qtd_pedidos', ascending=False).head(top_n)
    
    # Customizando dados de hover para melhor legibilidade
    fig_rank = px.bar(df_rank, x='franqueado', y='qtd_pedidos', 
                      title=f"Top {top_n} Franqueados por Pedidos", 
                      color='franqueado', 
                      color_discrete_sequence=px.colors.qualitative.Set2,
                      hover_data={'qtd_pedidos': ':,0f'}) # Formata com separador de milhares

    st.plotly_chart(fig_rank, use_container_width=True)
    st.download_button("📥 Exportar Top Franqueados", export_excel(df_rank), file_name="rank_franqueados.xlsx")

    # --- Análise de Tendência ---
    df_trend = calculate_monthly_trend(df_active_franchisees)
    
    col_decline, col_growth = st.columns(2)
    with col_decline:
        st.markdown(f"""<h4>📉 Top {top_n} Franqueados com Tendência de Queda</h4>""", unsafe_allow_html=True)

        df_decline = df_trend[df_trend['variacao'] < 0].sort_values(by='variacao', ascending=True).head(top_n)
        if not df_decline.empty:
            fig_decline = px.bar(df_decline, x='franqueado', y='variacao',
                                title=f"Top {top_n} Franqueados com Maior Queda",
                                color_discrete_sequence=['#FF6347'],
                                hover_data={'variacao': ':,0f'}) # Formata com separador de milhares
            fig_decline.update_layout(yaxis_title="Variação (nº de pedidos)", xaxis_title="", xaxis_tickangle=-45)
            st.plotly_chart(fig_decline, use_container_width=True)
            st.download_button("📥 Exportar Queda", export_excel(df_decline), file_name="queda_pedidos.xlsx")
        else:
            st.info("Nenhum franqueado apresentou queda significativa de pedidos no período.")
    
    with col_growth:
        st.markdown(f"""<h4>🔼 Top {top_n} Franqueados com Tendência de Crescimento</h4>""", unsafe_allow_html=True)

        df_growth = df_trend[df_trend['variacao'] > 0].sort_values(by='variacao', ascending=False).head(top_n)

        if not df_growth.empty:
            fig_growth = px.bar(df_growth, x='franqueado', y='variacao',
                                 title=f"Top {top_n} Franqueados com Maior Crescimento",
                                 color_discrete_sequence=['#4682B4'],
                                 hover_data={'variacao': ':,0f'}) # Formata com separador de milhares
            fig_growth.update_layout(yaxis_title="Variação (nº de pedidos)", xaxis_title="", xaxis_tickangle=-45)
            st.plotly_chart(fig_growth, use_container_width=True)
            st.download_button("📥 Exportar Crescimento", export_excel(df_growth), file_name="crescimento_pedidos.xlsx")
        else:
            st.info("Nenhum franqueado apresentou crescimento significativo de pedidos no período.")

with tab2:
    st.markdown("""<h4>📅 Total de Pedidos por Mês</h4>""", unsafe_allow_html=True)

    df_monthly = df_filtered.groupby('ano_mes').agg(total_pedidos=('numero_pedido', 'count')).reset_index()
    fig_trend = px.line(df_monthly, x='ano_mes', y='total_pedidos', markers=True, 
                        title="Evolução Mensal de Pedidos", 
                        color_discrete_sequence=px.colors.qualitative.Plotly,
                        hover_data={'total_pedidos': ':,0f'}) # Formata com separador de milhares
    fig_trend.update_layout(xaxis_title="Mês", yaxis_title="Quantidade de Pedidos")
    st.plotly_chart(fig_trend, use_container_width=True)
    st.download_button("📥 Exportar Pedidos Mensais", export_excel(df_monthly), file_name="pedidos_mensais.xlsx")
    
    st.markdown("---")

    st.markdown(f"""<h4>🏆 Top {top_n} Fornecedores por Valor de Pedido</h4>""", unsafe_allow_html=True)
    
    df_suppliers = df_filtered.groupby('fornecedor').agg(valor_total=('valor_pedido', 'sum')).reset_index()
    df_suppliers_top = df_suppliers.sort_values(by='valor_total', ascending=False).head(top_n)
    
    fig_suppliers = px.bar(
        df_suppliers_top,
        x='fornecedor',
        y='valor_total',
        title=f"Top {top_n} Fornecedores por Faturamento",
        text_auto='.2s', # Auto-formata texto nas barras
        labels={'valor_total': 'Valor Total (R$)'},
        hover_data={'valor_total': ':,.2f'} # Formata como moeda
    )
    fig_suppliers.update_traces(textposition='outside')
    fig_suppliers.update_layout(xaxis_title="Fornecedor", yaxis_title="Valor Total (R$)")
    st.plotly_chart(fig_suppliers, use_container_width=True)
    st.download_button("📥 Exportar Top Fornecedores", export_excel(df_suppliers_top), file_name="rank_fornecedores.xlsx")

    st.markdown("---")

    # --- NOVA A# --- ANÁLISE: Distribuição de Pedidos por Status ---
    st.markdown(f"""<h4>📊 Distribuição de Pedidos por Status</h4>""", unsafe_allow_html=True)
    
    # Lista dos status que você deseja exibir
    status_desejados = ["FINALIZADO", "CANCELADO", "PEDIDO ENTREGUE", "EM PROCESSAMENTO"]
    
    # Filtra o DataFrame para incluir apenas os status desejados
    df_status_for_chart = df_filtered[df_filtered["status"].isin(status_desejados)].copy()
    
    # Verificar se o DataFrame ainda tem dados após o filtro de status específico
    if df_status_for_chart.empty:
        st.info("Nenhum pedido encontrado para os status desejados neste período. Ajuste os filtros gerais.")
    else:
        df_status_distribution = df_status_for_chart.groupby('status').agg(count_pedidos=('numero_pedido', 'count')).reset_index()
        df_status_distribution['percentage'] = (df_status_distribution['count_pedidos'] / df_status_distribution['count_pedidos'].sum()) * 100

        fig_status = px.pie(df_status_distribution, values='count_pedidos', names='status', 
                            title="Distribuição de Pedidos por Status",
                            hole=.3, # Cria um gráfico de donut (rosca)
                            color_discrete_sequence=px.colors.qualitative.Pastel,
                            hover_data={'count_pedidos': ':,0f', 'percentage': ':.2f'})
        fig_status.update_traces(textinfo='percent+label', pull=[0.05]*len(df_status_distribution)) # Mostra percentual e rótulo, puxa ligeiramente as fatias
        fig_status.update_layout(showlegend=True) # Garante que a legenda esteja visível
        st.plotly_chart(fig_status, use_container_width=True)
        st.download_button("📥 Exportar Distribuição de Status", export_excel(df_status_distribution), file_name="distribuicao_status.xlsx")
