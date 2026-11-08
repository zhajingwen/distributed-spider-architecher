import fitz  # PyMuPDF

"""
由于DeepL限制文件大小为20M，某些特别大的PDF无法被处理
1、将PDF转换为TXT

"""

class Totxt:

    def __init__(self, pdf_source_path, txt_file_path):

        # PDF文件路径
        self.pdf_file = pdf_source_path
        # 输出的TXT文件路径
        self.txt_file = txt_file_path

    def is_header_or_footer(self, block, page_height, margin=50):
        # 判断文本块是否位于页眉或页脚位置
        block_y0 = block['bbox'][1]
        block_y1 = block['bbox'][3]
        return block_y1 < margin or block_y0 > page_height - margin


    def to_txt(self):

        # 打开PDF文件
        pdf_document = fitz.open(self.pdf_file)

        # 创建或打开TXT文件
        with open(self.txt_file, 'w', encoding='utf-8') as output_file:
            # 遍历每一页
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                page_height = page.rect.height

                # 获取页面中的文本块
                blocks = page.get_text("dict")["blocks"]

                for block in blocks:
                    if not self.is_header_or_footer(block, page_height):
                        if "lines" in block:
                            for line in block["lines"]:
                                for span in line["spans"]:
                                    output_file.write(span["text"])
                                output_file.write('\n')
                output_file.write('\n')  # 每页之间添加一个换行符
            print(f"PDF内容已成功保存到 {self.txt_file}")
