import io
import os
from datetime import date, timedelta
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from db import get_conn, put_conn

st.set_page_config(page_title="Dashboard Magnólia - Supply Team", layout="wide", initial_sidebar_state="expanded")
load_dotenv()

APP_TITLE = "Dashboard Magnólia"
DEFAULT_TOP_N = 10
MIN_MONTH_DIFF_FOR_ANALYSIS = 2
B2B_FRANCHISEE_PREFIX = "b2b"
EXCLUDED_FRANCHISEE_PATTERN = r'\[Excluído\]'
SHEET_TOP_FRANCHISEES = "Top Franqueados"
SHEET_DECLINE_FRANCHISEES = "Queda Franqueados"
SHEET_GROWTH_FRANCHISEES = "Crescimento Franqueados"
SHEET_MONTHLY_ORDERS = "Pedidos Mensais"
SHEET_TOP_SUPPLIERS = "Top Fornecedores"
SHEET_STATUS_DISTRIBUTION = "Distribuicao Status"

# Css in-line
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
/* Style to reduce multiselect height */
.stMultiSelect div[data-baseweb="select"] > div:first-child {
    max-height: 150px;
    overflow-y: auto;
}
</style>
""", unsafe_allow_html=True)

# Algumas funções auxiliares,
def add_months(sourcedate: date, months: int) -> date:
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)

# Exclui franqueados B2B, carrega os dados dos pedidos do nosso banco de dados e faz a primeira limpeza
@st.cache_data
def load_data() -> pd.DataFrame:
    loading_message_placeholder = st.empty()
    loading_message_placeholder.info("⌛ Carregando dados do banco de dados... Isso pode levar alguns segundos.")
    conn = None
    try:
        conn = get_conn()
        query = "SELECT * FROM pedidos;"
        df = pd.read_sql(query, conn)

        df['franqueado'] = df['franqueado'].astype(str)
        df = df[~df['franqueado'].str.lower().str.startswith(B2B_FRANCHISEE_PREFIX)]

        df['data_pedido'] = pd.to_datetime(df['data_pedido'])
        df['ano'] = df['data_pedido'].dt.year
        df['mes'] = df['data_pedido'].dt.month
        df['ano_mes'] = df['data_pedido'].dt.to_period('M').astype(str)

        loading_message_placeholder.empty()
        return df
    finally:
        if conn:
            put_conn(conn)

# calcula a varição nos pedidos
def calculate_monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    df_trend = df.groupby(['franqueado', 'ano_mes']).agg(total_pedidos=('numero_pedido', 'count')).reset_index()
    df_trend = df_trend.sort_values(by=['franqueado', 'ano_mes'])
    df_last_two = df_trend.groupby('franqueado').tail(2)
    df_last_two['variacao'] = df_last_two.groupby('franqueado')['total_pedidos'].diff()
    df_final = df_last_two.dropna(subset=['variacao'])
    df_final['variacao'] = df_final['variacao'].astype(int)
    return df_final[['franqueado', 'variacao']]

def calculate_kpis(df: pd.DataFrame, df_active: pd.DataFrame) -> dict:
    total_pedidos = len(df)
    total_valor = df['valor_pedido'].sum()
    active_franchisees = df_active['franqueado'].nunique()
    # Calcular o ticket médio apenas se houver pedidos para evitar divisão por zero
    ticket_medio = total_valor / total_pedidos if total_pedidos > 0 else 0
    return {
        'total_pedidos': total_pedidos,
        'total_valor': total_valor,
        'active_franchisees': active_franchisees,
        'ticket_medio': ticket_medio
    }

def get_comparison_period_dates(
    current_start: date,
    current_end: date,
    selected_quick_period: str,
    df_min_date: date,
    df_max_date: date
) -> tuple[date, date]:

    current_period_duration = current_end - current_start

    if selected_quick_period == "Ano Atual (YTD) vs. Ano Anterior":
        previous_start = current_start.replace(year=current_start.year - 1)
        previous_end = current_end.replace(year=current_end.year - 1)
    else:
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - current_period_duration

    previous_start_adjusted = max(df_min_date, previous_start)
    previous_end_adjusted = min(df_max_date, previous_end)

    if previous_start_adjusted > previous_end_adjusted:
        return date(1900, 1, 1), date(1900, 1, 1)
    return previous_start_adjusted, previous_end_adjusted

#Função para aplicar filtros
def apply_data_filters(df: pd.DataFrame, start_date: date, end_date: date,
                         franchisees: list, suppliers: list, statuses: list) -> pd.DataFrame:
    df_filtered = df[
        (df['data_pedido'] >= pd.to_datetime(start_date)) &
        (df['data_pedido'] <= pd.to_datetime(end_date))
    ].copy()

    if franchisees:
        df_filtered = df_filtered[df_filtered["franqueado"].isin(franchisees)]
    if suppliers:
        df_filtered = df_filtered[df_filtered["fornecedor"].isin(suppliers)]
    if statuses:
        df_filtered = df_filtered[df_filtered["status"].isin(statuses)]
    return df_filtered

if 'initialized' not in st.session_state:
    st.session_state['franqueados_selected'] = []
    st.session_state['fornecedores_selected'] = []
    st.session_state['status_selected'] = []
    st.session_state['data_inicio_selected'] = None
    st.session_state['data_fim_selected'] = None
    st.session_state['top_n_selected'] = DEFAULT_TOP_N
    st.session_state['initialized'] = True

with st.spinner('Carregando dados do banco de dados...'):
    df_original = load_data()

if st.session_state['data_inicio_selected'] is None:
    st.session_state['data_inicio_selected'] = df_original["data_pedido"].min().date()
if st.session_state['data_fim_selected'] is None:
    st.session_state['data_fim_selected'] = df_original["data_pedido"].max().date()

# --- 11. Filtros do sidebar
with st.sidebar:
    st.title("Filtros do Dashboard 📊")

    min_overall_date = df_original["data_pedido"].min().date()
    max_overall_date = df_original["data_pedido"].max().date()

    st.subheader("Período de Análise 🗓️")
    quick_period_options = [
        "Personalizado",
        "Últimos 3 meses (vs. anterior)",
        "Últimos 6 meses (vs. anterior)",
        "Últimos 12 meses (vs. anterior)",
        "Ano Atual (YTD) vs. Ano Anterior"
    ]
    selected_quick_period = st.selectbox("Seleção Rápida de Período", quick_period_options)

    current_date = date.today()

    # Determinamos os valores inciais de acordo com as datas pré-selecionadas
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


    data_inicio = start_date_default
    data_fim = end_date_default

    if selected_quick_period == "Personalizado":
        data_inicio = st.date_input(
            "Data Inicial",
            value=start_date_default,
            min_value=min_overall_date,
            max_value=max_overall_date,
            key='data_inicio_input'
        )
        st.session_state['data_inicio_selected'] = data_inicio

        min_date_allowed_for_end = add_months(data_inicio, MIN_MONTH_DIFF_FOR_ANALYSIS)
        if min_date_allowed_for_end > max_overall_date:
            min_date_allowed_for_end = max_overall_date  # Cap at max overall date

        data_fim = st.date_input(
            "Data Final",
            value=end_date_default,
            min_value=min_date_allowed_for_end,
            max_value=max_overall_date,
            help=f"A data final deve ter no mínimo {MIN_MONTH_DIFF_FOR_ANALYSIS + 1} meses de diferença da data inicial (a partir de {min_date_allowed_for_end.strftime('%d/%m/%Y')}).",
            key='data_fim_input'
        )
        st.session_state['data_fim_selected'] = data_fim

    # Validate date selection (non-blocking warning)
    dt_data_inicio_check = pd.to_datetime(data_inicio)
    dt_data_fim_check = pd.to_datetime(data_fim)
    month_diff_check = (dt_data_fim_check.year - dt_data_inicio_check.year) * 12 + dt_data_fim_check.month - dt_data_inicio_check.month

    if month_diff_check < MIN_MONTH_DIFF_FOR_ANALYSIS:
        st.warning(f"⚠️ **Período Insuficiente:** Para análises de tendência, selecione um intervalo de no mínimo **{MIN_MONTH_DIFF_FOR_ANALYSIS + 1} meses**.")

    st.markdown("---")

    st.subheader("Filtros Adicionais 🔍")
    unique_franqueados = sorted(df_original["franqueado"].unique())
    franqueados = st.multiselect(
        "Selecione Franqueados",
        unique_franqueados,
        default=st.session_state['franqueados_selected'],
        key='franqueados_multiselect'
    )
    st.session_state['franqueados_selected'] = franqueados

    unique_fornecedores = sorted(df_original["fornecedor"].unique())
    fornecedores = st.multiselect(
        "Selecione Fornecedores",
        unique_fornecedores,
        default=st.session_state['fornecedores_selected'],
        key='fornecedores_multiselect'
    )
    st.session_state['fornecedores_selected'] = fornecedores

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
    st.session_state['top_n_selected'] = top_n

    st.markdown("---")

# Usando a nova função para aplicar filtros
df_filtered = apply_data_filters(df_original, data_inicio, data_fim, franqueados, fornecedores, status)

if df_filtered.empty:
    st.warning("""
        ⚠️ **Nenhum dado encontrado!** Com os filtros selecionados, não há pedidos para exibir.
        Por favor, **ajuste suas seleções** de Franqueados, Fornecedores, Status ou o período de Datas para ver os resultados.
    """)
    if st.button("Limpar Todos os Filtros"):
        st.session_state['franqueados_selected'] = []
        st.session_state['fornecedores_selected'] = []
        st.session_state['status_selected'] = []
        st.session_state['data_inicio_selected'] = df_original["data_pedido"].min().date()
        st.session_state['data_fim_selected'] = df_original["data_pedido"].max().date()
        st.experimental_rerun()  # Reinicia o app com filtros limpos
    st.stop()

df_active_franchisees = df_filtered[~df_filtered['franqueado'].str.contains(EXCLUDED_FRANCHISEE_PATTERN, case=False, na=False)].copy()

#Calcula o KPI para a data atual
current_kpis = calculate_kpis(df_filtered, df_active_franchisees)

# Calcula o KPI para uma data prévia
previous_data_inicio_adj, previous_data_fim_adj = get_comparison_period_dates(
    data_inicio, data_fim, selected_quick_period,
    df_original["data_pedido"].min().date(), df_original["data_pedido"].max().date()
)

# Usando a nova função para aplicar filtros no período anterior
df_previous_period = apply_data_filters(df_original, previous_data_inicio_adj, previous_data_fim_adj,
                                        franqueados, fornecedores, status)


df_active_franchisees_prev = df_previous_period[~df_previous_period['franqueado'].str.contains(EXCLUDED_FRANCHISEE_PATTERN, case=False, na=False)].copy()
previous_kpis = calculate_kpis(df_previous_period, df_active_franchisees_prev)

# Calculate and format deltas for display
delta_pedidos = current_kpis['total_pedidos'] - previous_kpis['total_pedidos']
delta_valor = current_kpis['total_valor'] - previous_kpis['total_valor']
delta_franqueados = current_kpis['active_franchisees'] - previous_kpis['active_franchisees']
delta_ticket_medio = current_kpis['ticket_medio'] - previous_kpis['ticket_medio']

# Ajuste nos deltas para exibir "N/A" ou None para st.metric
display_delta_pedidos = f"{delta_pedidos:,.0f}" if previous_kpis['total_pedidos'] != 0 else None
display_delta_valor = f"R$ {delta_valor:,.2f}" if previous_kpis['total_valor'] != 0 else None
display_delta_franqueados = f"{delta_franqueados:,.0f}" if previous_kpis['active_franchisees'] != 0 else None
display_delta_ticket_medio = f"R$ {delta_ticket_medio:,.2f}" if previous_kpis['total_pedidos'] != 0 else None


st.title(APP_TITLE)

# Display current and comparison period information
data_inicio_fmt = data_inicio.strftime("%d/%m/%Y")
data_fim_fmt = data_fim.strftime("%d/%m/%Y")
current_period_description = f"Dados do período: **{data_inicio_fmt}** a **{data_fim_fmt}**."

comparison_description = ""
if previous_data_inicio_adj <= previous_data_fim_adj and previous_kpis['total_pedidos'] > 0:
    previous_data_inicio_fmt = previous_data_inicio_adj.strftime("%d/%m/%Y")
    previous_data_fim_fmt = previous_data_fim_adj.strftime("%d/%m/%Y")
    period_type = "ano anterior" if selected_quick_period == "Ano Atual (YTD) vs. Ano Anterior" else "período anterior"
    comparison_description = f"Comparado com: **{previous_data_inicio_fmt}** a **{previous_data_fim_fmt}** ({period_type})."

st.info(f"{current_period_description} {comparison_description}")

# Adicionado mais uma coluna para o Ticket Médio
col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

with col1:
    st.metric("Total de Pedidos", f"{current_kpis['total_pedidos']:,.0f}", delta=display_delta_pedidos)
with col2:
    st.metric("Valor Total", f"R$ {current_kpis['total_valor']:,.2f}", delta=display_delta_valor)
with col3:
    st.metric("Franqueados Ativos", current_kpis['active_franchisees'], delta=display_delta_franqueados)
with col4:
    st.metric("Ticket Médio", f"R$ {current_kpis['ticket_medio']:,.2f}", delta=display_delta_ticket_medio)


st.markdown("---")

# Aqui definimos as abas do nosso sistema
tab1, tab2 = st.tabs(["Análise de Franqueados", "Análise Geral e Fornecedores"])

with tab1:
    st.subheader(f"🏪 Top {top_n} Franqueados por Quantidade de Pedidos")
    df_rank = df_active_franchisees.groupby('franqueado')['numero_pedido'].count().reset_index(name='qtd_pedidos')
    df_rank = df_rank.sort_values(by='qtd_pedidos', ascending=False).head(top_n)

    fig_rank = px.bar(df_rank, x='franqueado', y='qtd_pedidos',
                      title=f"Top {top_n} Franqueados por Pedidos",
                      color='franqueado',
                      color_discrete_sequence=["#5885FF"],
                      hover_data={'qtd_pedidos': ':,0f'})
    st.plotly_chart(fig_rank, use_container_width=True)

    # NOVO: Top N Franqueados por Ticket Médio
    st.markdown("---")
    st.subheader(f"💵 Top {top_n} Franqueados por Ticket Médio")
    # Calcular ticket médio por franqueado
    df_ticket_medio_franqueado = df_active_franchisees.groupby('franqueado').agg(
        total_valor=('valor_pedido', 'sum'),
        total_pedidos=('numero_pedido', 'count')
    ).reset_index()
    df_ticket_medio_franqueado['ticket_medio'] = df_ticket_medio_franqueado['total_valor'] / df_ticket_medio_franqueado['total_pedidos']
    df_ticket_medio_franqueado = df_ticket_medio_franqueado.sort_values(by='ticket_medio', ascending=False).head(top_n)

    if not df_ticket_medio_franqueado.empty:
        fig_ticket_medio = px.bar(df_ticket_medio_franqueado, x='franqueado', y='ticket_medio',
                                  title=f"Top {top_n} Franqueados por Ticket Médio",
                                  color='franqueado',
                                  color_discrete_sequence=["#2ca02c"],  # Cor para ticket médio
                                  hover_data={'ticket_medio': ':,.2f', 'total_pedidos': ':,0f', 'total_valor': ':,.2f'})
        fig_ticket_medio.update_layout(yaxis_title="Ticket Médio (R$)", xaxis_title="", xaxis_tickangle=-45)
        st.plotly_chart(fig_ticket_medio, use_container_width=True)
    else:
        st.info("ℹ️ Nenhum dado para calcular o ticket médio por franqueado no período selecionado.")

    # --- Trend Analysis ---
    st.markdown("---")  # Separator for trend section
    st.subheader("Análise de Tendência de Pedidos (Mês a Mês)")
    df_trend = calculate_monthly_trend(df_active_franchisees)

    col_decline, col_growth = st.columns(2)
    with col_decline:
        st.markdown(f"<h5>📉 Top {top_n} Franqueados com Tendência de Queda</h5>", unsafe_allow_html=True)
        df_decline = df_trend[df_trend['variacao'] < 0].sort_values(by='variacao', ascending=True).head(top_n)
        if not df_decline.empty:
            fig_decline = px.bar(df_decline, x='franqueado', y='variacao',
                                 title=f"Top {top_n} Franqueados com Maior Queda",
                                 color_discrete_sequence=['#FF6347'],
                                 hover_data={'variacao': ':,0f'})
            fig_decline.update_layout(yaxis_title="Variação (nº de pedidos)", xaxis_title="", xaxis_tickangle=-45)
            st.plotly_chart(fig_decline, use_container_width=True)
        else:
            st.info("ℹ️ Nenhum franqueado apresentou **queda significativa** de pedidos no período selecionado.")

    with col_growth:
        st.markdown(f"<h5>🔼 Top {top_n} Franqueados com Tendência de Crescimento</h5>", unsafe_allow_html=True)
        df_growth = df_trend[df_trend['variacao'] > 0].sort_values(by='variacao', ascending=False).head(top_n)
        if not df_growth.empty:
            fig_growth = px.bar(df_growth, x='franqueado', y='variacao',
                                 title=f"Top {top_n} Franqueados com Maior Crescimento",
                                 color_discrete_sequence=['#4682B4'],
                                 hover_data={'variacao': ':,0f'})
            fig_growth.update_layout(yaxis_title="Variação (nº de pedidos)", xaxis_title="", xaxis_tickangle=-45)
            st.plotly_chart(fig_growth, use_container_width=True)
        else:
            st.info("ℹ️ Nenhum franqueado apresentou **crescimento significativo** de pedidos no período selecionado.")

with tab2:
    st.subheader("📅 Total de Pedidos por Mês")
    df_monthly = df_filtered.groupby('ano_mes').agg(total_pedidos=('numero_pedido', 'count')).reset_index()
    fig_trend = px.line(df_monthly, x='ano_mes', y='total_pedidos', markers=True,
                        title="Evolução Mensal de Pedidos",
                        color_discrete_sequence=px.colors.qualitative.Plotly,
                        hover_data={'total_pedidos': ':,0f'})
    fig_trend.update_layout(xaxis_title="Mês", yaxis_title="Quantidade de Pedidos")
    st.plotly_chart(fig_trend, use_container_width=True)

    st.markdown("---")

    st.subheader(f"🏆 Top {top_n} Fornecedores por Valor de Pedido")
    df_suppliers = df_filtered.groupby('fornecedor').agg(valor_total=('valor_pedido', 'sum')).reset_index()
    df_suppliers_top = df_suppliers.sort_values(by='valor_total', ascending=False).head(top_n)
    fig_suppliers = px.bar(
        df_suppliers_top,
        x='fornecedor',
        y='valor_total',
        title=f"Top {top_n} Fornecedores por Faturamento",
        text_auto='.2s',
        labels={'valor_total': 'Valor Total (R$)'},
        hover_data={'valor_total': ':,.2f'}
    )
    fig_suppliers.update_traces(textposition='outside')
    fig_suppliers.update_layout(xaxis_title="Fornecedor", yaxis_title="Valor Total (R$)")
    st.plotly_chart(fig_suppliers, use_container_width=True)

    st.markdown("---")

    st.subheader("📊 Distribuição de Pedidos por Status")
    desired_statuses = ["FINALIZADO", "CANCELADO", "PEDIDO ENTREGUE", "EM PROCESSAMENTO"]
    df_status_for_chart = df_filtered[df_filtered["status"].isin(desired_statuses)].copy()

    if df_status_for_chart.empty:
        st.info("ℹ️ Nenhum pedido encontrado para os **status desejados** neste período. Por favor, ajuste os filtros gerais.")
    else:
        df_status_distribution = df_status_for_chart.groupby('status').agg(count_pedidos=('numero_pedido', 'count')).reset_index()
        df_status_distribution['percentage'] = (df_status_distribution['count_pedidos'] / df_status_distribution['count_pedidos'].sum()) * 100

        fig_status = px.pie(df_status_distribution, values='count_pedidos', names='status',
                            title="Distribuição de Pedidos por Status",
                            hole=.3,
                            color_discrete_sequence=px.colors.qualitative.Pastel,
                            hover_data={'count_pedidos': ':,0f', 'percentage': ':.2f'})
        fig_status.update_traces(textinfo='percent+label', pull=[0.05] * len(df_status_distribution))
        fig_status.update_layout(showlegend=True)
        st.plotly_chart(fig_status, use_container_width=True)

# --- Footer ---
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: grey;">
        Dashboard Analítico de Pedidos | Versão 1.0.1 | Última Atualização: Julho de 2025
    </div>
    """,
    unsafe_allow_html=True
)