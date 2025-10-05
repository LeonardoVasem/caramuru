import streamlit as st
import pandas as pd
import requests
import psycopg2
import psycopg2.extras
import math
from typing import Dict, Any, Tuple, List
from datetime import date, timedelta

# --- CONFIGURAÇÕES DO BANCO DE DADOS ---
# MODIFICADO: Suas variáveis antigas foram removidas
# ADICIONADO: Sua nova string de conexão com o banco de dados na nuvem (Neon)
NEON_CONNECTION_STRING = "postgresql://neondb_owner:npg_EfqtyYGx5S1T@ep-super-glade-ac01z9h4-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# --- OPÇÕES DE SELEÇÃO (SELECTBOX) ---
PIGMENTO_OPTIONS = ['Branco', 'Preto', 'Azul', 'Rosa', 'Vermelho', 'Laranja', 'Amarelo', 'Verde', 'Transparente']
MODELO_OPTIONS = ['Vazada', 'Camiseta', 'Fita', 'Cordão']
MATERIAL_OPTIONS = ['Fosco', 'Brilho', 'PP']

# =================================================================================
# FUNÇÕES COMPARTILHADAS
# =================================================================================

def get_db_connection():
    try:
        # MODIFICADO: Agora usa a nova string para se conectar
        conn = psycopg2.connect(NEON_CONNECTION_STRING)
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados na nuvem: {e}")
        return None

def get_next_document_numbers():
    conn = get_db_connection()
    next_pedido = 1001
    next_orcamento = 2001
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT numero_documento FROM pedidos WHERE tipo_documento = 'Pedido' ORDER BY id DESC LIMIT 1")
                last_pedido = cur.fetchone()
                if last_pedido:
                    next_pedido = int(last_pedido[0].split('-')[1]) + 1

                cur.execute("SELECT numero_documento FROM pedidos WHERE tipo_documento = 'Orçamento' ORDER BY id DESC LIMIT 1")
                last_orcamento = cur.fetchone()
                if last_orcamento:
                    next_orcamento = int(last_orcamento[0].split('-')[1]) + 1
        except Exception as e:
            st.warning(f"Não foi possível buscar a numeração sequencial. Erro: {e}")
        finally:
            conn.close()
    return next_pedido, next_orcamento

@st.cache_data(ttl=300)
def load_data_from_sources():
    conn = get_db_connection()
    if conn:
        try:
            df_clientes = pd.read_sql("SELECT * FROM clientes ORDER BY nome_fantasia", conn)
            df_produtos = pd.read_sql("SELECT * FROM produtos ORDER BY sku", conn)
            clientes_dict = {row['nome_fantasia']: row for _, row in df_clientes.iterrows()}
            produtos_dict = {row['sku']: row for _, row in df_produtos.iterrows()}
            return df_clientes, clientes_dict, df_produtos, produtos_dict
        except psycopg2.errors.UndefinedTable:
             st.error("Erro: Tabelas não encontradas no DB. Crie-as com os comandos SQL.")
             return pd.DataFrame(), {}, pd.DataFrame(), {}
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
        finally:
            conn.close()
    return pd.DataFrame(), {}, pd.DataFrame(), {}

def execute_db_command(sql_command: str, data: Any = None, success_message: str = "Operação bem-sucedida!", fetch_id=False):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(sql_command, data)
                new_id = None
                if fetch_id:
                    new_id = cur.fetchone()[0]
            conn.commit()
            if success_message: st.toast(success_message)
            load_data_from_sources.clear()
            return new_id
        except Exception as e:
            conn.rollback()
            if "violates unique constraint" in str(e):
                if "clientes_cnpj_cpf_key" in str(e):
                    st.error("Erro: Já existe um cliente com este CNPJ/CPF.")
                elif "clientes_nome_fantasia_key" in str(e):
                    st.error("Erro: Já existe um cliente com este Nome Fantasia.")
                else:
                    st.error(f"Erro de duplicidade no banco de dados: {e}")
            else:
                st.error(f"Erro na operação: {e}")
            return None
        finally:
            conn.close()

def format_cnpj_cpf(doc: str) -> str:
    if doc is None or not isinstance(doc, str): return ""
    doc_clean = "".join(filter(str.isdigit, doc))
    if len(doc_clean) > 11:
        return f"{doc_clean[:2]}.{doc_clean[2:5]}.{doc_clean[5:8]}/{doc_clean[8:12]}-{doc_clean[12:14]}"
    elif len(doc_clean) > 0:
        return f"{doc_clean[:3]}.{doc_clean[3:6]}.{doc_clean[6:9]}-{doc_clean[9:11]}"
    return doc_clean

def fetch_cnpj_data(cnpj: str) -> Tuple[Dict[str, Any] | None, str | None]:
    cnpj_clean = "".join(filter(str.isdigit, cnpj))
    if len(cnpj_clean) != 14: return None, "CNPJ inválido (deve ter 14 dígitos)."
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_clean}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {'nome_fantasia': data.get('nome_fantasia', data.get('razao_social', '')),
                    'razao_social': data.get('razao_social', ''),
                    'logradouro_num': f"{data.get('logradouro', '')}, {data.get('numero', '')}",
                    'complemento': data.get('complemento', ''), 'bairro': data.get('bairro', ''),
                    'cidade': data.get('municipio', ''), 'uf': data.get('uf', ''), 'cep': data.get('cep', ''),
                    'cnpj_cpf': cnpj_clean}, None
        return None, "CNPJ não encontrado."
    except requests.exceptions.RequestException as e:
        return None, f"Erro de conexão: {e}"

def insert_cliente(data: Dict[str, Any]):
    sql = """INSERT INTO clientes (nome_fantasia, razao_social, inscricao_estadual, cnpj_cpf, logradouro_num, complemento, bairro, cidade, uf, cep) 
             VALUES (%(nome_fantasia)s, %(razao_social)s, %(inscricao_estadual)s, %(cnpj_cpf)s, %(logradouro_num)s, %(complemento)s, %(bairro)s, %(cidade)s, %(uf)s, %(cep)s)"""
    if execute_db_command(sql, data, "✅ Cliente cadastrado!") is not None:
        st.session_state.cnpj_input = ""
        st.session_state.fetched_client_data = {}
        st.rerun()

def update_cliente(data: Dict[str, Any]):
    sql = """UPDATE clientes SET nome_fantasia=%(nome_fantasia)s, razao_social=%(razao_social)s, inscricao_estadual=%(inscricao_estadual)s,
             cnpj_cpf=%(cnpj_cpf)s, logradouro_num=%(logradouro_num)s, complemento=%(complemento)s, 
             bairro=%(bairro)s, cidade=%(cidade)s, uf=%(uf)s, cep=%(cep)s 
             WHERE id=%(id)s"""
    if execute_db_command(sql, data, "✅ Cliente atualizado!") is not None:
        st.session_state.cnpj_input = ""
        st.session_state.fetched_client_data = {}
        st.rerun()

def delete_cliente(cliente_id: int):
    sql = "DELETE FROM clientes WHERE id = %(id)s"
    if execute_db_command(sql, {'id': cliente_id}, "✅ Cliente removido!") is not None:
        st.rerun()

def insert_produto(data: Dict[str, Any]):
    sql = """INSERT INTO produtos (sku, largura, altura, espessura, medidas, pigmento, modelo, material, peso, valor_kg, custo)
             VALUES (%(sku)s, %(largura)s, %(altura)s, %(espessura)s, %(medidas)s, %(pigmento)s, %(modelo)s, %(material)s, %(peso)s, %(valor_kg)s, %(custo)s)"""
    if execute_db_command(sql, data, "✅ Produto cadastrado!") is not None:
        st.rerun()

def update_produto(sku: str, data: Dict[str, Any]):
    data['current_sku'] = sku
    sql = """UPDATE produtos SET sku=%(sku)s, largura=%(largura)s, altura=%(altura)s, espessura=%(espessura)s, medidas=%(medidas)s,
             pigmento=%(pigmento)s, modelo=%(modelo)s, material=%(material)s, peso=%(peso)s, valor_kg=%(valor_kg)s, custo=%(custo)s
             WHERE sku=%(current_sku)s"""
    if execute_db_command(sql, data, "✅ Produto atualizado!") is not None:
        st.rerun()

def delete_produto(sku: str):
    sql = "DELETE FROM produtos WHERE sku = %(sku)s"
    if execute_db_command(sql, {'sku': sku}, "✅ Produto removido!") is not None:
        st.rerun()

def calcular_valores_produto(p_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        largura = int(p_data.get('largura', 0))
        altura = int(p_data.get('altura', 0))
        espessura = float(p_data.get('espessura', 0))
        valor_kg = float(p_data.get('valor_kg', 0))
        peso = math.ceil(largura * altura * espessura)
        custo = peso * valor_kg
        medidas = f"{largura} x {altura} x {espessura:.4f}"
        pigmento = p_data.get('pigmento', '').strip().upper()
        material = p_data.get('material', '').strip().upper()
        modelo = p_data.get('modelo', '').strip().upper()
        sku = f"{pigmento}-{material}-{largura}X{altura}X{espessura:.4f}-{modelo}"
        return {'peso': peso, 'custo': custo, 'medidas': medidas, 'sku': sku}
    except (ValueError, TypeError):
        return {'peso': 0, 'custo': 0, 'medidas': 'Inválido', 'sku': 'INVÁLIDO'}

def format_brl(value):
    if not isinstance(value, (int, float)): return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

def gerar_preview_numero_serie(tipo):
    if tipo == 'Pedido':
        return f"PED-{st.session_state.get('proximo_id_pedido', 1001)}"
    else:
        return f"ORC-{st.session_state.get('proximo_id_orcamento', 2001)}"

def update_order_status(pedido_id: int, new_status: str):
    if new_status == 'Faturado':
        generate_installments(pedido_id)
    
    sql = "UPDATE pedidos SET status = %(status)s WHERE id = %(id)s"
    if execute_db_command(sql, {'status': new_status, 'id': pedido_id}, f"✅ Status atualizado para {new_status}!") is not None:
        st.rerun()

def delete_order(pedido_id: int):
    sql = "DELETE FROM pedidos WHERE id = %(id)s"
    if execute_db_command(sql, {'id': pedido_id}, "🗑️ Documento excluído!") is not None:
        st.rerun()

def bulk_update_status(list_of_ids: List[int], new_status: str):
    if not list_of_ids: return
    
    if new_status == 'Faturado':
        for pedido_id in list_of_ids:
            generate_installments(pedido_id)

    sql = "UPDATE pedidos SET status = %s WHERE id IN %s"
    if execute_db_command(sql, (new_status, tuple(list_of_ids)), f"✅ {len(list_of_ids)} status atualizados!") is not None:
        st.rerun()

def bulk_delete_orders(list_of_ids: List[int]):
    if not list_of_ids: return
    sql = "DELETE FROM pedidos WHERE id IN %s"
    if execute_db_command(sql, (tuple(list_of_ids),), f"🗑️ {len(list_of_ids)} documentos excluídos!") is not None:
        st.rerun()

def convert_orcamento_to_pedido(orcamento_id: int):
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM pedidos WHERE id = %s", (orcamento_id,))
            orcamento = cur.fetchone()
            if not orcamento:
                st.error("Orçamento não encontrado.")
                return

            cur.execute("SELECT * FROM pedido_itens WHERE pedido_id = %s", (orcamento_id,))
            itens = cur.fetchall()

            next_pedido_num, _ = get_next_document_numbers()
            novo_numero_pedido = f"PED-{next_pedido_num}"
            
            sql_novo_pedido = """
                INSERT INTO pedidos (numero_documento, tipo_documento, cliente_id, data_emissao, custo_envio, valor_total, status, forma_pagamento, prazo_pagamento, prazo_entrega)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """
            cur.execute(sql_novo_pedido, (
                novo_numero_pedido, 'Pedido', orcamento['cliente_id'], orcamento['data_emissao'],
                orcamento['custo_envio'], orcamento['valor_total'], 'Aberto', orcamento['forma_pagamento'],
                orcamento['prazo_pagamento'], orcamento['prazo_entrega']
            ))
            novo_pedido_id = cur.fetchone()[0]

            for item in itens:
                sql_novo_item = """
                    INSERT INTO pedido_itens (pedido_id, produto_sku, descricao_item, quantidade_milheiro, preco_unitario, subtotal)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """
                cur.execute(sql_novo_item, (
                    novo_pedido_id, item['produto_sku'], item['descricao_item'], item['quantidade_milheiro'],
                    item['preco_unitario'], item['subtotal']
                ))

            cur.execute("UPDATE pedidos SET status = 'Aprovado' WHERE id = %s", (orcamento_id,))

        conn.commit()
        st.success(f"Orçamento convertido com sucesso para o Pedido Nº {novo_numero_pedido}!")
        load_data_from_sources.clear()
        st.rerun()

    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao converter orçamento: {e}")
    finally:
        conn.close()

def generate_installments(pedido_id: int):
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM contas_a_receber WHERE pedido_id = %s", (pedido_id,))
            if cur.fetchone():
                return

            cur.execute("SELECT valor_total, prazo_pagamento, data_emissao FROM pedidos WHERE id = %s", (pedido_id,))
            pedido = cur.fetchone()
            if not pedido or not pedido['prazo_pagamento']:
                st.warning(f"Pedido {pedido_id} sem prazo de pagamento definido. Parcelas não geradas.")
                return

            valor_total = pedido['valor_total']
            prazo_str = pedido['prazo_pagamento']
            data_emissao = pedido['data_emissao']
            
            prazos = []
            if prazo_str.lower() == 'à vista':
                prazos = [0]
            else:
                prazos = [int(p.strip()) for p in prazo_str.replace('dias', '').split('/')]

            num_parcelas = len(prazos)
            if num_parcelas == 0: return

            valor_parcela = round(valor_total / num_parcelas, 2)
            valor_primeira_parcela = valor_total - (valor_parcela * (num_parcelas - 1))

            for i, dias in enumerate(prazos):
                numero_parcela = i + 1
                data_vencimento = data_emissao + timedelta(days=dias)
                valor_a_inserir = valor_primeira_parcela if i == 0 else valor_parcela

                sql_insert = "INSERT INTO contas_a_receber (pedido_id, numero_parcela, valor_parcela, data_vencimento) VALUES (%s, %s, %s, %s);"
                cur.execute(sql_insert, (pedido_id, numero_parcela, valor_a_inserir, data_vencimento))
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao gerar parcelas: {e}")
    finally:
        conn.close()

def check_and_update_pedido_status(pedido_id: int):
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(id) FROM contas_a_receber WHERE pedido_id = %s AND status_pagamento != 'Pago'", (pedido_id,))
            pending_installments = cur.fetchone()[0]
            
            if pending_installments == 0:
                cur.execute("UPDATE pedidos SET status = 'Recebido' WHERE id = %s AND status = 'Faturado'", (pedido_id,))
                conn.commit()
                st.toast(f"Pedido quitado! Status atualizado para 'Recebido'.")
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao verificar e atualizar status do pedido: {e}")
    finally:
        conn.close()

def update_installment_status(installment_id: int, new_status: str, pedido_id: int):
    data_pagamento = date.today() if new_status == 'Pago' else None
    sql = "UPDATE contas_a_receber SET status_pagamento = %s, data_pagamento = %s WHERE id = %s"
    if execute_db_command(sql, (new_status, data_pagamento, installment_id), f"✅ Parcela atualizada!") is not None:
        if new_status == 'Pago':
            check_and_update_pedido_status(pedido_id)
        st.rerun()

def update_nota_fiscal_number(pedido_id: int, nf_number: str):
    sql = "UPDATE pedidos SET numero_nota_fiscal = %s WHERE id = %s"
    if execute_db_command(sql, (nf_number, pedido_id), "✅ Nº da Nota Fiscal salvo!") is not None:
        st.rerun()

def update_documento(pedido_id: int, pedido_data: Dict[str, Any], itens_data: List[Dict[str, Any]]):
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            sql_update_pedido = """
                UPDATE pedidos SET
                    cliente_id = %(cliente_id)s, data_emissao = %(data_emissao)s,
                    custo_envio = %(custo_envio)s, valor_total = %(valor_total)s,
                    forma_pagamento = %(forma_pagamento)s, prazo_pagamento = %(prazo_pagamento)s,
                    prazo_entrega = %(prazo_entrega)s
                WHERE id = %(id)s;
            """
            pedido_data['id'] = pedido_id
            cur.execute(sql_update_pedido, pedido_data)

            cur.execute("DELETE FROM pedido_itens WHERE pedido_id = %s", (pedido_id,))

            for item in itens_data:
                item_data_db = {
                    "pedido_id": pedido_id, "produto_sku": item['produto_sku'],
                    "descricao_item": str(item['descricao_completa']),
                    "quantidade_milheiro": item['quantidade_milheiro'],
                    "preco_unitario": item['preco_unitario'], "subtotal": item['subtotal']
                }
                sql_insert_item = """
                    INSERT INTO pedido_itens (pedido_id, produto_sku, descricao_item, quantidade_milheiro, preco_unitario, subtotal)
                    VALUES (%(pedido_id)s, %(produto_sku)s, %(descricao_item)s, %(quantidade_milheiro)s, %(preco_unitario)s, %(subtotal)s);
                """
                cur.execute(sql_insert_item, item_data_db)
        
        conn.commit()
        st.success("✅ Documento atualizado com sucesso!")
        load_data_from_sources.clear()
        
        if 'editing_id' in st.session_state:
            del st.session_state['editing_id']
        
        st.rerun()

    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao atualizar o documento: {e}")
    finally:
        conn.close()

# --- FUNÇÕES DO DASHBOARD ---

@st.cache_data(ttl=600)
def get_dashboard_metrics():
    conn = get_db_connection()
    if not conn:
        return {'faturamento_mes': 0, 'faturamento_ano': 0, 'ticket_medio_mes': 0, 'a_receber': 0, 'vencido': 0, 'em_producao': 0}
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            today = date.today()
            
            cur.execute("""
                SELECT SUM(valor_total), COUNT(id) FROM pedidos 
                WHERE status = 'Faturado' AND EXTRACT(MONTH FROM data_emissao) = %s AND EXTRACT(YEAR FROM data_emissao) = %s
            """, (today.month, today.year))
            faturamento_mes, pedidos_mes = cur.fetchone()
            faturamento_mes = faturamento_mes or 0
            ticket_medio_mes = (faturamento_mes / pedidos_mes) if pedidos_mes else 0

            cur.execute("SELECT SUM(valor_total) FROM pedidos WHERE status = 'Faturado' AND EXTRACT(YEAR FROM data_emissao) = %s", (today.year,))
            faturamento_ano = cur.fetchone()[0] or 0

            cur.execute("SELECT SUM(valor_parcela) FROM contas_a_receber WHERE status_pagamento != 'Pago'")
            a_receber = cur.fetchone()[0] or 0
            
            cur.execute("SELECT SUM(valor_parcela) FROM contas_a_receber WHERE status_pagamento = 'Em Aberto' AND data_vencimento < %s", (today,))
            vencido = cur.fetchone()[0] or 0

            cur.execute("SELECT COUNT(id) FROM pedidos WHERE status = 'Em Produção'")
            em_producao = cur.fetchone()[0] or 0

        return {
            'faturamento_mes': float(faturamento_mes), 'faturamento_ano': float(faturamento_ano),
            'ticket_medio_mes': float(ticket_medio_mes), 'a_receber': float(a_receber),
            'vencido': float(vencido), 'em_producao': int(em_producao)
        }
    except Exception as e:
        st.error(f"Erro ao buscar métricas do dashboard: {e}")
        return {'faturamento_mes': 0, 'faturamento_ano': 0, 'ticket_medio_mes': 0, 'a_receber': 0, 'vencido': 0, 'em_producao': 0}
    finally:
        if conn: conn.close()

@st.cache_data(ttl=600)
def get_monthly_revenue_chart_data():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    try:
        query = """
            SELECT
                to_char(date_trunc('month', p.data_emissao), 'YYYY-MM') as mes,
                SUM(p.valor_total) as faturamento
            FROM pedidos p
            WHERE p.status = 'Faturado' AND p.data_emissao >= date_trunc('month', current_date) - interval '11 month'
            GROUP BY mes ORDER BY mes;
        """
        df = pd.read_sql(query, conn)
        df['mes'] = pd.to_datetime(df['mes']).dt.strftime('%b/%Y')
        df.set_index('mes', inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao buscar faturamento mensal: {e}")
        return pd.DataFrame()
    finally:
        if conn: conn.close()

@st.cache_data(ttl=600)
def get_upcoming_installments():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    try:
        query = """
            SELECT cr.data_vencimento, cr.valor_parcela, c.nome_fantasia
            FROM contas_a_receber cr
            JOIN pedidos p ON cr.pedido_id = p.id
            JOIN clientes c ON p.cliente_id = c.id
            WHERE cr.status_pagamento != 'Pago' AND cr.data_vencimento >= current_date
            ORDER BY cr.data_vencimento ASC
            LIMIT 5;
        """
        return pd.read_sql(query, conn)
    except Exception as e:
        st.error(f"Erro ao buscar próximas contas a vencer: {e}")
        return pd.DataFrame()
    finally:
        if conn: conn.close()

@st.cache_data(ttl=600)
def get_recent_faturados():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    try:
        query = """
            SELECT p.numero_documento, p.data_emissao, c.nome_fantasia, p.valor_total
            FROM pedidos p
            JOIN clientes c ON p.cliente_id = c.id
            WHERE p.status = 'Faturado'
            ORDER BY p.data_emissao DESC, p.id DESC
            LIMIT 5;
        """
        return pd.read_sql(query, conn)
    except Exception as e:
        st.error(f"Erro ao buscar pedidos recentes: {e}")
        return pd.DataFrame()
    finally:
        if conn: conn.close()

