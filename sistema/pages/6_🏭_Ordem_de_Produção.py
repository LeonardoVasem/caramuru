import streamlit as st
import pandas as pd
from utils import get_db_connection
from datetime import timedelta
import ast
from op_pdf_generator import generate_op_pdf

st.set_page_config(layout="wide", page_title="Ordem de Produção", page_icon="🏭")
st.title("🏭 Ordem de Produção (OP)")
st.info("Esta página exibe os itens de pedidos com status 'Em Produção'. Selecione um ou mais itens para gerar um PDF com as fichas de produção.")

conn = get_db_connection()
if not conn:
    st.warning("Não foi possível conectar ao banco de dados.")
else:
    try:
        sql_query = """
            SELECT 
                pi.id as item_id,
                p.numero_documento,
                p.data_emissao,
                p.prazo_entrega,
                c.nome_fantasia,
                pi.descricao_item,
                pi.quantidade_milheiro
            FROM 
                pedido_itens pi
            JOIN 
                pedidos p ON pi.pedido_id = p.id
            JOIN 
                clientes c ON p.cliente_id = c.id
            WHERE 
                p.status = 'Em Produção'
            ORDER BY 
                p.data_emissao, p.id;
        """
        df_itens_producao = pd.read_sql(sql_query, conn)

        if df_itens_producao.empty:
            st.success("🎉 Tudo certo! Não há nenhum item na fila de produção no momento.")
        else:
            df_itens_producao['Selecionar'] = False
            
            st.subheader(f"Itens na Fila de Produção: {len(df_itens_producao)}")

            # Usa o data_editor para permitir a seleção
            edited_df = st.data_editor(
                df_itens_producao[['Selecionar', 'numero_documento', 'data_emissao', 'nome_fantasia', 'quantidade_milheiro', 'item_id']],
                column_config={
                    "item_id": None, # Oculta o ID do item
                    "numero_documento": st.column_config.TextColumn("Pedido Nº"),
                    "data_emissao": st.column_config.DateColumn("Data Emissão", format="DD/MM/YYYY"),
                    "nome_fantasia": st.column_config.TextColumn("Cliente"),
                    "quantidade_milheiro": st.column_config.NumberColumn("Qtde (M)", format="%.3f"),
                },
                hide_index=True,
                use_container_width=True,
                key='op_editor'
            )
            
            selected_rows = edited_df[edited_df['Selecionar']]
            
            if not selected_rows.empty:
                st.markdown("---")
                # Botão para imprimir os selecionados
                if st.button(f"🖨️ Imprimir Fichas Selecionadas ({len(selected_rows)})", type="primary"):
                    # Busca os dados completos das linhas selecionadas
                    selected_item_ids = tuple(selected_rows['item_id'].tolist())
                    
                    # Usa a tupla na query SQL
                    sql_full_data = f"""
                        SELECT pi.id as item_id, p.*, c.nome_fantasia, pi.descricao_item, pi.quantidade_milheiro
                        FROM pedido_itens pi
                        JOIN pedidos p ON pi.pedido_id = p.id
                        JOIN clientes c ON p.cliente_id = c.id
                        WHERE pi.id IN %s;
                    """
                    df_full_data = pd.read_sql(sql_full_data, conn, params=(selected_item_ids,))
                    items_to_print = df_full_data.to_dict('records')

                    pdf_bytes = generate_op_pdf(items_to_print)
                    st.download_button(
                        label="Baixar PDF com Fichas",
                        data=pdf_bytes,
                        file_name="Ordens_de_Producao.pdf",
                        mime="application/pdf"
                    )

    except Exception as e:
        st.error(f"Erro ao carregar as Ordens de Produção: {e}")
    finally:
        if conn: conn.close()