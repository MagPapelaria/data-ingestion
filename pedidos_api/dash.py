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


# --- CACHE DE DADOS ---
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

        #Exclusão do B2B
        df['franqueado'] = df['franqueado'].astype(str)
        df = df[~df['franqueado'].str.lower().str.startswith("b2b")]

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

# --- FUNÇÃO PARA CÁLCULO DE TENDÊNCIA (DRY) ---
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


# VERIFICAÇÃO DE DATAFRAME VAZIO 
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

# Abas para organizar as análises
tab1, tab2 = st.tabs(["Análise de Franqueados", "Análise Geral e Fornecedores"])


with tab1:
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
    st.download_button("📥 Exportar Top Franqueados", export_excel(df_rank), file_name="rank_franqueados.xlsx")

    # --- ANÁLISE DE TENDÊNCIA USANDO A FUNÇÃO ---
    df_tendencia = calcular_tendencia_mensal(df_franqueados_ativos)
    
    col_queda, col_crescimento = st.columns(2)
    with col_queda:
        # 📉 Queda de Pedidos
        st.markdown(f"""<h4>📉 Top {top_n} Franqueados com Tendência de Queda
        <span class="tooltip"> ℹ️
          <span class="tooltiptext">
            Compara os dois últimos meses de atividade e mostra aqueles com maior queda.
          </span>
        </span></h4>""", unsafe_allow_html=True)

        df_queda = df_tendencia[df_tendencia['variacao'] < 0].sort_values(by='variacao', ascending=True).head(top_n)
        if not df_queda.empty:
            fig_queda = px.bar(df_queda, x='franqueado', y='variacao',
                               title=f"Top {top_n} Franqueados com Maior Queda",
                               color_discrete_sequence=['#FF6347'])
            fig_queda.update_layout(yaxis_title="Variação (nº de pedidos)", xaxis_title="", xaxis_tickangle=-45)
            st.plotly_chart(fig_queda, use_container_width=True)
            st.download_button("📥 Exportar Queda", export_excel(df_queda), file_name="queda_pedidos.xlsx")
        else:
            st.info("Nenhum franqueado apresentou queda de pedidos.")
    
    with col_crescimento:
        # 🔼 Crescimento de Pedidos
        st.markdown(f"""<h4>🔼 Top {top_n} Franqueados com Tendência de Crescimento
        <span class="tooltip"> ℹ️
          <span class="tooltiptext">
            Compara os dois últimos meses de atividade e mostra aqueles com maior aumento.
          </span>
        </span></h4>""", unsafe_allow_html=True)

        df_crescimento = df_tendencia[df_tendencia['variacao'] > 0].sort_values(by='variacao', ascending=False)
        df_crescimento_top_n = df_crescimento.head(top_n)

        if not df_crescimento_top_n.empty:
            fig_crescimento = px.bar(df_crescimento_top_n, x='franqueado', y='variacao',
                                     title=f"Top {top_n} Franqueados com Maior Crescimento",
                                     color_discrete_sequence=['#4682B4'])
            fig_crescimento.update_layout(yaxis_title="Variação (nº de pedidos)", xaxis_title="", xaxis_tickangle=-45)
            st.plotly_chart(fig_crescimento, use_container_width=True)
            st.download_button("📥 Exportar Crescimento", export_excel(df_crescimento), file_name="crescimento_pedidos.xlsx")
        else:
            st.info("Nenhum franqueado apresentou crescimento de pedidos.")


with tab2:
    # 📅 Total de Pedidos por Mês
    st.markdown("""<h4>📅 Total de Pedidos por Mês
    <span class="tooltip"> ℹ️
      <span class="tooltiptext">
        Agrupa todos os pedidos por mês e conta o total.
      </span>
    </span></h4>""", unsafe_allow_html=True)

    df_mensal = df_filtrado.groupby('ano_mes').agg(total_pedidos=('numero_pedido', 'count')).reset_index()
    fig_trend = px.line(df_mensal, x='ano_mes', y='total_pedidos', markers=True, title="Evolução Mensal de Pedidos", color_discrete_sequence=px.colors.qualitative.Plotly)
    fig_trend.update_layout(xaxis_title="Mês", yaxis_title="Quantidade de Pedidos")
    st.plotly_chart(fig_trend, use_container_width=True)
    st.download_button("📥 Exportar Pedidos Mensais", export_excel(df_mensal), file_name="pedidos_mensais.xlsx")
    
    st.markdown("---")

    # --- NOVA ANÁLISE: TOP FORNECEDORES POR VALOR ---
    st.markdown(f"""<h4>🏆 Top {top_n} Fornecedores por Valor de Pedido
    <span class="tooltip"> ℹ️
      <span class="tooltiptext">
        Mostra os fornecedores que representam o maior valor total de pedidos no período selecionado.
      </span>
    </span></h4>""", unsafe_allow_html=True)
    
    df_fornecedores = df_filtrado.groupby('fornecedor').agg(valor_total=('valor_pedido', 'sum')).reset_index()
    df_fornecedores_top = df_fornecedores.sort_values(by='valor_total', ascending=False).head(top_n)
    
    fig_fornecedores = px.bar(
        df_fornecedores_top,
        x='fornecedor',
        y='valor_total',
        title=f"Top {top_n} Fornecedores por Faturamento",
        text_auto='.2s',
        labels={'valor_total': 'Valor Total (R$)'}
    )
    fig_fornecedores.update_traces(textposition='outside')
    fig_fornecedores.update_layout(xaxis_title="Fornecedor", yaxis_title="Valor Total (R$)")
    st.plotly_chart(fig_fornecedores, use_container_width=True)
    st.download_button("📥 Exportar Top Fornecedores", export_excel(df_fornecedores_top), file_name="rank_fornecedores.xlsx")
