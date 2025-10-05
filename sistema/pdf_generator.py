from fpdf import FPDF
import pandas as pd
from datetime import timedelta
import ast

class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.company_name = "Caramuru Sacolas e Representações Ltda"
        self.company_address = "Rua Ilsa Becker 411 - Bom Pastor"
        self.company_city = "Igrejinha - RS, CEP 95650-000"
        self.company_contact = "Telefone: (51) 99645-9933 | Email: contato@neysacolas.com.br"
        self.company_cnpj = "CNPJ: 11.258.592/0001-62"
        try:
            self.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            self.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf', uni=True)
            self.font_family = 'DejaVu'
        except RuntimeError:
            self.font_family = 'Arial'
            print("AVISO: Fonte DejaVuSans.ttf não encontrada. Usando Arial como fallback.")

    def header(self):
        self.set_font(self.font_family, 'B', 14)
        self.cell(40)
        self.cell(150, 8, self.company_name, 0, 1, 'R')
        self.set_font(self.font_family, '', 9)
        self.cell(40)
        self.cell(150, 5, self.company_address, 0, 1, 'R')
        self.cell(40)
        self.cell(150, 5, self.company_city, 0, 1, 'R')
        self.cell(40)
        self.cell(150, 5, self.company_cnpj, 0, 1, 'R')
        self.ln(10)
        self.line(10, 45, 200, 45)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_font(self.font_family, '', 8)
        self.ln(2)
        self.cell(0, 5, self.company_contact, 0, 1, 'C')
        self.cell(0, 5, f'Página {self.page_no()}/{{nb}}', 0, 0, 'C')

    def info_block(self, pedido_info, cliente_info):
        self.set_font(self.font_family, 'B', 10)
        self.cell(90, 7, "CLIENTE", 1, 0, 'C')
        self.cell(10)
        self.cell(90, 7, "DETALHES DO DOCUMENTO", 1, 1, 'C')

        self.set_font(self.font_family, '', 9)
        y_start = self.get_y()
        self.multi_cell(90, 5, 
            f"Nome Fantasia: {cliente_info.get('nome_fantasia', '')}\n"
            f"Razão Social: {cliente_info.get('razao_social', '')}\n"
            f"CNPJ: {format_cnpj_for_pdf(cliente_info.get('cnpj_cpf', ''))}\n"
            f"Endereço: {cliente_info.get('logradouro_num', '')}, {cliente_info.get('bairro', '')}\n"
            f"Cidade: {cliente_info.get('cidade', '')} - {cliente_info.get('uf', '')}",
            1, 'L')

        self.set_y(y_start)
        self.set_x(110)

        data_emissao = pd.to_datetime(pedido_info.get('data_emissao'))
        prazo_entrega_val = pedido_info.get('prazo_entrega')
        prazo_entrega = int(prazo_entrega_val) if prazo_entrega_val is not None else 30
        data_entrega_prevista = data_emissao + timedelta(days=prazo_entrega)
        
        pagamento_str = f"{pedido_info.get('forma_pagamento', '')} ({pedido_info.get('prazo_pagamento', '')})"

        self.multi_cell(90, 5,
            f"Data de Emissão: {data_emissao.strftime('%d/%m/%Y')}\n"
            f"Entrega Prevista: {data_entrega_prevista.strftime('%d/%m/%Y')}\n"
            f"Cond. Pagamento: {pagamento_str}",
            1, 'L')
        self.ln(10)
    
    def items_table(self, itens_df):
        self.set_font(self.font_family, 'B', 10)
        self.set_fill_color(220, 220, 220)
        
        col_widths = [95, 25, 35, 35]
        headers = ['Descrição', 'Qtde (M)', 'Preço Unit. (R$)', 'Subtotal (R$)']
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 8, header, 1, 0, 'C', fill=True)
        self.ln()

        self.set_font(self.font_family, '', 9)
        self.set_fill_color(245, 245, 245)
        fill = True
        
        for _, row in itens_df.iterrows():
            fill = not fill
            
            desc_data_raw = row.get('descricao_completa') if isinstance(row.get('descricao_completa'), dict) else row.get('descricao_item', '{}')
            try:
                desc_data = ast.literal_eval(desc_data_raw) if isinstance(desc_data_raw, str) else desc_data_raw
            except:
                desc_data = {}

            desc_line1 = f"{desc_data.get('pigmento', '')} {desc_data.get('material', '')} - {desc_data.get('medidas', '')} - Alça {desc_data.get('modelo', '')}"
            desc_line2 = f"Impressão: {desc_data.get('num_cores')} Cor(es): {desc_data.get('nomes_cores', '')} | {desc_data.get('lados')}"

            start_y = self.get_y()
            self.multi_cell(col_widths[0], 5, f"{desc_line1}\n{desc_line2}", 1, 'L', fill=fill)
            row_height = self.get_y() - start_y
            
            self.set_xy(10 + col_widths[0], start_y)
            self.cell(col_widths[1], row_height, f"{float(row.get('quantidade_milheiro', 0)):.3f}", 1, 0, 'C', fill=fill)
            self.cell(col_widths[2], row_height, f"R$ {float(row.get('preco_unitario', 0)) / 1000:.2f}", 1, 0, 'R', fill=fill)
            self.cell(col_widths[3], row_height, f"R$ {float(row.get('subtotal', 0)):.2f}", 1, 1, 'R', fill=fill)
            
    def totals_and_observations(self, pedido_info, itens_df):
        self.ln(5)
        subtotal_geral = float(itens_df['subtotal'].sum())
        custo_envio = float(pedido_info.get('custo_envio', 0))
        valor_total = float(pedido_info.get('valor_total', 0))

        self.set_font(self.font_family, 'B', 8)
        self.cell(100, 5, "OBSERVAÇÕES:", 0, 0, 'L')
        self.set_x(120)
        self.set_font(self.font_family, '', 10)
        self.cell(40, 7, 'Subtotal Produtos:', 0, 0, 'R')
        self.cell(40, 7, f"R$ {subtotal_geral:.2f}", 0, 1, 'R')

        self.set_font(self.font_family, '', 8)
        self.multi_cell(100, 4, "APÓS APROVADO, O PEDIDO NÃO PODERÁ SER ALTERADO!\nAS QUANTIDADES PODERÃO VARIAR EM ATÉ 10%, QUE SERÃO DEVIDAMENTE FATURADAS AO CLIENTE.", 0, 'L')
        
        y_pos = self.get_y()
        self.set_y(y_pos - 7)
        self.set_x(120)

        self.set_font(self.font_family, '', 10)
        self.cell(40, 7, 'Custo de Envio:', 0, 0, 'R')
        self.cell(40, 7, f"R$ {custo_envio:.2f}", 0, 1, 'R')
        self.set_x(120)
        self.set_font(self.font_family, 'B', 12)
        self.cell(40, 8, 'TOTAL GERAL:', 0, 0, 'R')
        self.cell(40, 8, f"R$ {valor_total:.2f}", 0, 1, 'R')

def format_cnpj_for_pdf(doc: str) -> str:
    if doc is None or not isinstance(doc, str): return ""
    doc_clean = "".join(filter(str.isdigit, doc))
    if len(doc_clean) == 14:
        return f"{doc_clean[:2]}.{doc_clean[2:5]}.{doc_clean[5:8]}/{doc_clean[8:12]}-{doc_clean[12:14]}"
    return doc_clean

def generate_pdf(pedido_info, itens_df, cliente_info):
    pdf = PDF(orientation='P', unit='mm', format='A4')
    
    pdf.alias_nb_pages()
    pdf.add_page()
    
    pdf.set_font(pdf.font_family, 'B', 18)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 12, f'{str(pedido_info.get("tipo_documento", "")).upper()} Nº {pedido_info.get("numero_documento", "")}', 0, 1, 'C', fill=True)
    pdf.ln(7)

    pdf.info_block(pedido_info, cliente_info)
    pdf.items_table(itens_df)
    pdf.totals_and_observations(pedido_info, itens_df)
    
    return bytes(pdf.output())