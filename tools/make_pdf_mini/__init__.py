from .pdf_to_txt import Totxt
from .txt_to_pdf import Topdf

def run():
    # 输出的PDF文件路径
    pdf_file = 'path/to/your/output.pdf'
    # TXT文件路径
    txt_file = 'path/to/your/file.txt'
    Totxt(pdf_file, txt_file).to_txt()
    Topdf(pdf_file, txt_file).to_pdf()



