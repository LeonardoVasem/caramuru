import streamlit as st
import pandas as pd
from utils import *
from pdf_generator import generate_pdf

st.title("🔍 Orçamentos (Follow-up)")

STATUS_OPTIONS = ['Aberto', 'Aprovado', 'Recusado', 'Cancelado']

def start_editing_mode(doc_id):
    st.session_state.editing_id = doc_id
    st.session_state.edit_data_loaded = False
    st.switch_page("pages/2_📝_Lançamento.py") # CORRIGIDO

conn = get_db_connection()
if not conn:
    st.warning("Não foi possível conectar ao banco de dados.")
else:
    try:
        sql_query = "SELECT p.*, c.nome_fantasia, c.razao_social, c.cnpj_cpf FROM pedidos p JOIN clientes c ON p.cliente_id = c.id WHERE p.tipo_documento = 'Orçamento' ORDER BY p.data_emissao DESC, p.id DESC;"
        df_docs = pd.read_sql(sql_query, conn)
        
        df_docs_display = df_docs.copy()
        df_docs_display['Selecionar'] = False
        df_docs_display = df_docs_display[['Selecionar', 'numero_documento', 'data_emissao', 'nome_fantasia', 'valor_total', 'status', 'id']]

        st.info("Marque 'Selecionar' para Ações em Massa ou escolha um documento abaixo para ver os detalhes.")
        
        edited_df = st.data_editor(
            df_docs_display,
            column_config={
                "id": None,
                "numero_documento": st.column_config.TextColumn("Nº Documento"),
                "data_emissao": st.column_config.DateColumn("Data Emissão", format="DD/MM/YYYY"),
                "nome_fantasia": st.column_config.TextColumn("Cliente"),
                "valor_total": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                "status": st.column_config.TextColumn("Status"),
            },
            hide_index=True,
            use_container_width=True,
            key='orcamentos_editor'
        )

        selected_rows = edited_df[edited_df['Selecionar']]
        selected_ids = selected_rows['id'].tolist()

        if selected_ids:
            st.markdown("---")
            st.subheader(f"Ações em Massa para {len(selected_ids)} Orçamento(s)")
            col1, col2, col3 = st.columns([2,1,1])
            new_status = col1.selectbox("Mudar status para:", STATUS_OPTIONS, key="bulk_status_orc")
            if col2.button("Aplicar Status", use_container_width=True):
                bulk_update_status(selected_ids, new_status)
            if col3.button("🗑️ Excluir Selecionados", type="primary", use_container_width=True):
                bulk_delete_orders(selected_ids)
        
        st.divider()
        st.subheader("Visualizar Detalhes do Orçamento")
        lista_docs_selecao = ["Selecione um orçamento..."] + df_docs['numero_documento'].tolist()
        selected_doc_num = st.selectbox("Escolha o documento para ver detalhes:", lista_docs_selecao)

        if selected_doc_num != "Selecione um orçamento...":
            doc_info = df_docs[df_docs['numero_documento'] == selected_doc_num].iloc[0]
            
            with st.expander(f"Detalhes: {selected_doc_num}", expanded=True):
                # MODIFICADO: Layout das métricas (igual ao de Pedidos)
                st.markdown(f"""
                <div style='display: flex; justify-content: space-around; padding: 10px; background-color: #fafafa; border-radius: 10px;'>
                    <div style='text-align: center;'><strong>Cliente</strong><br>{doc_info['nome_fantasia']}</div>
                    <div style='text-align: center;'><strong>Data de Emissão</strong><br>{doc_info['data_emissao'].strftime('%d/%m/%Y')}</div>
                    <div style='text-align: center;'><strong>Valor Total</strong><br>{format_brl(doc_info['valor_total'])}</div>
                    <div style='text-align: center;'><strong>Status Atual</strong><br>{doc_info['status']}</div>
                </div>
                """, unsafe_allow_html=True)
                st.write("")

                st.markdown("##### Itens do Documento:")
                sql_query_itens = "SELECT produto_sku, descricao_item, quantidade_milheiro, preco_unitario, subtotal FROM pedido_itens WHERE pedido_id = %s;"
                df_itens = pd.read_sql(sql_query_itens, conn, params=(int(doc_info['id']),))
                
                st.dataframe(df_itens, use_container_width=True, hide_index=True)
                
                st.divider()
                st.markdown("##### Ações do Orçamento")
                
                col_a, col_b, col_c, col_d, col_e = st.columns([2, 1, 2, 1, 1])

                with col_a:
                    if st.button("✅ Aprovar e Converter em Pedido", type="primary", use_container_width=True):
                        convert_orcamento_to_pedido(int(doc_info['id']))
                
                with col_b:
                     if st.button("Gerar PDF", use_container_width=True, key=f"pdf_single_{doc_info['id']}"):
                        cliente_info_pdf = doc_info.to_dict()
                        pdf_bytes = generate_pdf(doc_info, df_itens, cliente_info_pdf)
                        cliente_nome = doc_info.get('nome_fantasia', 'documento').replace(' ', '_')
                        data_emissao = pd.to_datetime(doc_info['data_emissao'])
                        nome_arquivo = f"{cliente_nome}_{data_emissao.month}-{data_emissao.year}.pdf"
                        st.download_button(label="Baixar PDF", data=pdf_bytes, file_name=nome_arquivo, mime="application/pdf")
                
                with col_c:
                    current_status_index = STATUS_OPTIONS.index(doc_info['status']) if doc_info['status'] in STATUS_OPTIONS else 0
                    new_status_single = st.selectbox("Mudar status para:", STATUS_OPTIONS, index=current_status_index, key="single_status_orc")
                
                with col_d:
                    st.write("")
                    if st.button("Salvar", use_container_width=True, key=f"save_status_{doc_info['id']}"):
                        update_order_status(int(doc_info['id']), new_status_single)
                
                with col_e:
                    st.write("")
                    if st.button("Excluir", type="primary", use_container_width=True, key=f"delete_{doc_info['id']}"):
                        delete_order(int(doc_info['id']))

    except Exception as e:
        st.error(f"Erro ao carregar os orçamentos: {e}")
    finally:
        if conn: conn.close()