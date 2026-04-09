import re
import pdfplumber
import io

# ========== 【专属读取函数，和原始代码完全一致】 ==========
def read_pdf_with_font_size(pdf_file):
    pdf_pages = []
    try:
        if isinstance(pdf_file, (str, io.BytesIO)):
            pdf = pdfplumber.open(pdf_file)
        else:
            pdf = pdfplumber.open(io.BytesIO(pdf_file.getvalue()))
        for page in pdf.pages:
            page_data = {
                "page_num": page.page_number,
                "text": page.extract_text(),
                "images": page.images,
                "tables": page.extract_tables(),
                "chars": page.chars,
            }
            pdf_pages.append(page_data)
        pdf.close()
        return pdf_pages
    except Exception as e:
        print(f"专属读取函数运行异常：{e}")
        return []

# ========== 统一配置项，和原始代码完全一致 ==========
STANDARD_FONT_SIZE = 12
STANDARD_FIRST_LINE = 31
STANDARD_MIDDLE_LINE = 33
STANDARD_PAGE_LINE_COUNT = 33
CODE_ENGLISH_THRESHOLD = 0.5

# ==================== 行字数检测规则，完全不动 ====================
VALID_CONTENT_PATTERN = re.compile(r"^[\u4e00-\u9fa5。，、；：？！“”‘’（）【】]+$")
SKIP_CHAR_PATTERN = re.compile(r"[0-9a-zA-Z]|——|……")
SKIP_KEYWORD_PATTERN = re.compile(r"毕业设计|论文|摘要|关键词|参考文献|致谢|目录|附录|注释")

# ==================== 标题过滤规则，完全不动 ====================
PAGE_SKIP_TRIGGER = re.compile(
    r"第\d+章|^\d+\.\s*[\u4e00-\u9fa5]|^\d+\.\d+\s*[\u4e00-\u9fa5]|^\d+\.\d+\.\d+\s*[\u4e00-\u9fa5]|^[（(]\d+[）)]\s*[\u4e00-\u9fa5]|绪论|课题背景|研究现状|目的和意义|课题目的|方案设计|实验验证|结\s*论|致\s*谢|本章小结|本章总结",
    re.MULTILINE
)
# 【精准匹配：只匹配阿拉伯数字2的第2章，兼容任意空格】
CHAPTER2_MATCH = re.compile(r"第\s*2\s*章")
# 终极跳过规则，完全不动
FINAL_SKIP_TRIGGER = re.compile(r"结\s*论|致\s*谢|参考文献|附录")
# 图表过滤规则，完全不动
FIGURE_TABLE_FILTER = re.compile(
    r"图\d+-\d+|图 \d+-\d+|表\d+-\d+|表 \d+-\d+|如图.*?所示|如表.*?所示|如下图所示|如下表所示|附图\d+|附表\d+|拓扑图|流程图|活动图|用例图",
    re.MULTILINE
)
# 其他过滤规则，完全不动
HEADER_PATTERN = re.compile(r"哈尔滨华德学院本科毕业设计（论文）")
FOOTER_PATTERN = re.compile(r"^\d+$")
CODE_ENGLISH_PATTERN = re.compile(r"[0-9a-zA-Z{}();=+\-*/\[\]<>]")

# ========== 字号判断函数，完全不动 ==========
def page_has_large_font_title(page):
    try:
        chars = page.get("chars", [])
        for char in chars:
            font_size = char.get("size", 0)
            if font_size > STANDARD_FONT_SIZE:
                return True
    except:
        return False
    return False

# ========== 代码/英文页判断，完全不动 ==========
def is_code_english_page(page_text):
    if not page_text:
        return False
    total_chars = len(page_text)
    if total_chars == 0:
        return False
    code_english_chars = len(CODE_ENGLISH_PATTERN.findall(page_text))
    ratio = code_english_chars / total_chars
    return ratio >= CODE_ENGLISH_THRESHOLD

# ========== 【过滤规则：唯一特殊规则仅跳过「下一页是第2章」的当前页】 ==========
def is_page_skip_total_line_check(page, page_raw_text, is_last_page, has_encountered_final, next_page_is_chapter2):
    """
    唯一特殊规则：当前页的下一页是第2章 → 跳过（第一章末尾页）
    其他所有规则100%还原原始代码，无任何额外过滤
    """
    # 1. 终极规则：结论/致谢后续页全跳过
    if has_encountered_final:
        return True, "结论/致谢/参考文献后续页"
    # 2. 带图表/表格 → 跳过
    if len(page.get("images", [])) > 0 or len(page.get("tables", [])) > 0:
        return True, "带图表/表格对象"
    # 3. 大字号标题 → 跳过
    if page_has_large_font_title(page):
        return True, "检测到大字号标题"
    # 4. 标题/本章小结关键词 → 跳过
    if PAGE_SKIP_TRIGGER.search(page_raw_text):
        return True, "匹配到标题/章节/本章小结关键词"
    # 5. 【完全按你的要求：下一页是第2章 → 跳过】
    if next_page_is_chapter2:
        return True, "当前页为第一章末尾页，下一页是第2章起始页"
    # 6. 其他兜底规则，完全不动
    if FIGURE_TABLE_FILTER.search(page_raw_text):
        return True, "带图表/表格相关内容"
    if is_code_english_page(page_raw_text):
        return True, "代码/英文附录页"
    if is_last_page:
        return True, "论文最后一页"
    # 都不符合，进入总行数检测
    return False, "纯正文页"

# ========== 【check入口函数，核心修改：拆分两个模块，加专属隔断】 ==========
def check(pdf_pages, detected_offset=0, pdf_file=None):
    # 优先用专属函数读取PDF
    if pdf_file is not None:
        detect_pdf_pages = read_pdf_with_font_size(pdf_file)
    else:
        detect_pdf_pages = pdf_pages
    if not detect_pdf_pages:
        return [{"type": "error", "msg": "PDF读取失败，请检查文件"}]

    line_word_issues = []
    page_line_issues = []
    total_line_check_pages = 0
    total_line_error = 0
    total_page_check_pages = 0
    total_page_pass = 0
    skip_log = []
    total_pdf_pages = len(detect_pdf_pages)
    has_encountered_final = False

    # 遍历正文页，检测逻辑完全不动
    for page_idx, page in enumerate(detect_pdf_pages[detected_offset:]):
        current_page_num = detected_offset + page_idx + 1
        is_last_page = (detected_offset + page_idx) == (total_pdf_pages - 1)
        page_raw_text = page.get("text", "")

        # 【核心逻辑：检测当前页的下一页是不是第2章】
        next_page_is_chapter2 = False
        next_page_index = detected_offset + page_idx + 1
        if next_page_index < total_pdf_pages:
            next_page_text = detect_pdf_pages[next_page_index].get("text", "")
            if CHAPTER2_MATCH.search(next_page_text):
                next_page_is_chapter2 = True
                skip_log.append(f"✅ 检测到PDF第{next_page_index+1}页为第2章起始页，当前页{current_page_num}为第一章末尾页")

        # ==============================================
        # 【行字数检测，逻辑完全不动】
        # ==============================================
        page_has_image = len(page.get("images", [])) > 0
        page_has_table = len(page.get("tables", [])) > 0
        if not page_has_image and not page_has_table:
            total_line_check_pages += 1
            text_lines = [line for line in page_raw_text.split('\n') if line.strip()]
            if len(text_lines) >= 2:
                valid_content_lines = []
                for line_text in text_lines:
                    stripped_line = line_text.strip()
                    if SKIP_KEYWORD_PATTERN.search(stripped_line):
                        continue
                    if SKIP_CHAR_PATTERN.search(stripped_line):
                        continue
                    if not VALID_CONTENT_PATTERN.match(stripped_line):
                        continue
                    valid_content_lines.append({
                        "text": line_text,
                        "length": len(stripped_line),
                        "page_num": current_page_num
                    })
                # 逐行检测行字数，逻辑完全不动
                total_valid_lines = len(valid_content_lines)
                if total_valid_lines >= 2:
                    for line_idx, line in enumerate(valid_content_lines):
                        line_len = line["length"]
                        page_num = line["page_num"]
                        line_text = line["text"]
                        is_last_line = (line_idx == total_valid_lines - 1)
                        # 段尾行跳过
                        is_end_line = False
                        if line_len < STANDARD_FIRST_LINE:
                            is_end_line = True
                        elif line_len == STANDARD_FIRST_LINE and is_last_line:
                            is_end_line = True
                        elif line_len == STANDARD_FIRST_LINE and not is_last_line:
                            next_len = valid_content_lines[line_idx + 1]["length"]
                            if next_len == STANDARD_FIRST_LINE:
                                is_end_line = True
                        elif line_len == STANDARD_MIDDLE_LINE and not is_last_line:
                            next_len = valid_content_lines[line_idx + 1]["length"]
                            if next_len == STANDARD_FIRST_LINE:
                                is_end_line = True
                        if is_end_line:
                            continue
                        # 段首行校验
                        if line_len == STANDARD_FIRST_LINE:
                            if line_len != STANDARD_FIRST_LINE:
                                line_word_issues.append({
                                    "type": "error",
                                    "msg": f"PDF第{page_num}页 段落首行：共{line_len}字（需31字）\n原文：{line_text.strip()}"
                                })
                                total_line_error += 1
                            continue
                        # 中间行校验
                        if line_len != STANDARD_MIDDLE_LINE:
                            line_word_issues.append({
                                "type": "error",
                                "msg": f"PDF第{page_num}页 正文中间行：共{line_len}字（需33字）\n原文：{line_text.strip()}"
                            })
                            total_line_error += 1

        # ==============================================
        # 【每页行数检测，逻辑完全不动】
        # ==============================================
        if FINAL_SKIP_TRIGGER.search(page_raw_text):
            has_encountered_final = True
            skip_log.append(f"第{current_page_num}页：检测到结论/致谢/参考文献，后续所有页全部跳过总行数检测")
            continue
        is_skip, skip_reason = is_page_skip_total_line_check(
            page, page_raw_text, is_last_page, has_encountered_final,
            next_page_is_chapter2
        )
        if is_skip:
            skip_log.append(f"第{current_page_num}页：{skip_reason}，跳过总行数检测")
            continue
        total_page_check_pages += 1
        all_raw_lines = page_raw_text.split('\n')
        valid_total_lines = []
        for line in all_raw_lines:
            if HEADER_PATTERN.search(line):
                continue
            if FOOTER_PATTERN.match(line.strip()):
                continue
            if line == "":
                continue
            valid_total_lines.append(line)
        page_total_line = len(valid_total_lines)
        if page_total_line == STANDARD_PAGE_LINE_COUNT:
            total_page_pass += 1
        else:
            page_line_issues.append({
                "type": "error",
                "msg": f"PDF第{current_page_num}页 正文总行数不符合规范：共{page_total_line}行（需{STANDARD_PAGE_LINE_COUNT}行）"
            })

    # ==============================================
    # 【核心修改：拆分两个模块，加专属隔断，独立展示】
    # ==============================================
    final_result = []
    # 1. 第一模块：行字数规范检测（独立报告+专属报错）
    line_report_html = f"""
    <div style="padding: 12px; border-radius: 8px; background: #f0f9ff; margin-bottom: 15px; border-left: 4px solid #0ea5e9;">
    <h4>📝 行字数规范检测</h4>
    <p>有效检测页：<b>{total_line_check_pages}</b>页 | 不合格行：<b style="color: #dc2626;">{total_line_error}</b>行</p>
    <p style="font-size: 12px; color: #64748b;">
    检测规则：仅带图表/表格的页整页跳过，带标题的页仅跳过标题行，正文行正常检测<br>
    标准要求：段落首行31字，正文中间行33字，段尾行不做强制要求
    </p>
    </div>
    """
    final_result.append({"type": "html_report", "html_content": line_report_html})
    final_result.extend(line_word_issues)

    # 2. 两个模块之间的专属隔断（视觉分割线+空白间隔）
    final_result.append({
        "type": "html_report",
        "html_content": "<div style='margin: 35px 0; border-top: 2px dashed #d1d5db;'></div>"
    })

    # 3. 第二模块：每页行数规范检测（独立报告+专属报错）
    total_page_error = len(page_line_issues)
    log_html = f"<p style='font-size: 12px; color: #64748b;'>页面过滤日志：{'; '.join(skip_log)}</p>" if skip_log else ""
    page_report_html = f"""
    <div style="padding: 12px; border-radius: 8px; background: #f0fdf4; margin-bottom: 15px; border-left: 4px solid #22c55e;">
    <h4>📄 每页行数规范检测</h4>
    <p>有效检测页：<b>{total_page_check_pages}</b>页 | 合格页：<b style="color: #059669;">{total_page_pass}</b>页 | 不合格页：<b style="color: #dc2626;">{total_page_error}</b>页</p>
    {log_html}
    <p style="font-size: 12px; color: #64748b;">
    检测规则：仅对「下一页是第2章」的第一章末尾页做特殊跳过，其他页面仅跳过带标题/本章小结/图表的页面<br>
    标准要求：纯正文页标准总行数33行
    </p>
    </div>
    """
    final_result.append({"type": "html_report", "html_content": page_report_html})
    final_result.extend(page_line_issues)

    return final_result