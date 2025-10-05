import streamlit as st
from utils import *

st.title("👥 Gerenciamento de Clientes")

clientes_db, clientes_dict, _, _ = load_data_from_sources()

selected_name = st.selectbox("Selecione para Editar ou 'Novo Cliente'", 
                             ["Novo Cliente"] + sorted(clientes_db['nome_fantasia'].dropna().unique()), 
                             key="client_select_key")

is_new_client = (selected_name == "Novo Cliente")
client_data = clientes_dict.get(selected_name, {})
client_id = client_data.get('id')
fetched_data = st.session_state.get('fetched_client_data', {})

st.markdown("##### CNPJ/CPF")

if 'cnpj_input' not in st.session_state:
    st.session_state.cnpj_input = client_data.get('cnpj_cpf', '') if not is_new_client else fetched_data.get('cnpj_cpf', '')

raw_cnpj = "".join(filter(str.isdigit, st.session_state.get('cnpj_input', '')))
formatted_cnpj = format_cnpj_cpf(raw_cnpj)
st.session_state.cnpj_input = formatted_cnpj

col_cnpj, col_btn = st.columns([2, 1])
with col_cnpj:
    st.text_input("CNPJ/CPF", key='cnpj_input', disabled=not is_new_client, label_visibility="collapsed")
with col_btn:
    if is_new_client and st.button("🔍 Buscar Dados", type='secondary', use_container_width=True):
        data, error = fetch_cnpj_data(st.session_state.cnpj_input)
        if data:
            st.session_state.fetched_client_data = data
            st.success("Dados preenchidos!")
            st.rerun()
        else:
            st.error(error)

with st.form(key='client_form'):
    st.subheader(f"{'Cadastrar Novo Cliente' if is_new_client else f'Editar {selected_name}'}")
    
    col_a, col_b = st.columns(2)
    nome_fantasia = col_a.text_input("Nome Fantasia", value=fetched_data.get('nome_fantasia', client_data.get('nome_fantasia', '')))
    razao_social = col_b.text_input("Razão Social", value=fetched_data.get('razao_social', client_data.get('razao_social', '')))
    inscricao_estadual = st.text_input("Inscrição Estadual", value=client_data.get('inscricao_estadual', ''), help="Este campo é de preenchimento manual.")

    st.divider()

    col1, col2 = st.columns(2)
    logradouro = col1.text_input("Rua e Número", value=fetched_data.get('logradouro_num', client_data.get('logradouro_num', '')))
    bairro = col1.text_input("Bairro", value=fetched_data.get('bairro', client_data.get('bairro', '')))
    complemento = col2.text_input("Complemento", value=fetched_data.get('complemento', client_data.get('complemento', '')))
    cidade = col2.text_input("Cidade", value=fetched_data.get('cidade', client_data.get('cidade', '')))
    col3, col4, _ = st.columns([1, 1, 4])
    uf = col3.text_input("UF", value=fetched_data.get('uf', client_data.get('uf', 'RS')), max_chars=2)
    cep = col4.text_input("CEP", value=fetched_data.get('cep', client_data.get('cep', '')))
    
    st.markdown("---")
    col_btn_save, col_btn_del, _ = st.columns([1, 1, 4])
    if col_btn_save.form_submit_button(f"✅ {'CADASTRAR' if is_new_client else 'SALVAR EDIÇÃO'}", type="primary"):
        cnpj_final = "".join(filter(str.isdigit, st.session_state.cnpj_input))
        if not cnpj_final and is_new_client:
            st.error("O campo CNPJ/CPF é obrigatório.")
        elif is_new_client and (nome_fantasia in clientes_dict or any(c['cnpj_cpf'] == cnpj_final for c in clientes_dict.values())):
            if nome_fantasia in clientes_dict:
                st.error("Erro: Já existe um cliente com este Nome Fantasia.")
            else:
                st.error("Erro: Já existe um cliente com este CNPJ/CPF.")
        else:
            data = {'id': client_id, 'nome_fantasia': nome_fantasia, 'razao_social': razao_social, 
                    'inscricao_estadual': inscricao_estadual, 'cnpj_cpf': cnpj_final, 
                    'logradouro_num': logradouro, 'complemento': complemento, 'bairro': bairro, 
                    'cidade': cidade, 'uf': uf, 'cep': cep}
            if is_new_client: insert_cliente(data)
            else: update_cliente(data)
            
    if not is_new_client and col_btn_del.form_submit_button("❌ REMOVER"):
        delete_cliente(client_id)

st.subheader("Clientes Cadastrados")
df_display = clientes_db[['nome_fantasia', 'razao_social', 'cnpj_cpf', 'inscricao_estadual', 'cidade']].copy()
df_display['cnpj_cpf'] = df_display['cnpj_cpf'].apply(format_cnpj_cpf)
st.dataframe(df_display, use_container_width=True, hide_index=True)