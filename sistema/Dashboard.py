import streamlit as st
import pandas as pd
from utils import get_dashboard_metrics, get_monthly_revenue_chart_data, get_upcoming_installments, get_recent_faturados, format_brl

# st.set_page_config deve ser o primeiro comando e só pode ser chamado uma vez
st.set_page_config(layout="wide", page_title="Dashboard", page_icon="🏠")

st.title("🏠 Dashboard Gerencial")
st.markdown("Visão geral do desempenho do seu negócio em tempo real.")

# --- Carrega os dados ---
metrics = get_dashboard_metrics()
df_monthly_revenue = get_monthly_revenue_chart_data()
df_upcoming = get_upcoming_installments()
df_recent = get_recent_faturados()

st.divider()

# --- Exibe as Métricas Principais ---
col1, col2, col3 = st.columns(3)
col1.metric("Faturamento do Mês", format_brl(metrics['faturamento_mes']))
col2.metric("Faturamento no Ano (YTD)", format_brl(metrics['faturamento_ano']))
col3.metric("Ticket Médio (Mês)", format_brl(metrics['ticket_medio_mes']))

st.write("") 

col4, col5, col6 = st.columns(3)
col4.metric("Contas a Receber", format_brl(metrics['a_receber']))
col5.metric("Valor Vencido", format_brl(metrics['vencido']), delta_color="inverse")
col6.metric("Pedidos em Produção", f"{metrics['em_producao']} OP(s)")

st.divider()

# --- Gráfico Principal ---
st.subheader("Faturamento Mensal (Últimos 12 Meses)")
if not df_monthly_revenue.empty:
    st.bar_chart(df_monthly_revenue, y="faturamento")
else:
    st.info("Ainda não há dados de faturamento para exibir o gráfico mensal.")

st.divider()

# --- Tabelas de Atividade Recente ---
col_sidebar, col_main = st.columns([1, 2])

with col_sidebar:
    st.subheader("🗓️ Próximas Contas a Vencer")
    if not df_upcoming.empty:
        df_upcoming_display = df_upcoming.copy()
        df_upcoming_display['valor_parcela'] = df_upcoming_display['valor_parcela'].apply(format_brl)
        df_upcoming_display.rename(columns={
            'data_vencimento': 'Vencimento',
            'valor_parcela': 'Valor',
            'nome_fantasia': 'Cliente'
        }, inplace=True)
        st.dataframe(df_upcoming_display[['Vencimento', 'Valor', 'Cliente']], hide_index=True, use_container_width=True)
    else:
        st.info("Nenhuma conta em aberto com vencimento futuro.")

with col_main:
    st.subheader("🧾 Últimos Pedidos Faturados")
    if not df_recent.empty:
        df_recent_display = df_recent.copy()
        df_recent_display['valor_total'] = df_recent_display['valor_total'].apply(format_brl)
        df_recent_display.rename(columns={
            'numero_documento': 'Nº Pedido',
            'data_emissao': 'Data',
            'nome_fantasia': 'Cliente',
            'valor_total': 'Valor Total'
        }, inplace=True)
        st.dataframe(df_recent_display, hide_index=True, use_container_width=True)
    else:
        st.info("Nenhum pedido foi faturado recentemente.")