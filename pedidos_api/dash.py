import streamlit as st
import pandas as pd
import plotly.express as px
import io
from datetime import timedelta
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import numpy as np

# Assumindo que seu arquivo db.py com get_conn e put_conn existe
from db import get_conn, put_conn

st.set_page_config(page_title="Dashboard de Pedidos", layout="wide", initial_sidebar_state="expanded")

# Estilo CSS para tooltips personalizados
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

        # Exclusão do B2B
        df['franqueado'] = df['franqueado'].astype(str)
        df = df[~df['franqueado'].str.lower().str.startswith("b2b")]

        # Conversões que não dependem de filtros são feitas aqui
        df['data_pedido'] = pd.to_datetime(df['data_pedido'])
        df['ano'] = df['data_pedido'].dt.year
        df['mes'] = df['data_pedido'].dt.month
        df['ano_mes'] = df['data_pedido'].dt.to_period('M').astype(str)
        # Adicionar data da primeira compra para Cohort
        df['data_primeira_compra'] = df.groupby('franqueado')['data_pedido'].transform('min')
        df['mes_primeira_compra'] = df['data_primeira_compra'].dt.to_period('M').astype(str)
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
    
    # --- RANKING CONFIGURÁVEL ---
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
tab1, tab2, tab4 = st.tabs(["Análise de Franqueados", "Análise Geral e Fornecedores", "Análises Avançadas"])


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


with tab4:
    st.header("Análises Avançadas de Franqueados")

    st.markdown("""
    ---
    ### 🤝 Análise de Cohorts (Retenção de Franqueados)
    <span class="tooltip"> ℹ️
        <span class="tooltiptext">
            Analisa a retenção de franqueados ao longo do tempo, agrupando-os pelo mês de sua primeira compra.
            Um valor de 100% no "Mês 0" indica a coorte original, e os valores subsequentes mostram a porcentagem
            de franqueados daquela coorte que ainda fizeram pedidos em meses posteriores.
        </span>
    </span>
    """, unsafe_allow_html=True)

    if df_franqueados_ativos['data_primeira_compra'].nunique() < 2 or df_franqueados_ativos['ano_mes'].nunique() < 2:
        st.info("São necessários dados de múltiplos meses e franqueados para realizar a Análise de Cohorts.")
    else:
        df_cohort = df_franqueados_ativos.copy()
        
        df_cohort['periodo_atividade'] = (
            df_cohort['data_pedido'].dt.to_period('M') - 
            df_cohort['data_primeira_compra'].dt.to_period('M')
        ).apply(lambda x: x.n)

        # 1. Contar franqueados únicos E COLETAR SUAS SIGLAS para o tooltip
        cohort_details = df_cohort.groupby(['mes_primeira_compra', 'periodo_atividade']).agg(
            num_franqueados=('franqueado', 'nunique'),
            lista_franqueados=('franqueado', lambda x: ', '.join(sorted(x.unique()))) # Coleta as siglas únicas e as ordena
        ).reset_index()
        
        # Opcional: Limitar o número de siglas exibidas no tooltip se for muito grande
        # Se 75 franqueados, a lista pode ser imensa. Pode ser melhor mostrar "10 franqueados: Sigla1, Sigla2..."
        # Ou "Total: 10 franqueados." e as siglas em uma linha separada ou em outra parte do tooltip.
        # Por simplicidade, estou juntando todas as siglas aqui.
        
        cohort_details = cohort_details.rename(columns={'num_franqueados': 'num_franqueados_no_periodo'})

        # 2. Calcular o tamanho da coorte inicial (Mês 0)
        cohort_sizes = cohort_details[cohort_details['periodo_atividade'] == 0][['mes_primeira_compra', 'num_franqueados_no_periodo']]
        cohort_sizes = cohort_sizes.rename(columns={'num_franqueados_no_periodo': 'tamanho_coorte'})

        # 3. Juntar e calcular a retenção
        cohort_retention_data = pd.merge(cohort_details, cohort_sizes, on='mes_primeira_compra')
        cohort_retention_data['retencao'] = (cohort_retention_data['num_franqueados_no_periodo'] / cohort_retention_data['tamanho_coorte']) * 100

        # Pivotar apenas para a porcentagem de retenção para o heatmap
        retention_pivot = cohort_retention_data.pivot_table(
            index='mes_primeira_compra',
            columns='periodo_atividade',
            values='retencao'
        )
        
        # Pivotar para as listas de franqueados para o tooltip
        franqueados_pivot = cohort_retention_data.pivot_table(
            index='mes_primeira_compra',
            columns='periodo_atividade',
            values='lista_franqueados',
            aggfunc=lambda x: x.iloc[0] if not x.empty else '' # Pegar o valor único da lista, ou vazio
        )
        
        # Ordenar os meses da primeira compra para ambos os pivots
        retention_pivot = retention_pivot.reindex(sorted(retention_pivot.index), axis=0)
        franqueados_pivot = franqueados_pivot.reindex(sorted(franqueados_pivot.index), axis=0)

        num_cohorts = retention_pivot.shape[0]
        altura_base = 300 
        altura_por_linha = 40 
        altura_final = max(altura_base, num_cohorts * altura_por_linha)

        color_scale = "Greens" 

        st.markdown("##### Tabela de Retenção de Cohorts (%):")
        st.dataframe(retention_pivot.style.format("{:.1f}%"), use_container_width=True)

        fig_cohort = px.imshow(retention_pivot,
            text_auto=".1f", 
            aspect="auto",
            color_continuous_scale=color_scale, 
            title="Retenção de Franqueados por Cohort",
            height=altura_final 
        )
        fig_cohort.update_xaxes(side="top", title="Meses Desde a Primeira Compra")
        fig_cohort.update_yaxes(title="Mês da Primeira Compra da Coorte")
        
        # IMPORTANT: Adicionar os dados da lista de franqueados ao hovertemplate usando um customdata
        # plotly.express não permite customdata diretamente no imshow de forma trivial
        # Precisamos construir o trace manualmente ou passar os dados via fig.add_trace
        # Uma alternativa mais simples é usar text (se for apenas para uma célula) ou passar para o hovertemplate
        
        # A forma mais elegante é usar 'customdata' em Plotly Go para ter acesso no hovertemplate
        # px.imshow não expõe o 'customdata' de forma direta como outros gráficos
        # Uma alternativa é injetar no hovertemplate via string format (menos robusto) ou
        # fazer um Plotly Graph Objects (go) em vez de px.imshow.

        # Adaptando para o px.imshow: a 'text_auto' não é a mesma coisa que 'customdata' para o hovertemplate.
        # Precisamos que a 'lista_franqueados' esteja disponível no mesmo dataframe que o px.imshow está usando para 'values'.
        # Isso significa que o dataframe que alimenta o imshow deve ter a coluna 'lista_franqueados'.
        # Infelizmente, px.imshow é mais limitado para isso.

        # ALTERNATIVA PARA px.imshow: Criar a string do tooltip diretamente
        # Isso é um pouco menos elegante, mas funcional com px.imshow
        
        # Vamos criar uma matriz de strings para o hovertext
        hover_text_matrix = franqueados_pivot.applymap(lambda x: f"Franqueados: {x}" if x else "Nenhum Franqueado")
        
        fig_cohort = px.imshow(
            retention_pivot,
            text_auto=".1f", 
            aspect="auto",
            color_continuous_scale=color_scale, 
            title="Retenção de Franqueados por Cohort",
            height=altura_final,
            # Injetamos o hover_name e hover_data para o hovertemplate.
            # px.imshow não suporta hover_data diretamente para um dataframe pivotado como entrada principal.
            # A solução mais robusta é usar go.Heatmap ou criar o hovertemplate com base em dados pré-formatados.
            # Para manter a simplicidade com px.imshow, usaremos a técnica de 'text' ou 'customdata' que px.imshow
            # não expõe facilmente.
            # A melhor forma aqui é criar a customdata e adicionar via fig.data[0].customdata.
        )
        
        # Para adicionar customdata no px.imshow (requer um truque ou go.Heatmap):
        # px.imshow cria um objeto go.Heatmap por baixo dos panos.
        # Podemos acessar e modificar seu customdata.
        fig_cohort.data[0].customdata = franqueados_pivot.values
        
        # Atualizar o hovertemplate para usar o customdata
        fig_cohort.update_traces(
            hovertemplate=(
                "Mês da Coorte: %{y}<br>" +
                "Meses de Atividade: %{x}<br>" +
                "Retenção: %{z:.1f}%<br>" +
                "Franqueados Ativos: %{customdata}<extra></extra>" # Use %{customdata} aqui
            )
        )

        st.plotly_chart(fig_cohort, use_container_width=True)
        st.download_button("📥 Exportar Cohorts", export_excel(retention_pivot), file_name="analise_cohorts.xlsx")
