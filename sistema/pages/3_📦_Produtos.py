import streamlit as st
import math
from utils import *

st.title("📦 Gerenciamento de Produtos")

_, _, produtos_db, produtos_dict = load_data_from_sources()

def on_product_select_change():
    sku = st.session_state.product_select_key
    p_data = produtos_dict.get(sku, {}) if sku != "Novo Produto" else {}
    st.session_state.p_largura = int(p_data.get('largura', 10))
    st.session_state.p_altura = int(p_data.get('altura', 10))
    st.session_state.p_espessura = float(p_data.get('espessura', 0.0130))
    st.session_state.p_pigmento = p_data.get('pigmento', PIGMENTO_OPTIONS[0])
    st.session_state.p_modelo = p_data.get('modelo', MODELO_OPTIONS[0])
    st.session_state.p_material = p_data.get('material', MATERIAL_OPTIONS[0])
    st.session_state.p_valor_kg = float(p_data.get('valor_kg', 25.0))

product_skus = ["Novo Produto"] + sorted(produtos_db['sku'].unique())
selected_sku = st.selectbox("Selecione para Editar ou 'Novo Produto'", product_skus,
                            key="product_select_key", on_change=on_product_select_change)

is_new_product = (selected_sku == "Novo Produto")

if 'p_largura' not in st.session_state:
    on_product_select_change()

st.subheader(f"{'Cadastrar Novo Produto' if is_new_product else 'Editar Produto'}")

col1, col2, col3 = st.columns(3)
largura = col1.number_input("Largura (cm)", min_value=1, step=1, key='p_largura', format="%d")
altura = col2.number_input("Altura (cm)", min_value=1, step=1, key='p_altura', format="%d")
espessura = col3.number_input("Espessura (micra)", min_value=0.0001, key='p_espessura', format="%.4f")

col4, col5, col6 = st.columns(3)
pigmento = col4.selectbox("Pigmento", PIGMENTO_OPTIONS, key='p_pigmento')
modelo = col5.selectbox("Modelo", MODELO_OPTIONS, key='p_modelo')
material = col6.selectbox("Material", MATERIAL_OPTIONS, key='p_material')
valor_kg = st.number_input("Valor por KG (R$)", min_value=0.01, key='p_valor_kg', format="%.2f")

current_data_for_calc = {'largura': largura, 'altura': altura, 'espessura': espessura, 'pigmento': pigmento,
                         'modelo': modelo, 'material': material, 'valor_kg': valor_kg}
calculos = calcular_valores_produto(current_data_for_calc)

st.divider()
st.subheader("Valores Calculados")
col7, col8, col9 = st.columns(3)
col7.metric("Peso (Kg / Milheiro)", f"{calculos.get('peso', 0):.0f}")
col8.metric("Custo (R$ / Milheiro)", format_brl(calculos.get('custo', 0)))
col9.text_input("Medidas Finais", value=calculos.get('medidas', ''), disabled=True)
st.text_input("SKU Final (Gerado Automaticamente)", value=calculos.get('sku', ''), disabled=True)
st.divider()

with st.form(key='product_form_actions'):
    col_btn_save, col_btn_del, _ = st.columns([1,1,4])
    if col_btn_save.form_submit_button(f"✅ {'CADASTRAR' if is_new_product else 'SALVAR EDIÇÃO'}", type="primary"):
        final_data = {**current_data_for_calc, **calculos}
        if not final_data.get('sku') or 'INVÁLIDO' in final_data.get('sku'):
            st.error("Dados inválidos. Verifique os valores de entrada.")
        else:
            if is_new_product: insert_produto(final_data)
            else: update_produto(selected_sku, final_data)
            
    if not is_new_product and col_btn_del.form_submit_button("❌ REMOVER"):
        delete_produto(selected_sku)

st.subheader("Produtos Cadastrados")
st.dataframe(produtos_db, use_container_width=True, hide_index=True)