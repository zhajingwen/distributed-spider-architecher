import os
import sys
import fitz  # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter

import os

# 获取当前目录路径
current_directory = os.getcwd()

# 列出当前目录的所有文件和文件夹
files_and_folders = os.listdir(current_directory)

print(files_and_folders)


def trim_pdf(file_path, skip_front, skip_back, output_path):
    """
    切掉首尾垃圾信息
    """
    # 打开PDF文件
    reader = PdfReader(file_path)
    total_pages = len(reader.pages)

    # 创建PDF写入器
    writer = PdfWriter()

    # 计算需要写入的页码范围
    start_page = skip_front
    end_page = total_pages - skip_back

    # 添加指定范围的页面到新的PDF
    for i in range(start_page, end_page):
        writer.add_page(reader.pages[i])

    # 写入到新的PDF文件
    with open(output_path, 'wb') as f:
        writer.write(f)


def merge_pdfs(pdf_path1, pdf_path2, output_path):
    """
    合并2个PDF文件
    """
    # 创建一个PDF写入器对象
    writer = PdfWriter()

    # 加载第一个PDF文件并添加到写入器
    reader1 = PdfReader(pdf_path1)
    for page in reader1.pages:
        writer.add_page(page)

    # 加载第二个PDF文件并添加到写入器
    reader2 = PdfReader(pdf_path2)
    for page in reader2.pages:
        writer.add_page(page)

    # 将合并的PDF输出到一个新文件
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)




def split_pdf(file_path, output_path1, output_path2):
    """
    将大文件 PDF 切割成两份
    """
    # 打开PDF文件
    document = fitz.open(file_path)
    total_pages = document.page_count
    mid_point = total_pages // 2

    # 创建第一个输出PDF
    writer1 = fitz.open()
    for i in range(mid_point):
        writer1.insert_pdf(document, from_page=i, to_page=i)

    # 创建第二个输出PDF
    writer2 = fitz.open()
    for i in range(mid_point, total_pages):
        writer2.insert_pdf(document, from_page=i, to_page=i)

    # 保存输出PDF文件
    writer1.save(output_path1)
    writer2.save(output_path2)

    # 关闭文档
    document.close()
    writer1.close()
    writer2.close()

# 原始文件名
source_filename = 'Thermoinfocomplexity_A_Comp.pdf'



# 要切掉的首位页数
head = 0
bottom = 8


# 剔除文头，文尾
f'tools/{source_filename}'
trim_pdf(source_filename, head, bottom, f'cutted {source_filename}')
# trim_pdf(source_filename, head, bottom, source_filename)


# 合并
# merge_pdfs('1.pdf', '2.pdf', 'Kondratieff Waves, Warfare and World Security .pdf')


# 大PDF切割成2份
# split_pdf(source_filename, f'part1 {source_filename}', f'part2 {source_filename}')
