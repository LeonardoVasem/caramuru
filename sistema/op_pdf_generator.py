from fpdf import FPDF
import pandas as pd
from datetime import timedelta
import ast

class OP_PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.company_name = "Caramuru Sacolas e Representações Ltda"
        try:
            self.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            self.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf', uni=True)
            self.font_family = 'DejaVu'
        except RuntimeError:
            self.font_family = 'Arial'
            print("AVISO: Fonte DejaVuSans.ttf não encontrada. Usando Arial como fallback.")

    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_family, '', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def draw_half_page_card(self, item_info, y_offset=0):
        try:
            desc_data = ast.literal_eval(item_info['descricao_item'])
        except (ValueError, SyntaxError):
            desc_data = {}

        prazo_entrega_val = item_info.get('prazo_entrega')
        prazo_entrega = int(prazo_entrega_val) if prazo_entrega_val is not None else 30
        data_emissao = pd.to_datetime(item_info.get('data_emissao'))
        data_entrega_prevista = data_emissao + timedelta(days=prazo_entrega)
        
        # --- Borda Externa ---
        self.rect(10, 10 + y_offset, 190, 128.5)
        
        # --- Bloco do Título ---
        self.set_y(12 + y_offset)
        self.set_font(self.font_family, 'B', 18)
        self.cell(0, 12, "ORDEM DE PRODUÇÃO", 'B', 1, 'C')
        self.ln(5)

        # --- Bloco de Informações do Pedido ---
        self.set_font(self.font_family, '', 10)
        self.cell(95, 7, f"Pedido de Venda: {item_info['numero_documento']}", 0, 0, 'L')
        self.cell(95, 7, f"Data de Emissão: {data_emissao.strftime('%d/%m/%Y')}", 0, 1, 'R')
        self.ln(3)
        
        # --- Blocos de Destaque (Cliente e Entrega) ---
        y_pos_boxes = self.get_y()
        self.set_xy(10, y_pos_boxes)
        self.set_font(self.font_family, 'B', 9)
        self.set_fill_color(240, 240, 240)
        self.cell(120, 6, "CLIENTE", 1, 2, 'C', fill=True)
        self.set_font(self.font_family, 'B', 20)
        self.multi_cell(120, 12, item_info['nome_fantasia'], 1, 'C')

        self.set_xy(135, y_pos_boxes)
        self.set_font(self.font_family, 'B', 9)
        self.cell(65, 6, "ENTREGA PREVISTA", 1, 2, 'C', fill=True)
        self.set_font(self.font_family, 'B', 20)
        self.multi_cell(65, 12, data_entrega_prevista.strftime('%d/%m/%Y'), 1, 'C')
        self.ln(5)

        # --- Bloco de Especificações ---
        self.set_font(self.font_family, 'B', 11)
        self.cell(0, 7, "Especificações de Produção", 0, 1, 'L')
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)

        def spec_row(label, value, is_bold=False):
            self.set_font(self.font_family, 'B', 10)
            self.cell(30, 6, label, 0, 0, 'L')
            font_style = 'B' if is_bold else ''
            self.set_font(self.font_family, font_style, 10)
            self.cell(160, 6, str(value), 0, 1, 'L')

        spec_row("Pigmento:", desc_data.get('pigmento', ''))
        spec_row("Material:", desc_data.get('material', ''))
        spec_row("Alça:", desc_data.get('modelo', ''))
        spec_row("Medidas:", desc_data.get('medidas', ''))
        
        quantidade_unidades = int(item_info['quantidade_milheiro'] * 1000)
        spec_row("Quantidade:", f"{quantidade_unidades:,}".replace(',', '.') + " Unidades", is_bold=True)
        self.ln(4)
        
        self.set_font(self.font_family, 'B', 11)
        self.cell(0, 7, "Especificações de Impressão", 0, 1, 'L')
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)

        spec_row("Cores:", desc_data.get('nomes_cores', ''))
        spec_row("Lados:", desc_data.get('lados', ''))
        self.ln(4)

def generate_op_pdf(items_info):
    pdf = OP_PDF(orientation='P', unit='mm', format='A4')
    pdf.alias_nb_pages()
    
    if not isinstance(items_info, list):
        items_info = [items_info]

    y_offset = 0
    card_height = 148.5
    
    for i, item in enumerate(items_info):
        if i % 2 == 0:
            pdf.add_page()
            y_offset = 0
        else:
            y_offset = card_height
        
        pdf.draw_half_page_card(item, y_offset)
        
        if i % 2 == 0 and i + 1 < len(items_info):
            pdf.set_line_width(0.1)
            pdf.set_draw_color(180, 180, 180)
            pdf.dashed_line(5, card_height, 205, card_height, dash_length=2, space_length=2)
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.2)

    return bytes(pdf.output())

