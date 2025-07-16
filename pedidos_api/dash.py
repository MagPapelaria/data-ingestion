import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from dotenv import load_dotenv
from db import get_conn, put_conn
from datetime import timedelta, date

# Define add_months function globally to avoid redefinition on reruns
def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    return date(year, month, day)

st.set_page_config(page_title="Dashboard de Pedidos", layout="wide", initial_sidebar_state="expanded")

load_dotenv()

# Estilo CSS para tooltips personalizados e multiselect (MANTIDO EXATAMENTE COMO ESTAVA)
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

/* NOVO: Estilo para diminuir a altura do multiselect */
.stMultiSelect div[data-baseweb="select"] > div:first-child {
    max-height: 150px; /* Ajuste este valor conforme necessário */
    overflow-y: auto; /* Adiciona rolagem vertical */
}
</style>
""", unsafe_allow_html=True)

# --- CACHE DE DADOS ---
@st.cache_data
def load_data():
    """Carrega dados do banco de dados, realiza limpeza inicial e conversões de tipo."""
    loading_message_placeholder = st.empty()
    loading_message_placeholder.info("⌛ Carregando dados do banco de dados... Isso pode levar alguns segundos.")

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

        # Limpa a mensagem de carregamento após o sucesso
        loading_message_placeholder.empty()
        return df
    finally:
        if conn:
            put_conn(conn)

# --- Initialize session state for filters ---
if 'franqueados_selected' not in st.session_state:
    st.session_state['franqueados_selected'] = []
if 'fornecedores_selected' not in st.session_state:
    st.session_state['fornecedores_selected'] = []
if 'status_selected' not in st.session_state:
    st.session_state['status_selected'] = []
if 'data_inicio_selected' not in st.session_state:
    st.session_state['data_inicio_selected'] = None # Will be set after df_original is loaded
if 'data_fim_selected' not in st.session_state:
    st.session_state['data_fim_selected'] = None # Will be set after df_original is loaded
if 'top_n_selected' not in st.session_state:
    st.session_state['top_n_selected'] = 10 # Default value

with st.spinner('Carregando dados do banco de dados...'): # Spinner for initial data load
    df_original = load_data()

# Set default date values in session state if not already set
if st.session_state['data_inicio_selected'] is None:
    st.session_state['data_inicio_selected'] = df_original["data_pedido"].min().date()
if st.session_state['data_fim_selected'] is None:
    st.session_state['data_fim_selected'] = df_original["data_pedido"].max().date()


def calculate_monthly_trend(df):
    """Calcula a variação mês a mês na contagem de pedidos para franqueados."""
    df_trend = df.groupby(['franqueado', 'ano_mes']).agg(total_pedidos=('numero_pedido', 'count')).reset_index()
    df_trend = df_trend.sort_values(by=['franqueado', 'ano_mes'])

    # Pega os últimos dois meses para cada franqueado
    df_last_two = df_trend.groupby('franqueado').tail(2)
    # Calcula a diferença no total de pedidos entre os últimos dois meses
    df_last_two['variacao'] = df_last_two.groupby('franqueado')['total_pedidos'].diff()
    # Filtra linhas onde a variacao é NaN (significa apenas um mês de dados)
    df_final = df_last_two.dropna(subset=['variacao'])
    df_final['variacao'] = df_final['variacao'].astype(int)
    return df_final[['franqueado', 'variacao']]

def export_excel(dataframe, sheet_name="Sheet1"):
    """Exporta um DataFrame pandas para um arquivo Excel em bytes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        dataframe.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output

# --- Função auxiliar para gerar todos os exports ---
def generate_all_exports(df_rank, df_decline, df_growth, df_monthly, df_suppliers_top, df_status_distribution):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_rank.to_excel(writer, sheet_name="Top Franqueados", index=False)
        df_decline.to_excel(writer, sheet_name="Queda Franqueados", index=False)
        df_growth.to_excel(writer, sheet_name="Crescimento Franqueados", index=False)
        df_monthly.to_excel(writer, sheet_name="Pedidos Mensais", index=False)
        df_suppliers_top.to_excel(writer, sheet_name="Top Fornecedores", index=False)
        df_status_distribution.to_excel(writer, sheet_name="Distribuicao Status", index=False)
    output.seek(0)
    return output

# --- FILTROS SIDEBAR ---
with st.sidebar:
    st.title("Filtros do Dashboard 📊") # Adicionado emoji

    min_overall_date = df_original["data_pedido"].min().date()
    max_overall_date = df_original["data_pedido"].max().date()

    # --- DATAS NO TOPO ---
    st.subheader("Período de Análise 🗓️") # Adicionado emoji

    # --- ALTERAÇÕES AQUI: Novas opções de seleção rápida de período ---
    quick_period_options = [
        "Personalizado",
        "Últimos 3 meses (vs. anterior)",
        "Últimos 6 meses (vs. anterior)",
        "Últimos 12 meses (vs. anterior)",
        "Ano Atual (YTD) vs. Ano Anterior"
    ]
    selected_quick_period = st.selectbox("Seleção Rápida de Período", quick_period_options)

    # Calculate dates based on quick selection
    current_date = date.today()

    # --- ALTERAÇÕES AQUI: Lógica para definir data_inicio e data_fim com base na seleção rápida ---
    if selected_quick_period == "Personalizado":
        start_date_default = st.session_state['data_inicio_selected']
        end_date_default = st.session_state['data_fim_selected']
    elif selected_quick_period == "Últimos 3 meses (vs. anterior)":
        end_date_default = current_date
        start_date_default = add_months(current_date, -3) + timedelta(days=1)
    elif selected_quick_period == "Últimos 6 meses (vs. anterior)":
        end_date_default = current_date
        start_date_default = add_months(current_date, -6) + timedelta(days=1)
    elif selected_quick_period == "Últimos 12 meses (vs. anterior)":
        end_date_default = current_date
        start_date_default = add_months(current_date, -12) + timedelta(days=1)
    elif selected_quick_period == "Ano Atual (YTD) vs. Ano Anterior":
        end_date_default = current_date
        start_date_default = date(current_date.year, 1, 1)

    # Ensure default dates are within overall data range
    start_date_default = max(min_overall_date, min(start_date_default, max_overall_date))
    end_date_default = max(min_overall_date, min(end_date_default, max_overall_date))


    data_inicio = st.date_input(
        "Data Inicial",
        value=start_date_default,
        min_value=min_overall_date,
        max_value=max_overall_date,
        key='data_inicio_input' # Unique key for widget
    )
    st.session_state['data_inicio_selected'] = data_inicio # Update session state

    min_date_allowed = add_months(data_inicio, 2)
    # Garante que min_date_allowed não seja maior que a data máxima geral de dados
    if min_date_allowed > max_overall_date:
        min_date_allowed = max_overall_date

    data_fim = st.date_input(
        "Data Final",
        value=end_date_default,
        min_value=min_date_allowed,
        max_value=max_overall_date,
        help=f"A data final deve ter no mínimo 3 meses de diferença da data inicial (a partir de {min_date_allowed.strftime('%d/%m/%Y')}).",
        key='data_fim_input' # Unique key for widget
    )
    st.session_state['data_fim_selected'] = data_fim # Update session state

    # --- VALIDAÇÃO DA SELEÇÃO DE DATAS (NÃO BLOQUEANTE) ---
    dt_data_inicio = pd.to_datetime(data_inicio)
    dt_data_fim = pd.to_datetime(data_fim)
    month_diff = (dt_data_fim.year - dt_data_inicio.year) * 12 + dt_data_fim.month - dt_data_inicio.month

    if month_diff < 2:
        st.warning("⚠️ **Período Insuficiente:** Por favor, selecione um intervalo de no mínimo **3 meses** para a análise (ex: de Janeiro até Março).")

    st.markdown("---")

    # --- OUTROS FILTROS ---
    st.subheader("Filtros Adicionais 🔍") # Adicionado emoji

    # Franqueados filter (Botões "Selecionar Todos/Limpar Seleção" REMOVIDOS)
    unique_franqueados = sorted(df_original["franqueado"].unique())
    franqueados = st.multiselect(
        "Selecione Franqueados",
        unique_franqueados,
        default=st.session_state['franqueados_selected'],
        key='franqueados_multiselect'
    )
    st.session_state['franqueados_selected'] = franqueados


    # Fornecedores filter (Botões "Selecionar Todos/Limpar Seleção" REMOVIDOS)
    unique_fornecedores = sorted(df_original["fornecedor"].unique())
    fornecedores = st.multiselect(
        "Selecione Fornecedores",
        unique_fornecedores,
        default=st.session_state['fornecedores_selected'],
        key='fornecedores_multiselect'
    )
    st.session_state['fornecedores_selected'] = fornecedores

    # Status filter (Botões "Selecionar Todos/Limpar Seleção" REMOVIDOS)
    unique_status = sorted(df_original["status"].unique())
    status = st.multiselect(
        "Selecione Status",
        unique_status,
        default=st.session_state['status_selected'],
        key='status_multiselect'
    )
    st.session_state['status_selected'] = status

    st.markdown("---")

    top_n = st.number_input(
        "Número de Itens nos Rankings",
        min_value=3, max_value=30, value=st.session_state['top_n_selected'], step=1,
        help="Selecione a quantidade de itens (franqueados/fornecedores) a serem exibidos nos gráficos de ranking.",
        key='top_n_input'
    )
    st.session_state['top_n_selected'] = top_n # Update session state

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

# --- Feedback para filtros vazios ---
if df_filtered.empty:
    st.warning("""
        ⚠️ **Nenhum dado encontrado!** Com os filtros selecionados, não há pedidos para exibir.
        Por favor, **ajuste suas seleções** de Franqueados, Fornecedores, Status ou o período de Datas para ver os resultados.
    """)
    st.stop()

df_active_franchisees = df_filtered[~df_filtered['franqueado'].str.contains(r'\[Excluído\]', case=False, na=False)]

# --- Cálculo para Deltas dos KPIs ---
# Determine previous period based on selected_quick_period
current_period_start_dt = pd.to_datetime(data_inicio)
current_period_end_dt = pd.to_datetime(data_fim)

# --- ALTERAÇÕES AQUI: Lógica para calcular o período anterior ---
if selected_quick_period == "Ano Atual (YTD) vs. Ano Anterior":
    # Mesmo período do ano passado (Year-to-Date)
    previous_data_inicio = current_period_start_dt.replace(year=current_period_start_dt.year - 1)
    previous_data_fim = current_period_end_dt.replace(year=current_period_end_dt.year - 1)
else:
    # Período anterior contíguo com a mesma duração
    current_period_duration = current_period_end_dt - current_period_start_dt
    previous_data_fim = current_period_start_dt - timedelta(days=1)
    previous_data_inicio = previous_data_fim - current_period_duration

df_previous_period = df_original[
    (df_original['data_pedido'] >= previous_data_inicio) &
    (df_original['data_pedido'] <= previous_data_fim)
]

# Apply same filters to previous period data
if franqueados:
    df_previous_period = df_previous_period[df_previous_period["franqueado"].isin(franqueados)]
if fornecedores:
    df_previous_period = df_previous_period[df_previous_period["fornecedor"].isin(fornecedores)]
if status:
    df_previous_period = df_previous_period[df_previous_period["status"].isin(status)]

df_active_franchisees_prev = df_previous_period[~df_previous_period['franqueado'].str.contains(r'\[Excluído\]', case=False, na=False)]

total_pedidos_kpi = len(df_filtered)
total_valor_kpi = df_filtered['valor_pedido'].sum()
active_franchisees_kpi = df_active_franchisees['franqueado'].nunique()

# KPIs do período anterior
total_pedidos_kpi_prev = len(df_previous_period) if not df_previous_period.empty else 0
total_valor_kpi_prev = df_previous_period['valor_pedido'].sum() if not df_previous_period.empty else 0
active_franchisees_kpi_prev = df_active_franchisees_prev['franqueado'].nunique() if not df_active_franchisees_prev.empty else 0

# Calcular deltas
# Usar None ou 0 para evitar divisão por zero quando o período anterior não tem dados
delta_pedidos = total_pedidos_kpi - total_pedidos_kpi_prev if total_pedidos_kpi_prev != 0 else None
delta_valor = total_valor_kpi - total_valor_kpi_prev if total_valor_kpi_prev != 0 else None
delta_franqueados = active_franchisees_kpi - active_franchisees_kpi_prev if active_franchisees_kpi_prev != 0 else None

# Formatar deltas
# O st.metric já lida com o texto e a seta. Se o delta for None, ele não mostra nada.
delta_pedidos_str = f"{delta_pedidos:,.0f}" if delta_pedidos is not None else None
delta_valor_str = f"R$ {delta_valor:,.2f}" if delta_valor is not None else None
delta_franqueados_str = f"{delta_franqueados:,.0f}" if delta_franqueados is not None else None


st.title("📦 Dashboard Analítico de Pedidos") # Adicionado emoji
col1, col2, col3, col_export = st.columns([1, 1, 1, 0.7])

with col1:
    st.metric("Total de Pedidos", f"{total_pedidos_kpi:,.0f}", delta=delta_pedidos_str)
with col2:
    st.metric("Valor Total", f"R$ {total_valor_kpi:,.2f}", delta=delta_valor_str)
with col3:
    st.metric("Franqueados Ativos", active_franchisees_kpi, delta=delta_franqueados_str)
with col_export:
    st.markdown(" ") # Espaçamento para alinhar o botão
    st.markdown(" ")
    # Botão de exportação que será habilitado após a geração dos DataFrames
    # O truque é ter um botão "invisível" que é clicado via código quando o botão visível é acionado.
    # Isso impede que o botão de download seja renderizado antes dos dados estarem prontos.
    if st.button("📥 Exportar Tudo (Excel)", help="Exporta os dados dos principais gráficos em um único arquivo Excel."):
        # Chamar a função de exportação com os DataFrames que serão populados nas abas
        excel_data = generate_all_exports(
            df_rank_for_export,
            df_decline_for_export,
            df_growth_for_export,
            df_monthly_for_export,
            df_suppliers_top_for_export,
            df_status_distribution_for_export
        )
        st.download_button(
            label="Download do Excel",
            data=excel_data,
            file_name="dados_dashboard_pedidos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_all_data_hidden" # Chave única, o botão de cima é o que o usuário clica
        )


st.markdown("---")

# --- ABAS ---
tab1, tab2 = st.tabs(["Análise de Franqueados", "Análise Geral e Fornecedores"])

# placeholders para dados que serão gerados nas abas para o export (mantidos para que generate_all_exports possa ser chamado)
df_rank_for_export = pd.DataFrame()
df_decline_for_export = pd.DataFrame()
df_growth_for_export = pd.DataFrame()
df_monthly_for_export = pd.DataFrame()
df_suppliers_top_for_export = pd.DataFrame()
df_status_distribution_for_export = pd.DataFrame()


with tab1:
    st.markdown(f"""<h4>🏪 Top {top_n} Franqueados por Quantidade de Pedidos</h4>""", unsafe_allow_html=True)

    df_rank = df_active_franchisees.groupby('franqueado')['numero_pedido'].count().reset_index(name='qtd_pedidos')
    df_rank = df_rank.sort_values(by='qtd_pedidos', ascending=False).head(top_n)
    df_rank_for_export = df_rank # Popula o DataFrame para exportação geral

    # Customizando dados de hover para melhor legibilidade
    fig_rank = px.bar(df_rank, x='franqueado', y='qtd_pedidos',
                      title=f"Top {top_n} Franqueados por Pedidos",
                      color='franqueado',
                      color_discrete_sequence=px.colors.qualitative.Set2,
                      hover_data={'qtd_pedidos': ':,0f'}) # Formata com separador de milhares

    st.plotly_chart(fig_rank, use_container_width=True)
    st.download_button("📥 Exportar Top Franqueados (Tabela Atual)", export_excel(df_rank, sheet_name="Top Franqueados"), file_name="rank_franqueados.xlsx")

    # --- Análise de Tendência ---
    df_trend = calculate_monthly_trend(df_active_franchisees)

    col_decline, col_growth = st.columns(2)
    with col_decline:
        st.markdown(f"""<h4>📉 Top {top_n} Franqueados com Tendência de Queda</h4>""", unsafe_allow_html=True)

        df_decline = df_trend[df_trend['variacao'] < 0].sort_values(by='variacao', ascending=True).head(top_n)
        df_decline_for_export = df_decline # Popula o DataFrame para exportação geral
        if not df_decline.empty:
            fig_decline = px.bar(df_decline, x='franqueado', y='variacao',
                                 title=f"Top {top_n} Franqueados com Maior Queda",
                                 color_discrete_sequence=['#FF6347'],
                                 hover_data={'variacao': ':,0f'}) # Formata com separador de milhares
            fig_decline.update_layout(yaxis_title="Variação (nº de pedidos)", xaxis_title="", xaxis_tickangle=-45)
            st.plotly_chart(fig_decline, use_container_width=True)
            st.download_button("📥 Exportar Queda (Tabela Atual)", export_excel(df_decline, sheet_name="Queda Franqueados"), file_name="queda_pedidos.xlsx")
        else:
            st.info("ℹ️ Nenhum franqueado apresentou **queda significativa** de pedidos no período selecionado.")

    with col_growth:
        st.markdown(f"""<h4>🔼 Top {top_n} Franqueados com Tendência de Crescimento</h4>""", unsafe_allow_html=True)

        df_growth = df_trend[df_trend['variacao'] > 0].sort_values(by='variacao', ascending=False).head(top_n)
        df_growth_for_export = df_growth # Popula o DataFrame para exportação geral

        if not df_growth.empty:
            fig_growth = px.bar(df_growth, x='franqueado', y='variacao',
                                 title=f"Top {top_n} Franqueados com Maior Crescimento",
                                 color_discrete_sequence=['#4682B4'],
                                 hover_data={'variacao': ':,0f'}) # Formata com separador de milhares
            fig_growth.update_layout(yaxis_title="Variação (nº de pedidos)", xaxis_title="", xaxis_tickangle=-45)
            st.plotly_chart(fig_growth, use_container_width=True)
            st.download_button("📥 Exportar Crescimento (Tabela Atual)", export_excel(df_growth, sheet_name="Crescimento Franqueados"), file_name="crescimento_pedidos.xlsx")
        else:
            st.info("ℹ️ Nenhum franqueado apresentou **crescimento significativo** de pedidos no período selecionado.")

with tab2:
    st.markdown("""<h4>📅 Total de Pedidos por Mês</h4>""", unsafe_allow_html=True)

    df_monthly = df_filtered.groupby('ano_mes').agg(total_pedidos=('numero_pedido', 'count')).reset_index()
    df_monthly_for_export = df_monthly # Popula o DataFrame para exportação geral
    fig_trend = px.line(df_monthly, x='ano_mes', y='total_pedidos', markers=True,
                         title="Evolução Mensal de Pedidos",
                         color_discrete_sequence=px.colors.qualitative.Plotly,
                         hover_data={'total_pedidos': ':,0f'}) # Formata com separador de milhares
    fig_trend.update_layout(xaxis_title="Mês", yaxis_title="Quantidade de Pedidos")
    st.plotly_chart(fig_trend, use_container_width=True)
    st.download_button("📥 Exportar Pedidos Mensais (Tabela Atual)", export_excel(df_monthly), file_name="pedidos_mensais.xlsx")

    st.markdown("---")

    st.markdown(f"""<h4>🏆 Top {top_n} Fornecedores por Valor de Pedido</h4>""", unsafe_allow_html=True)

    df_suppliers = df_filtered.groupby('fornecedor').agg(valor_total=('valor_pedido', 'sum')).reset_index()
    df_suppliers_top = df_suppliers.sort_values(by='valor_total', ascending=False).head(top_n)
    df_suppliers_top_for_export = df_suppliers_top # Popula o DataFrame para exportação geral

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
    st.download_button("📥 Exportar Top Fornecedores (Tabela Atual)", export_excel(df_suppliers_top), file_name="rank_fornecedores.xlsx")

    st.markdown("---")

    # --- NOVA ANÁLISE: Distribuição de Pedidos por Status ---
    st.markdown(f"""<h4>📊 Distribuição de Pedidos por Status</h4>""", unsafe_allow_html=True)

    # Lista dos status que você deseja exibir
    status_desejados = ["FINALIZADO", "CANCELADO", "PEDIDO ENTREGUE", "EM PROCESSAMENTO"]

    # Filtra o DataFrame para incluir apenas os status desejados
    df_status_for_chart = df_filtered[df_filtered["status"].isin(status_desejados)].copy()

    # Verificar se o DataFrame ainda tem dados após o filtro de status específico
    if df_status_for_chart.empty:
        st.info("ℹ️ Nenhum pedido encontrado para os **status desejados** neste período. Por favor, ajuste os filtros gerais.")
    else:
        df_status_distribution = df_status_for_chart.groupby('status').agg(count_pedidos=('numero_pedido', 'count')).reset_index()
        df_status_distribution['percentage'] = (df_status_distribution['count_pedidos'] / df_status_distribution['count_pedidos'].sum()) * 100
        df_status_distribution_for_export = df_status_distribution # Popula o DataFrame para exportação geral

        fig_status = px.pie(df_status_distribution, values='count_pedidos', names='status',
                             title="Distribuição de Pedidos por Status",
                             hole=.3, # Cria um gráfico de donut (rosca)
                             color_discrete_sequence=px.colors.qualitative.Pastel,
                             hover_data={'count_pedidos': ':,0f', 'percentage': ':.2f'})
        fig_status.update_traces(textinfo='percent+label', pull=[0.05]*len(df_status_distribution)) # Mostra percentual e rótulo, puxa ligeiramente as fatias
        fig_status.update_layout(showlegend=True) # Garante que a legenda esteja visível
        st.plotly_chart(fig_status, use_container_width=True)
        st.download_button("📥 Exportar Distribuição de Status (Tabela Atual)", export_excel(df_status_distribution), file_name="distribuicao_status.xlsx")

# --- Rodapé ---
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: grey;">
        Dashboard Analítico de Pedidos | Última Atualização: Julho de 2025
    </div>
    """,
    unsafe_allow_html=True
)