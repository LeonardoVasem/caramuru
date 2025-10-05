import streamlit as st
import pandas as pd
from utils import get_db_connection, execute_db_command, format_brl

st.title("📈 Controle de Estoque de Matéria-Prima")
st.info("Cadastre e gerencie suas matérias-primas. O próximo passo será integrar este estoque à ficha técnica dos seus produtos.")

conn = get_db_connection()
if not conn:
    st.warning("Não foi possível conectar ao banco de dados.")
else:
    try:
        # Carrega as matérias-primas existentes
        df_materias_primas = pd.read_sql("SELECT * FROM materias_primas ORDER BY nome", conn)

        # --- Formulário para Adicionar/Editar ---
        with st.form(key='materia_prima_form', clear_on_submit=True):
            st.subheader("Cadastrar Nova Matéria-Prima")
            
            nome_materia_prima = st.text_input("Nome da Matéria-Prima (ex: PEBD Virgem, Pigmento Azul)")
            unidade = st.selectbox("Unidade de Medida", ["kg", "un", "litro"])
            
            submitted = st.form_submit_button("✅ Salvar Nova Matéria-Prima")
            if submitted:
                if not nome_materia_prima:
                    st.error("O nome da matéria-prima é obrigatório.")
                else:
                    sql = "INSERT INTO materias_primas (nome, unidade_medida) VALUES (%s, %s)"
                    execute_db_command(sql, (nome_materia_prima, unidade), "Matéria-prima cadastrada com sucesso!")
                    st.rerun()

        st.divider()

        # --- Tabela de Matérias-Primas ---
        st.subheader("Matérias-Primas em Estoque")
        if df_materias_primas.empty:
            st.info("Nenhuma matéria-prima cadastrada ainda.")
        else:
            # Renomeia colunas para exibição
            df_display = df_materias_primas.rename(columns={
                'nome': 'Nome',
                'unidade_medida': 'Unidade',
                'quantidade_estoque': 'Qtde em Estoque',
                'custo_medio': 'Custo Médio (R$)'
            })
            # Formata a coluna de custo
            df_display['Custo Médio (R$)'] = df_display['Custo Médio (R$)'].apply(format_brl)

            st.dataframe(df_display[['Nome', 'Qtde em Estoque', 'Unidade', 'Custo Médio (R$)']],
                         use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Erro ao carregar a página de estoque: {e}")
    finally:
        conn.close()
