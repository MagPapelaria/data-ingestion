import streamlit as st
import pandas as pd
import plotly.express as px
import io

# Assumindo que seu arquivo db.py com get_conn e put_conn existe
from db import get_conn, put_conn

st.set_page_config(page_title="Dashboard de Pedidos", layout="wide", initial_sidebar_state="expanded")

# Estilo CSS para tooltips personalizados (mantido como estava)
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


# --- MELHORIA 1: CACHE DE DADOS ---
@st.cache_data
def carregar_dados():
    """
    Função para conectar ao banco, buscar os dados e fazer o pré-processamento.
    O resultado fica em cache para não ser executado a cada interação no app.
    """
    print("Executando a carga de dados do banco...") # Para depuração
    conn = None # Inicia conn como None
    try:
        conn = get_conn()
        query = "SELECT * FROM pedidos;"
        df = pd.read_sql(query, conn)
        # Conversões que não dependem de filtros são feitas aqui
        df['data_pedido'] = pd.to_datetime(df['data_pedido'])
        df['ano'] = df['data_pedido'].dt.year
        df['mes'] = df['data_pedido'].dt.month
        df['ano_mes'] = df['data_pedido'].dt.to_period('M').astype(str)
        return df
    finally:
        # Garante que a conexão seja devolvida mesmo se houver um erro
        if conn:
            put_conn(conn)

# Carrega os dados usando a função com cache
df_original = carregar_dados()

# --- MELHORIA 3: FUNÇÃO PARA CÁLCULO DE TENDÊNCIA (DRY) ---
def calcular_tendencia_mensal(df):
    """
    Calcula a variação no número de pedidos entre os dois últimos meses
    de atividade para cada franqueado.
    """
    df_trend = df.groupby(['franqueado', 'ano_mes']).agg(total_pedidos=('numero_pedido', 'count')).reset_index()
    df_trend = df_trend.sort_values(by=['franqueado', 'ano_mes'])
    
    # Pega os dados dos últimos dois meses de atividade de cada franqueado
    df_last_two = df_trend.groupby('franqueado').tail(2)
    
    # Calcula a diferença em relação ao mês anterior
    df_last_two['variacao'] = df_last_two.groupby('franqueado')['total_pedidos'].diff()
    
    # Filtra para manter apenas o último mês que contém a variação calculada
    df_final = df_last_two.dropna(subset=['variacao'])
    df_final['variacao'] = df_final['variacao'].astype(int)
    
    return df_final[['franqueado', 'variacao']]


def export_excel(dataframe):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        dataframe.to_excel(writer, index=False)
    output.seek(0)
    return output

# --- Filtros na Sidebar ---
with st.sidebar:
    st.title("Filtros")
    franqueados = st.multiselect("Franqueado", sorted(df_original["franqueado"].unique()))
    fornecedores = st.multiselect("Fornecedor", sorted(df_original["fornecedor"].unique()))
    status = st.multiselect("Status", sorted(df_original["status"].unique()))
    
    # Filtro de data
    data_inicio = st.date_input("Data inicial", df_original["data_pedido"].min().date())
    data_fim = st.date_input("Data final", df_original["data_pedido"].max().date())
    st.markdown("---")
    
    # --- MELHORIA 6: RANKING CONFIGURÁVEL ---
    top_n = st.number_input(
        "Itens nos rankings", 
        min_value=3, 
        max_value=30, 
        value=10, 
        step=1,
        help="Selecione o número de franqueados a serem exibidos nos gráficos de ranking."
    )
    st.markdown("---")

# Aplicação dos filtros em uma cópia do dataframe original
df_filtrado = df_original.copy()

if franqueados:
    df_filtrado = df_filtrado[df_filtrado["franqueado"].isin(franqueados)]
if fornecedores:
    df_filtrado = df_filtrado[df_filtrado["fornecedor"].isin(fornecedores)]
if status:
    df_filtrado = df_filtrado[df_filtrado["status"].isin(status)]
    
# Filtro de data
df_filtrado = df_filtrado[
    (df_filtrado['data_pedido'] >= pd.to_datetime(data_inicio)) & 
    (df_filtrado['data_pedido'] <= pd.to_datetime(data_fim))
]


# --- MELHORIA 2: VERIFICAÇÃO DE DATAFRAME VAZIO ---
if df_filtrado.empty:
    st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados.")
    st.stop() # Interrompe a execução do app

# Remover franqueados [Excluídos] das análises específicas
df_franqueados_ativos = df_filtrado[~df_filtrado['franqueado'].str.contains(r'\[Excluído\]', case=False, na=False)]

# Título e KPIs
st.title("📦 Dashboard Analítico de Pedidos")
col1, col2, col3 = st.columns(3)
col1.metric("Total de Pedidos", f"{len(df_filtrado):,}")
col2.metric("Valor Total", f"R$ {df_filtrado['valor_pedido'].sum():,.2f}")
col3.metric("Franqueados Ativos", df_franqueados_ativos['franqueado'].nunique())

st.markdown("---")

# 📅 Total de Pedidos por Mês
st.markdown("""<h4>📅 Total de Pedidos por Mês
<span class="tooltip"> ℹ️
  <span class="tooltiptext">
    Agrupa todos os pedidos por mês e conta o total. Inclui todos os franqueados, inclusive os desativados.
  </span>
</span></h4>""", unsafe_allow_html=True)

df_mensal = df_filtrado.groupby('ano_mes').agg(total_pedidos=('numero_pedido', 'count')).reset_index()
fig_trend = px.line(df_mensal, x='ano_mes', y='total_pedidos', markers=True, title="Evolução Mensal de Pedidos", color_discrete_sequence=px.colors.qualitative.Plotly)
fig_trend.update_layout(xaxis_title="Mês", yaxis_title="Quantidade de Pedidos")
st.plotly_chart(fig_trend, use_container_width=True)
st.download_button("📥 Exportar Excel", export_excel(df_mensal), file_name="pedidos_mensais.xlsx")

# 🏪 Top Franqueados
st.markdown(f"""<h4>🏪 Top {top_n} Franqueados por Quantidade de Pedidos
<span class="tooltip"> ℹ️
  <span class="tooltiptext">
    Mostra os {top_n} franqueados com maior volume de pedidos no período selecionado. Ignora franqueados desativados.
  </span>
</span></h4>""", unsafe_allow_html=True)

df_rank = df_franqueados_ativos.groupby('franqueado')['numero_pedido'].count().reset_index(name='qtd_pedidos')
df_rank = df_rank.sort_values(by='qtd_pedidos', ascending=False).head(top_n)
fig_rank = px.bar(df_rank, x='franqueado', y='qtd_pedidos', title=f"Top {top_n} Franqueados", color='franqueado', color_discrete_sequence=px.colors.qualitative.Set2)
st.plotly_chart(fig_rank, use_container_width=True)
st.download_button("📥 Exportar Excel", export_excel(df_rank), file_name="rank_franqueados.xlsx")

# ⏱️ Tempo Médio Entre Pedidos
st.markdown("""<h4>⏱️ Tempo Médio Entre Pedidos por Franqueado
<span class="tooltip"> ℹ️
  <span class="tooltiptext">
    Calcula a média de dias entre os pedidos feitos por cada franqueado. Considera apenas franqueados ativos com 2 ou mais pedidos.
  </span>
</span></h4>""", unsafe_allow_html=True)

df_sorted = df_franqueados_ativos.sort_values(['franqueado', 'data_pedido'])
df_sorted['diff_dias'] = df_sorted.groupby('franqueado')['data_pedido'].diff().dt.days
df_tempo_medio = df_sorted.groupby('franqueado')['diff_dias'].mean().reset_index().dropna()
df_tempo_medio.columns = ['franqueado', 'tempo_medio_dias']
df_tempo_medio = df_tempo_medio.sort_values(by='tempo_medio_dias', ascending=True).head(15) # Ascending=True faz mais sentido aqui
fig_tempo = px.bar(df_tempo_medio, x='franqueado', y='tempo_medio_dias', title="Tempo Médio Entre Pedidos (em dias)")
st.plotly_chart(fig_tempo, use_container_width=True)
st.download_button("📥 Exportar Excel", export_excel(df_tempo_medio), file_name="tempo_medio.xlsx")

# --- ANÁLISE DE TENDÊNCIA USANDO A FUNÇÃO ---
df_tendencia = calcular_tendencia_mensal(df_franqueados_ativos)

# 📉 Queda de Pedidos
st.markdown(f"""<h4>📉 Top {top_n} Franqueados com Tendência de Queda
<span class="tooltip"> ℹ️
  <span class="tooltiptext">
    Compara os dois últimos meses de atividade e mostra aqueles com maior queda. Exclui franqueados marcados como [Excluído].
  </span>
</span></h4>""", unsafe_allow_html=True)

df_queda = df_tendencia[df_tendencia['variacao'] < 0].sort_values(by='variacao', ascending=True).head(top_n)
if not df_queda.empty:
    fig_queda = px.bar(df_queda, x='franqueado', y='variacao',
                       title=f"Top {top_n} Franqueados com Maior Queda de Pedidos (Comparativo Mês a Mês)",
                       color_discrete_sequence=['#FF6347'])
    fig_queda.update_layout(yaxis_title="Variação (nº de pedidos)", xaxis_title="", xaxis_tickangle=-45)
    st.plotly_chart(fig_queda, use_container_width=True)
    st.download_button("📥 Exportar Excel", export_excel(df_queda), file_name="queda_pedidos.xlsx")
else:
    st.info("Nenhum franqueado apresentou queda de pedidos no período analisado.")

# 🔼 Crescimento de Pedidos
st.markdown(f"""<h4>🔼 Top {top_n} Franqueados com Tendência de Crescimento
<span class="tooltip"> ℹ️
  <span class="tooltiptext">
    Compara os dois últimos meses de atividade e mostra aqueles com maior aumento, o que pode indicar um aumento no risco de inadimplência. Exclui franqueados [Excluído].
  </span>
</span></h4>""", unsafe_allow_html=True)

df_crescimento = df_tendencia[df_tendencia['variacao'] > 0].sort_values(by='variacao', ascending=False)
df_crescimento_top_n = df_crescimento.head(top_n)

if not df_crescimento_top_n.empty:
    fig_crescimento = px.bar(df_crescimento_top_n, x='franqueado', y='variacao',
                             title=f"Top {top_n} Franqueados com Maior Crescimento de Pedidos (Comparativo Mês a Mês)",
                             color_discrete_sequence=['#4682B4'])
    fig_crescimento.update_layout(yaxis_title="Variação (nº de pedidos)", xaxis_title="", xaxis_tickangle=-45)
    st.plotly_chart(fig_crescimento, use_container_width=True)
    st.download_button("📥 Exportar Excel", export_excel(df_crescimento), file_name="crescimento_pedidos.xlsx")
else:
    st.info("Nenhum franqueado apresentou crescimento de pedidos no período analisado.")