import streamlit as st
import pandas as pd
from utils import get_db_connection, format_brl, update_installment_status
from datetime import date

st.set_page_config(layout="wide", page_title="Controle Financeiro", page_icon="💰")
st.title("💰 Controle Financeiro - Contas a Receber")

conn = get_db_connection()
if not conn:
    st.warning("Não foi possível conectar ao banco de dados.")
else:
    try:
        sql_query = """
            SELECT 
                cr.id, cr.pedido_id, cr.numero_parcela, cr.valor_parcela, 
                cr.data_vencimento, cr.status_pagamento, cr.data_pagamento,
                p.numero_documento,
                c.nome_fantasia
            FROM 
                contas_a_receber cr
            JOIN 
                pedidos p ON cr.pedido_id = p.id
            JOIN 
                clientes c ON p.cliente_id = c.id
            ORDER BY 
                cr.data_vencimento;
        """
        df_contas = pd.read_sql(sql_query, conn)

        # Atualiza status para 'Vencido' dinamicamente para exibição
        today = date.today()
        if not df_contas.empty:
            df_contas['status_pagamento'] = df_contas.apply(
                lambda row: 'Vencido' if row['data_vencimento'] < today and row['status_pagamento'] == 'Em Aberto' else row['status_pagamento'],
                axis=1
            )
        
        # --- Métricas de Resumo ---
        total_receber = df_contas[df_contas['status_pagamento'] != 'Pago']['valor_parcela'].sum()
        total_recebido = df_contas[df_contas['status_pagamento'] == 'Pago']['valor_parcela'].sum()
        total_vencido = df_contas[df_contas['status_pagamento'] == 'Vencido']['valor_parcela'].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("A Receber", format_brl(total_receber))
        col2.metric("Recebido (Total)", format_brl(total_recebido))
        col3.metric("Vencido", format_brl(total_vencido), delta_color="inverse")

        st.divider()

        # --- Filtros ---
        st.subheader("Filtros")
        col_f1, col_f2 = st.columns(2)
        
        clientes_lista = ["Todos"] + sorted(df_contas['nome_fantasia'].unique())
        cliente_filtro = col_f1.selectbox("Filtrar por cliente:", clientes_lista)
        
        status_lista = ["Todos", "Em Aberto", "Pago", "Vencido"]
        status_filtro = col_f2.selectbox("Filtrar por status:", status_lista)

        df_filtrado = df_contas.copy()
        if cliente_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado['nome_fantasia'] == cliente_filtro]
        if status_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado['status_pagamento'] == status_filtro]
        
        df_filtrado['Pagar'] = False
        
        st.subheader("Lançamentos")
        
        # MODIFICADO: Passa o DataFrame completo e usa column_order/column_config para ajustar a exibição
        edited_df = st.data_editor(
            df_filtrado,
            column_order=('Pagar', 'numero_documento', 'nome_fantasia', 'numero_parcela', 'valor_parcela', 'data_vencimento', 'status_pagamento'),
            column_config={
                # Oculta colunas desnecessárias
                "id": None,
                "pedido_id": None,
                "data_pagamento": None,
                
                # Renomeia e formata as colunas visíveis
                "numero_documento": st.column_config.TextColumn("Nº Pedido"),
                "nome_fantasia": st.column_config.TextColumn("Cliente"),
                "numero_parcela": st.column_config.NumberColumn("Parcela", format="%d"),
                "valor_parcela": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                "data_vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                "status_pagamento": st.column_config.TextColumn("Status"),
            },
            hide_index=True,
            use_container_width=True,
            key='financeiro_editor'
        )
        
        parcelas_a_pagar = edited_df[edited_df['Pagar']]
        if not parcelas_a_pagar.empty:
            if st.button("✅ Dar Baixa nas Parcelas Selecionadas", type="primary"):
                for _, row in parcelas_a_pagar.iterrows():
                    update_installment_status(int(row['id']), 'Pago')

    except Exception as e:
        st.error(f"Erro ao carregar o controle financeiro: {e}")
    finally:
        if conn: conn.close()