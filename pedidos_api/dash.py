import streamlit as st
import pandas as pd
import plotly.express as px
from db import get_conn, put_conn
import io  # Para exportação Excel

st.set_page_config(page_title="Dashboard de Pedidos", layout="wide", initial_sidebar_state="expanded")

# Estilo CSS (mantido)
st.markdown("""...""", unsafe_allow_html=True)

# Conexão com o banco
conn = get_conn()
query = "SELECT * FROM pedidos;"
df = pd.read_sql(query, conn)
put_conn(conn)

# Adiciona coluna 'estado' se não existir (ajuste conforme necessário)
if 'estado' not in df.columns:
    df['estado'] = "N/D"

# Processamento de datas
df['data_pedido'] = pd.to_datetime(df['data_pedido'])
df['ano'] = df['data_pedido'].dt.year
df['mes'] = df['data_pedido'].dt.month
df['ano_mes'] = df['data_pedido'].dt.to_period('M').astype(str)

# Filtros
with st.sidebar:
    st.title("Filtros")
    franqueados = st.multiselect("Franqueado", df["franqueado"].unique())
    fornecedores = st.multiselect("Fornecedor", df["fornecedor"].unique())
    status = st.multiselect("Status", df["status"].unique())
    anos = st.multiselect("Ano", sorted(df["ano"].unique()))
    meses = st.multiselect("Mês", sorted(df["mes"].unique()))
    estados = st.multiselect("Estado", sorted(df["estado"].unique()))
    data_inicio = st.date_input("Data inicial", df["data_pedido"].min())
    data_fim = st.date_input("Data final", df["data_pedido"].max())
    st.markdown("---")

# Aplicando filtros
if franqueados:
    df = df[df["franqueado"].isin(franqueados)]
if fornecedores:
    df = df[df["fornecedor"].isin(fornecedores)]
if status:
    df = df[df["status"].isin(status)]
if anos:
    df = df[df["ano"].isin(anos)]
if meses:
    df = df[df["mes"].isin(meses)]
if estados:
    df = df[df["estado"].isin(estados)]

df = df[(df['data_pedido'] >= pd.to_datetime(data_inicio)) & (df['data_pedido'] <= pd.to_datetime(data_fim))]

# Franqueados ativos
df_franqueados_ativos = df[~df['franqueado'].str.contains(r'\[Excluído\]', case=False, na=False)]

# Função auxiliar: exportar Excel
def export_excel(dataframe):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        dataframe.to_excel(writer, index=False)
    output.seek(0)
    return output

# KPIs
st.title("📦 Dashboard Analítico de Pedidos")
col1, col2, col3 = st.columns(3)
col1.metric("Total de Pedidos", len(df))
col2.metric("Valor Total", f"R${df['valor_pedido'].sum():,.2f}")
col3.metric("Franqueados Ativos", df_franqueados_ativos['franqueado'].nunique())
st.markdown("---")

# Gráfico: Total de Pedidos por Mês
st.subheader("📅 Total de Pedidos por Mês")
df_mensal = df.groupby('ano_mes').agg({'numero_pedido': 'count'}).reset_index().rename(columns={'numero_pedido': 'total_pedidos'})
fig_trend = px.line(df_mensal, x='ano_mes', y='total_pedidos', markers=True)
st.plotly_chart(fig_trend, use_container_width=True)
st.download_button("📥 Exportar Excel", export_excel(df_mensal), file_name="pedidos_mensais.xlsx")

# Gráfico: Top Franqueados
st.subheader("🏪 Top Franqueados")
df_rank = df['franqueado'].value_counts().reset_index()
df_rank.columns = ['franqueado', 'qtd_pedidos']
fig_rank = px.bar(df_rank, x='franqueado', y='qtd_pedidos')
st.plotly_chart(fig_rank, use_container_width=True)
st.download_button("📥 Exportar Excel", export_excel(df_rank), file_name="top_franqueados.xlsx")

# Gráfico: Tempo Médio Entre Pedidos
st.subheader("⏱️ Tempo Médio Entre Pedidos por Franqueado")
df_tempo_medio = df.groupby("franqueado")["data_pedido"].apply(lambda x: x.sort_values().diff().mean()).reset_index()
df_tempo_medio.columns = ["franqueado", "tempo_medio"]
fig_tempo = px.bar(df_tempo_medio, x="franqueado", y="tempo_medio")
st.plotly_chart(fig_tempo, use_container_width=True)
st.download_button("📥 Exportar Excel", export_excel(df_tempo_medio), file_name="tempo_medio.xlsx")

# Gráfico: Queda de Pedidos
st.subheader("📉 Queda de Pedidos")
df_queda = df.groupby(['ano_mes', 'franqueado'])['numero_pedido'].count().reset_index()
df_queda['dif'] = df_queda.groupby('franqueado')['numero_pedido'].diff()
df_queda_top10 = df_queda.sort_values('dif').head(10)
fig_queda = px.bar(df_queda_top10, x='franqueado', y='dif')
st.plotly_chart(fig_queda, use_container_width=True)
st.download_button("📥 Exportar Excel", export_excel(df_queda_top10), file_name="queda_pedidos.xlsx")

# Gráfico: Crescimento de Pedidos
st.subheader("🔼 Crescimento de Pedidos")
df_crescimento = df.copy()
df_crescimento['qtd'] = 1
df_crescimento_mensal = df_crescimento.groupby(['ano_mes', 'franqueado'])['qtd'].sum().reset_index()
df_crescimento_mensal['crescimento'] = df_crescimento_mensal.groupby('franqueado')['qtd'].diff()
df_crescimento_top10 = df_crescimento_mensal.sort_values('crescimento', ascending=False).head(10)
fig_crescimento = px.bar(df_crescimento_top10, x='franqueado', y='crescimento')
st.plotly_chart(fig_crescimento, use_container_width=True)
st.download_button("📥 Exportar Excel", export_excel(df_crescimento_top10), file_name="crescimento_pedidos.xlsx")
