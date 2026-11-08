import re
from fpdf import FPDF

"""
由于DeepL限制文件大小为20M，某些特别大的PDF无法被处理
1、将PDF转换为TXT
2、将TXT转换为PDF
"""

class PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

class Topdf:
    def __init__(self, pdf_source_path, txt_file_path):
        # PDF文件路径
        self.pdf_file = pdf_source_path
        # 输出的TXT文件路径
        self.txt_file = txt_file_path

    def optimize_text(self, text):
        # 用正则表达式替换不合理的换行符
        optimized_text = re.sub(r'([^\.\!\?])\n', r'\1 ', text)
        return optimized_text

    def to_pdf(self):
        # 创建PDF对象
        pdf = PDF()
        pdf.set_left_margin(10)
        pdf.set_right_margin(10)
        pdf.add_page()

        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)

        # 读取TXT文件并优化文本内容
        with open(self.txt_file, 'r', encoding='utf-8') as file:
            text = file.read()
            optimized_text = self.optimize_text(text)

        # 将优化后的文本添加到PDF
        for line in optimized_text.split('\n'):
            cleaned_line = line.encode('latin-1', 'ignore').decode('latin-1')
            pdf.multi_cell(0, 10, cleaned_line)

        # 保存PDF文件
        pdf.output(self.pdf_file)
        print(f"TXT内容已成功保存到 {self.pdf_file}")
