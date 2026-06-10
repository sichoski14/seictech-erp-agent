import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Análise de Varejo",
    page_icon="📊",
    layout="wide"
)

# Configuração
DB_PATH = 'data/retail_analytics.db'

def get_connection():
    return sqlite3.connect(DB_PATH)

# Título
st.title("📊 Sistema Avançado de Análise de Varejo")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configurações")
    refresh = st.button("🔄 Atualizar Dados")
    
    st.header("📅 Período de Análise")
    period = st.selectbox(
        "Selecionar período",
        ["Hoje", "Últimos 7 dias", "Últimos 30 dias", "Último ano"]
    )
    
    st.header("📈 Indicadores")
    st.metric("Produtos Cadastrados", "125")
    st.metric("Vendas Hoje", "R$ 12.450,00")

# Layout principal
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Receita Hoje",
        value="R$ 12.450",
        delta="+15%"
    )
    
with col2:
    st.metric(
        label="Transações",
        value="234",
        delta="+8%"
    )
    
with col3:
    st.metric(
        label="Ticket Médio",
        value="R$ 53,20",
        delta="-2%"
    )
    
with col4:
    st.metric(
        label="Produtos Críticos",
        value="5",
        delta="⚠️"
    )

# Gráficos
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Vendas por Dia")
    
    # Dados de exemplo
    dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
    sales = pd.DataFrame({
        'Data': dates,
        'Receita': [12000 + (i * 100) for i in range(30)]
    })
    
    fig = px.line(sales, x='Data', y='Receita', title='Tendência de Vendas')
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("💳 Vendas por Pagamento")
    
    payments = pd.DataFrame({
        'Método': ['PIX', 'Crédito', 'Débito', 'Dinheiro'],
        'Valor': [45000, 35000, 15000, 5000]
    })
    
    fig = px.pie(payments, values='Valor', names='Método', title='Distribuição de Pagamentos')
    st.plotly_chart(fig, use_container_width=True)

# Tabela de produtos
st.subheader("📦 Estoque de Produtos")

products = pd.DataFrame({
    'SKU': ['SKU001', 'SKU002', 'SKU003', 'SKU004'],
    'Produto': ['Camiseta', 'Calça', 'Tênis', 'Boné'],
    'Estoque': [50, 20, 5, 35],
    'Mínimo': [30, 15, 10, 20],
    'Status': ['✅ Normal', '✅ Normal', '⚠️ Crítico', '✅ Normal']
})

st.dataframe(products, use_container_width=True)

# Gráfico de barras
st.subheader("🏆 Top Produtos")
fig = px.bar(products, x='Produto', y='Estoque', color='Status', 
             title='Estoque por Produto')
st.plotly_chart(fig, use_container_width=True)