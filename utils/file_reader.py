# 文件路径: utils/file_reader.py
import pdfplumber
import docx
import re

class PDFPageData:
    """定义PDF页面数据结构，对应 core.js 中的 pageContents 元素"""
    def __init__(self):
        self.page_num = 0
        self.width = 0
        self.height = 0
        self.text = ""
        self.lines = []   # 文本行对象
        self.rects = []   # 图形线条（对应 graphicLines）
        self.has_image = False

def read_word(file_obj):
    """
    对应 core.js -> loadWordWithProgress
    解析 Word 文件
    """
    try:
        doc = docx.Document(file_obj)
        return doc
    except Exception as e:
        print(f"Word 读取错误: {e}")
        return None

def read_pdf(file_obj):
    """
    对应 core.js -> loadPDFWithProgress & processPage
    使用 pdfplumber 解析 PDF，提取文字、坐标、字体和线条
    """
    parsed_pages = []
    
    try:
        with pdfplumber.open(file_obj) as pdf:
            for i, page in enumerate(pdf.pages):
                data = PDFPageData()
                data.page_num = i + 1
                data.width = page.width
                data.height = page.height
                data.text = page.extract_text()
                
                # 1. 提取文字行信息 (对应 JS 的 textContent)
                # pdfplumber 的 extract_words 包含 x0, top, bottom, fontname, size
                words = page.extract_words(keep_blank_chars=True, extra_attrs=['fontname', 'size'])
                data.lines = words # 这里简化处理，实际可能需要按 Y 轴聚合
                
                # 2. 提取图形线条 (对应 JS 的 extractAllLinesWithMatrix)
                # pdfplumber 直接提供 .lines 和 .rects
                data.rects = page.lines + page.rects
                
                # 3. 检测图片 (对应 JS 的 detectImages)
                data.has_image = len(page.images) > 0
                
                parsed_pages.append(data)
                
        return parsed_pages
    except Exception as e:
        print(f"PDF 读取错误: {e}")
        return []

def build_chapter_map(pages):
    """
    对应 core.js -> buildChapterMap
    构建章节索引
    """
    chapter_map = []
    # 正则匹配 "第 x 章"
    regex = re.compile(r'(?:^|\n)\s*第\s*(\d+)\s*章')
    
    for idx, page in enumerate(pages):
        # 取前几行文本检查
        text_start = page.text[:200] if page.text else ""
        match = regex.search(text_start)
        
        if match:
            num = int(match.group(1))
            # 简单的去重逻辑
            if not chapter_map or chapter_map[-1]['num'] != num:
                chapter_map.append({'num': num, 'start_page': idx})
    
    # 补全 end_page
    for i in range(len(chapter_map)):
        if i < len(chapter_map) - 1:
            chapter_map[i]['end_page'] = chapter_map[i+1]['start_page'] - 1
        else:
            chapter_map[i]['end_page'] = len(pages) - 1
            
    return chapter_map