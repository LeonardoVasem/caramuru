import streamlit as st
import pandas as pd
from utils import *
from pdf_generator import generate_pdf

st.set_page_config(layout="wide", page_title="Controle de Pedidos", page_icon="📋")
st.title("📋 Controle de Pedidos")

STATUS_OPTIONS = ['Aberto', 'Em Produção', 'Faturado', 'Enviado', 'Recebido', 'Concluído', 'Cancelado']

def start_editing_mode(doc_id):
    """Prepara o estado da sessão para entrar no modo de edição e navega para a página."""
    st.session_state.editing_id = doc_id
    st.session_state.edit_data_loaded = False # Força o recarregamento dos dados na página de Lançamento
    st.switch_page("pages/2_📝_Lançamento.py")

conn = get_db_connection()
if not conn:
    st.warning("Não foi possível conectar ao banco de dados.")
else:
    try:
        sql_query = """
            SELECT p.*, c.nome_fantasia, c.razao_social, c.cnpj_cpf, c.logradouro_num, 
                   c.bairro, c.cidade, c.uf, c.cep, c.inscricao_estadual
            FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
            WHERE p.tipo_documento = 'Pedido' ORDER BY p.data_emissao DESC, p.id DESC;
        """
        df_docs = pd.read_sql(sql_query, conn)
        
        df_docs_display = df_docs.copy()
        df_docs_display['Selecionar'] = False
        
        df_docs_display = df_docs_display[['Selecionar', 'numero_documento', 'numero_nota_fiscal', 'data_emissao', 'nome_fantasia', 'valor_total', 'status', 'id']]

        st.info("Marque 'Selecionar' para Ações em Massa ou escolha um documento abaixo para ver os detalhes.")
        
        edited_df = st.data_editor(
            df_docs_display,
            column_config={
                "id": None,
                "numero_documento": st.column_config.TextColumn("Nº Pedido"),
                "numero_nota_fiscal": st.column_config.TextColumn("Nº NF-e"),
                "data_emissao": st.column_config.DateColumn("Data Emissão", format="DD/MM/YYYY"),
                "nome_fantasia": st.column_config.TextColumn("Cliente"),
                "valor_total": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                "status": st.column_config.TextColumn("Status"),
            },
            hide_index=True, use_container_width=True, key='pedidos_editor'
        )

        selected_rows = edited_df[edited_df['Selecionar']]
        selected_ids = selected_rows['id'].tolist()

        if selected_ids:
            st.markdown("---")
            st.subheader(f"Ações em Massa para {len(selected_ids)} Pedido(s)")
            col1, col2, col3 = st.columns([2,1,1])
            new_status = col1.selectbox("Mudar status para:", STATUS_OPTIONS, key="bulk_status_ped")
            if col2.button("Aplicar Status", use_container_width=True):
                bulk_update_status(selected_ids, new_status)
            if col3.button("🗑️ Excluir Selecionados", type="primary", use_container_width=True):
                bulk_delete_orders(selected_ids)
        
        st.divider()
        st.subheader("Visualizar Detalhes do Pedido")
        lista_docs_selecao = ["Selecione um pedido..."] + df_docs['numero_documento'].tolist()
        selected_doc_num = st.selectbox("Escolha o documento para ver detalhes:", lista_docs_selecao)

        if selected_doc_num != "Selecione um pedido...":
            doc_info = df_docs[df_docs['numero_documento'] == selected_doc_num].iloc[0]
            
            with st.expander(f"Detalhes: {selected_doc_num}", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Cliente", doc_info['nome_fantasia'])
                col2.metric("Data de Emissão", doc_info['data_emissao'].strftime('%d/%m/%Y'))
                col3.metric("Valor Total", format_brl(doc_info['valor_total']))
                col4.metric("Status Atual", doc_info['status'])

                st.markdown("##### Itens do Documento:")
                sql_query_itens = "SELECT * FROM pedido_itens WHERE pedido_id = %s;"
                df_itens = pd.read_sql(sql_query_itens, conn, params=(int(doc_info['id']),))
                st.dataframe(df_itens[['produto_sku', 'quantidade_milheiro', 'preco_unitario', 'subtotal']], use_container_width=True, hide_index=True)

                st.divider()
                st.markdown("##### Ações e Informações Fiscais")

                col_nf, col_btn_nf = st.columns([2,1])
                nf_number = col_nf.text_input("Número da Nota Fiscal (NF-e)", value=doc_info.get('numero_nota_fiscal') or "", key=f"nf_input_{doc_info['id']}")
                if col_btn_nf.button("Salvar NF", key=f"nf_save_{doc_info['id']}", use_container_width=True):
                    update_nota_fiscal_number(int(doc_info['id']), nf_number)
                
                st.divider()

                col_a, col_b, col_c, col_d, col_e = st.columns([1, 1, 2, 1, 1])

                if col_a.button("✏️ Editar", key=f"edit_{doc_info['id']}", use_container_width=True):
                    start_editing_mode(int(doc_info['id']))
                
                if col_b.button("Gerar PDF", key=f"pdf_{doc_info['id']}", use_container_width=True):
                    cliente_info_pdf = doc_info.to_dict()
                    pdf_bytes = generate_pdf(doc_info, df_itens, cliente_info_pdf)
                    
                    cliente_nome = doc_info.get('nome_fantasia', 'documento').replace(' ', '_')
                    data_str = pd.to_datetime(doc_info['data_emissao']).strftime('%d-%m-%Y')
                    nome_arquivo = f"{cliente_nome}_{doc_info['numero_documento']}_{data_str}.pdf"

                    st.download_button(label="Baixar PDF", data=pdf_bytes, file_name=nome_arquivo, mime="application/pdf")

                with col_c:
                    current_status_index = STATUS_OPTIONS.index(doc_info['status']) if doc_info['status'] in STATUS_OPTIONS else 0
                    new_status_single = st.selectbox("Mudar status para:", STATUS_OPTIONS, index=current_status_index, key=f"status_single_{doc_info['id']}")
                
                with col_d:
                    st.write("")
                    if st.button("Salvar", use_container_width=True, key=f"save_status_{doc_info['id']}"):
                        update_order_status(int(doc_info['id']), new_status_single)

                with col_e:
                    st.write("")
                    if st.button("Excluir", type="primary", use_container_width=True, key=f"delete_{doc_info['id']}"):
                        delete_order(int(doc_info['id']))

    except Exception as e:
        st.error(f"Erro ao carregar os pedidos: {e}")
    finally:
        if conn: conn.close()