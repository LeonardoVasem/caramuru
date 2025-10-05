import streamlit as st
import pandas as pd
import uuid
from datetime import date
from pdf_generator import generate_pdf
from utils import *
import ast

# --- CONSTANTES GLOBAIS DA PÁGINA ---
MIN_QTDE_MILHEIRO = 0.500
PRAZO_PAGAMENTO_OPTIONS = ['À vista', '30 dias', '30/45 dias', '30/60 dias', '30/45/60 dias']
FORMA_PAGAMENTO_OPTIONS = ['Pix', 'Dinheiro', 'Boleto', 'Cheque']

# =================================================================================
# FUNÇÕES DA PÁGINA DE LANÇAMENTO
# =================================================================================

def calcular_totais():
    subtotal_produtos = sum(item['subtotal'] for item in st.session_state.get('itens_pedido', []))
    custo_envio = st.session_state.get('custo_envio', 0.0)
    st.session_state.total_geral = subtotal_produtos + custo_envio
    return subtotal_produtos

def adicionar_item_ao_pedido():
    if st.session_state.get('is_saved', False): return
    sku_selecionado = st.session_state.get('produto_selecionado_sku')
    if not sku_selecionado or sku_selecionado == "Selecione um produto...":
        st.warning("Por favor, selecione um produto para adicionar.")
        return

    _, _, _, produtos_dict = load_data_from_sources()
    produto_info = produtos_dict.get(sku_selecionado, {})
    
    qtde = st.session_state.qtde_milheiro
    preco_manual = st.session_state.preco_manual_input
    custo_base_reais = st.session_state.custo_base_reais
    custo_imp = st.session_state.custo_impressao_reais
    
    markup_pct = (st.session_state.lucro_percentual + st.session_state.custo_percentual + st.session_state.imposto_percentual_lci) / 100
    if markup_pct >= 1:
        st.error("Mark-up inválido: A soma de C, I e L não pode ser >= 100%.")
        return
        
    preco_final = preco_manual if preco_manual > 0.0 else (custo_base_reais + custo_imp) / (1 - markup_pct)
    
    nomes_cores = st.session_state.get('nomes_cores', '')
    num_cores = len([cor for cor in nomes_cores.split(',') if cor.strip()]) if nomes_cores.strip() else 0
    
    descricao_completa = {
        "material": produto_info.get('material', ''), "medidas": produto_info.get('medidas', ''),
        "modelo": produto_info.get('modelo', ''), "pigmento": produto_info.get('pigmento', ''),
        "num_cores": num_cores, "nomes_cores": nomes_cores, "lados": st.session_state.lados_impressao
    }

    if 'itens_pedido' not in st.session_state:
        st.session_state.itens_pedido = []
        
    st.session_state.itens_pedido.append({
        'produto_sku': sku_selecionado, 'descricao_completa': descricao_completa,
        'quantidade_milheiro': qtde, 'preco_unitario': preco_final, 'subtotal': qtde * preco_final
    })
    st.session_state.produto_selecionado_sku = "Selecione um produto..."
    st.session_state.preco_manual_input = 0.0
    st.session_state.nomes_cores = 'Preto'

def salvar_documento():
    _, clientes_dict, _, _ = load_data_from_sources()
    if not st.session_state.get('itens_pedido') or not st.session_state.get('cliente_selecionado'):
        st.error("É necessário ter um cliente selecionado e pelo menos um item no pedido.")
        return
        
    tipo = st.session_state.tipo_doc
    numero_doc = f"PED-{st.session_state.proximo_id_pedido}" if tipo == 'Pedido' else f"ORC-{st.session_state.proximo_id_orcamento}"
    cliente_selecionado_info = clientes_dict.get(st.session_state.cliente_selecionado, {})
    cliente_id = int(cliente_selecionado_info.get('id'))

    dados_pedido = {
        "numero_documento": numero_doc, "tipo_documento": tipo, "cliente_id": cliente_id,
        "data_emissao": st.session_state.data_emissao, "custo_envio": st.session_state.custo_envio,
        "valor_total": st.session_state.total_geral, "status": 'Aberto',
        "forma_pagamento": st.session_state.forma_pagamento, "prazo_pagamento": st.session_state.prazo_pagamento,
        "prazo_entrega": st.session_state.prazo_entrega
    }
    dados_pedido_pdf = {**dados_pedido, **cliente_selecionado_info}

    sql_pedido = "INSERT INTO pedidos (numero_documento, tipo_documento, cliente_id, data_emissao, custo_envio, valor_total, status, forma_pagamento, prazo_pagamento, prazo_entrega) VALUES (%(numero_documento)s, %(tipo_documento)s, %(cliente_id)s, %(data_emissao)s, %(custo_envio)s, %(valor_total)s, %(status)s, %(forma_pagamento)s, %(prazo_pagamento)s, %(prazo_entrega)s) RETURNING id;"
    pedido_id = execute_db_command(sql_pedido, dados_pedido, None, fetch_id=True)
    
    if pedido_id:
        for item in st.session_state.itens_pedido:
            item_data = item.copy()
            item_data['pedido_id'] = pedido_id
            item_data['descricao_item'] = str(item['descricao_completa'])
            sql_item = "INSERT INTO pedido_itens (pedido_id, produto_sku, descricao_item, quantidade_milheiro, preco_unitario, subtotal) VALUES (%(pedido_id)s, %(produto_sku)s, %(descricao_item)s, %(quantidade_milheiro)s, %(preco_unitario)s, %(subtotal)s);"
            execute_db_command(sql_item, item_data, success_message=None)

        st.session_state.documento_salvo_id = numero_doc
        st.session_state.is_saved = True
        st.session_state.saved_doc_type = tipo 
        if tipo == 'Pedido': st.session_state.proximo_id_pedido += 1
        else: st.session_state.proximo_id_orcamento += 1
        
        st.success(f"🎉 {tipo} **{numero_doc}** salvo!")
        st.balloons()
        
        df_itens = pd.DataFrame(st.session_state.itens_pedido)
        pdf_bytes = generate_pdf(dados_pedido_pdf, df_itens, dados_pedido_pdf)
        st.session_state.pdf_bytes = pdf_bytes
        
        cliente_nome = cliente_selecionado_info.get('nome_fantasia', 'doc').replace(' ', '_')
        data_str = pd.to_datetime(dados_pedido['data_emissao']).strftime('%d-%m-%Y')
        nome_arquivo = f"{cliente_nome}_{numero_doc}_{data_str}.pdf"
        st.session_state.pdf_filename = nome_arquivo

def handle_update():
    _, clientes_dict, _, _ = load_data_from_sources()
    cliente_id = clientes_dict.get(st.session_state.cliente_selecionado, {}).get('id')

    if not cliente_id:
        st.error("Cliente inválido. Não foi possível salvar.")
        return

    pedido_data = {
        "cliente_id": cliente_id, "data_emissao": st.session_state.data_emissao,
        "custo_envio": st.session_state.custo_envio, "valor_total": st.session_state.total_geral,
        "forma_pagamento": st.session_state.forma_pagamento, "prazo_pagamento": st.session_state.prazo_pagamento,
        "prazo_entrega": st.session_state.prazo_entrega
    }
    itens_data = st.session_state.get('itens_pedido', [])
    update_documento(st.session_state.editing_id, pedido_data, itens_data)

def novo_lancamento():
    keys_to_reset = ['itens_pedido', 'is_saved', 'documento_salvo_id', 'produto_selecionado_sku', 
                     'pdf_bytes', 'pdf_filename', 'saved_doc_type', 'nomes_cores', 'editing_id', 'edit_data_loaded']
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

def load_document_for_editing(doc_id):
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT p.*, c.nome_fantasia FROM pedidos p JOIN clientes c ON p.cliente_id = c.id WHERE p.id = %s", (doc_id,))
            pedido = cur.fetchone()
            if not pedido: return
            
            st.session_state.tipo_doc_edit = pedido['tipo_documento']
            st.session_state.cliente_selecionado = pedido['nome_fantasia']
            st.session_state.data_emissao = pedido['data_emissao']
            st.session_state.forma_pagamento = pedido['forma_pagamento']
            st.session_state.prazo_pagamento = pedido['prazo_pagamento']
            st.session_state.prazo_entrega = pedido['prazo_entrega']
            st.session_state.custo_envio = float(pedido['custo_envio'])
            st.session_state.numero_documento_edit = pedido['numero_documento']
            
            cur.execute("SELECT * FROM pedido_itens WHERE pedido_id = %s", (doc_id,))
            itens = cur.fetchall()
            
            itens_list = []
            for item in itens:
                try:
                    desc_completa = ast.literal_eval(item['descricao_item'])
                except (ValueError, SyntaxError):
                    desc_completa = {"raw_text": item['descricao_item']}
                
                itens_list.append({
                    'produto_sku': item['produto_sku'], 'descricao_completa': desc_completa,
                    'quantidade_milheiro': float(item['quantidade_milheiro']),
                    'preco_unitario': float(item['preco_unitario']), 'subtotal': float(item['subtotal'])
                })
            st.session_state.itens_pedido = itens_list
    except Exception as e:
        st.error(f"Erro ao carregar documento para edição: {e}")
    finally:
        if conn: conn.close()

def clear_edit_state():
    keys_to_clear = ['editing_id', 'edit_data_loaded', 'itens_pedido', 'cliente_selecionado', 'numero_documento_edit', 'tipo_doc_edit']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

is_editing = 'editing_id' in st.session_state and st.session_state.editing_id is not None

if is_editing:
    if not st.session_state.get('edit_data_loaded', False):
        load_document_for_editing(st.session_state.editing_id)
        st.session_state.edit_data_loaded = True
    doc_type = st.session_state.get('tipo_doc_edit', 'Documento')
    doc_num = st.session_state.get('numero_documento_edit', '')
    st.title(f"✏️ Editando {doc_type} Nº {doc_num}")
else:
    st.title("📝 Novo Lançamento")    

# =================================================================================
# LÓGICA DE INICIALIZAÇÃO E EDIÇÃO
# =================================================================================

is_editing = 'editing_id' in st.session_state and st.session_state.editing_id is not None

if is_editing:
    if not st.session_state.get('edit_data_loaded', False):
        load_document_for_editing(st.session_state.editing_id)
        st.session_state.edit_data_loaded = True
    doc_type = st.session_state.get('tipo_doc_edit', 'Documento')
    doc_num = st.session_state.get('numero_documento_edit', '')
    st.title(f"✏️ Editando {doc_type} Nº {doc_num}")
else:
    st.title("📝 Novo Lançamento")

next_pedido_db, next_orcamento_db = get_next_document_numbers()
if 'proximo_id_pedido' not in st.session_state or st.session_state.proximo_id_pedido < next_pedido_db:
    st.session_state.proximo_id_pedido = next_pedido_db
if 'proximo_id_orcamento' not in st.session_state or st.session_state.proximo_id_orcamento < next_orcamento_db:
    st.session_state.proximo_id_orcamento = next_orcamento_db

default_session_state = {
    'itens_pedido': [], 'is_saved': False, 'lucro_percentual': 25.0, 'custo_percentual': 15.0,
    'imposto_percentual_lci': 8.5, 'custo_base_reais': 160.0, 'qtde_milheiro': MIN_QTDE_MILHEIRO,
    'preco_manual_input': 0.0, 'custo_envio': 0.0, 'produto_selecionado_sku': "Selecione um produto...",
    'nomes_cores': 'Preto', 'lados_impressao': 'Só Frente', 'custo_base_impressao': 230.0,
    'prazo_entrega': 40
}
for key, value in default_session_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =================================================================================
# EXECUÇÃO DA PÁGINA
# =================================================================================

clientes_db, _, produtos_db, produtos_dict = load_data_from_sources()

if not st.session_state.is_saved:
    st.subheader("1. Detalhes do Documento")
    col1, col2, col3 = st.columns(3)

    if is_editing:
        tipo_doc_display = st.session_state.get('tipo_doc_edit', 'Documento')
        col1.text_input("Tipo", value=tipo_doc_display, disabled=True)
    else:
        tipo_doc = col1.selectbox("Tipo", ['Pedido', 'Orçamento'], key='tipo_doc')
    
    doc_id = st.session_state.get('numero_documento_edit', '') if is_editing else gerar_preview_numero_serie(st.session_state.tipo_doc)
    col2.text_input("Nº Documento", value=doc_id, disabled=True)
    col3.date_input("Data de Emissão", key='data_emissao', format="DD/MM/YYYY")
    
    if not clientes_db.empty:
        cliente_options = sorted(clientes_db['nome_fantasia'].unique())
        default_cliente_index = cliente_options.index(st.session_state.cliente_selecionado) if st.session_state.get('cliente_selecionado') in cliente_options else 0
        st.selectbox("Cliente", options=cliente_options, key='cliente_selecionado', index=default_cliente_index)
    else:
        st.warning("Nenhum cliente cadastrado.")

    st.subheader("Condições e Prazo")
    col_p1, col_p2, col_p3 = st.columns(3)
    
    default_forma_idx = FORMA_PAGAMENTO_OPTIONS.index(st.session_state.get('forma_pagamento', 'Boleto')) if st.session_state.get('forma_pagamento') in FORMA_PAGAMENTO_OPTIONS else 0
    col_p1.selectbox("Forma de Pagamento", options=FORMA_PAGAMENTO_OPTIONS, key='forma_pagamento', index=default_forma_idx)
    
    default_prazo_idx = PRAZO_PAGAMENTO_OPTIONS.index(st.session_state.get('prazo_pagamento', '30/45/60 dias')) if st.session_state.get('prazo_pagamento') in PRAZO_PAGAMENTO_OPTIONS else 0
    col_p2.selectbox("Prazo de Pagamento", options=PRAZO_PAGAMENTO_OPTIONS, key='prazo_pagamento', index=default_prazo_idx)
    
    col_p3.number_input("Prazo de Entrega (dias)", min_value=1, step=1, key='prazo_entrega')

    st.divider()
    
    st.subheader("2. Lançamento de Itens")
    if not produtos_db.empty:
        lista_produtos = ["Selecione um produto..."] + sorted(produtos_db['sku'].unique())
        st.selectbox("Selecionar Produto Cadastrado", options=lista_produtos,
                     key='produto_selecionado_sku')
    else:
        st.warning("Nenhum produto cadastrado.")

    sku_selecionado = st.session_state.get('produto_selecionado_sku')
    if sku_selecionado and sku_selecionado != "Selecione um produto...":
        produto = produtos_dict.get(sku_selecionado)
        if produto is not None:
            st.session_state.custo_base_reais = float(produto['custo'])
            largura = float(produto['largura'])
            altura = float(produto['altura'])
            if largura < 25 or altura < 35:
                st.session_state.custo_base_impressao = 170.0
            else:
                st.session_state.custo_base_impressao = 230.0
    
    st.subheader("Personalização da Impressão")
    col_pers1, col_pers2 = st.columns(2)
    nomes_cores_str = col_pers1.text_input("Nomes das Cores", key='nomes_cores', help="Separe os nomes das cores por vírgula.")
    if nomes_cores_str and nomes_cores_str.strip():
        num_cores_calculado = len([cor for cor in nomes_cores_str.split(',') if cor.strip()])
    else:
        num_cores_calculado = 0
    
    col_pers2.selectbox("Lados", options=['Só Frente', 'Frente e Verso'], key='lados_impressao')

    multiplicador_lados = 2 if st.session_state.lados_impressao == 'Frente e Verso' else 1
    custo_impressao_final = st.session_state.custo_base_impressao * num_cores_calculado * multiplicador_lados
    st.session_state.custo_impressao_reais = custo_impressao_final

    st.subheader("Cálculo de Preço")
    cols_lci = st.columns([1.5, 1.5, 0.8, 0.8, 0.8, 2, 1.5])
    cols_lci[0].number_input("Custo Base", min_value=0.01, format="%.2f", key='custo_base_reais')
    cols_lci[1].number_input("Custo Impressão", value=custo_impressao_final, format="%.2f", disabled=True, help="Calculado automaticamente.")
    cols_lci[2].number_input("L(%)", min_value=0.0, max_value=99.9, step=0.5, key='lucro_percentual')
    cols_lci[3].number_input("C(%)", min_value=0.0, max_value=99.9, step=0.5, key='custo_percentual')
    cols_lci[4].number_input("I(%)", min_value=0.0, max_value=99.9, step=0.5, key='imposto_percentual_lci')
    
    try:
        custo_total = st.session_state.custo_base_reais + custo_impressao_final
        markup = (st.session_state.custo_percentual + st.session_state.imposto_percentual_lci + st.session_state.lucro_percentual) / 100
        preco_calc = custo_total / (1 - markup) if markup < 1 else 0
    except (ZeroDivisionError, TypeError): preco_calc = 0
    cols_lci[5].metric("Preço Final", format_brl(preco_calc))
    cols_lci[6].number_input("Preço Especial", min_value=0.0, format="%.2f", key='preco_manual_input')
    
    st.number_input("Qtde (Milheiros)", min_value=MIN_QTDE_MILHEIRO, step=0.5, format="%.3f", key='qtde_milheiro')

    st.button("➕ Adicionar Item ao Pedido", on_click=adicionar_item_ao_pedido, type="secondary")
    st.divider()

    st.subheader("3. Resumo do Documento")
    if st.session_state.itens_pedido:
        itens_para_exibir = []
        for item in st.session_state.itens_pedido:
            desc_dict = item['descricao_completa']
            desc_str = f"{desc_dict.get('pigmento', '')} {desc_dict.get('material', '')} - {desc_dict.get('medidas', '')} - alça {desc_dict.get('modelo', '')}"
            
            item_exibicao = item.copy()
            item_exibicao['descricao_completa'] = desc_str
            itens_para_exibir.append(item_exibicao)

        df_display = pd.DataFrame(itens_para_exibir)
        
        df_display['quantidade_milheiro'] = df_display['quantidade_milheiro'].apply(lambda x: f"{x:.3f}")
        df_display['preco_unitario_individual'] = (df_display['preco_unitario'] / 1000).apply(format_brl)
        df_display['subtotal'] = df_display['subtotal'].apply(format_brl)
        
        df_display.rename(columns={
            'descricao_completa': 'Descrição', 'quantidade_milheiro': 'Qtde (M)',
            'preco_unitario_individual': 'Preço Unitário', 'subtotal': 'Subtotal'
        }, inplace=True)

        st.dataframe(df_display[['Descrição', 'Qtde (M)', 'Preço Unitário', 'Subtotal']], hide_index=True, use_container_width=True)
    else:
        st.info("Nenhum item adicionado ao documento.")

    st.divider()
    subtotal = calcular_totais()
    cols_fin = st.columns(3)
    cols_fin[0].metric("Subtotal Produtos", format_brl(subtotal))
    cols_fin[1].number_input("Custo Envio", min_value=0.0, format="%.2f", key='custo_envio', disabled=st.session_state.is_saved, on_change=calcular_totais)
    cols_fin[2].metric("TOTAL GERAL", format_brl(st.session_state.get('total_geral', 0)))

    st.divider()

    if is_editing:
        col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 4])
        col_btn1.button("💾 Salvar Alterações", on_click=handle_update, type="primary", use_container_width=True)
        col_btn2.button("❌ Cancelar Edição", on_click=clear_edit_state, use_container_width=True)
    else:
        button_label = f"🚀 Emitir {st.session_state.get('tipo_doc', 'Documento')}"
        st.button(button_label, on_click=salvar_documento, type="primary", disabled=not st.session_state.itens_pedido)

else:
    st.subheader("Documento Salvo com Sucesso")
    st.info(f"Visualizando {st.session_state.saved_doc_type} salvo: **{st.session_state.documento_salvo_id}**")
    if 'pdf_bytes' in st.session_state:
        st.download_button(
            label="Baixar PDF Gerado",
            data=st.session_state.pdf_bytes,
            file_name=st.session_state.pdf_filename,
            mime="application/pdf"
        )
    
    st.button("➕ Novo Lançamento", on_click=novo_lancamento, type="primary")

