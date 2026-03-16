import re
from utils.file_reader import build_chapter_map

def check(pdf_pages, detected_offset=0):
    """
    对应 JS 版 modules/template.js
    检测章节完整性：引言、小结、居中格式
    """
    if not pdf_pages:
        return []

    # 1. 构建章节映射
    raw_chapter_map = build_chapter_map(pdf_pages)
    if not raw_chapter_map:
        return [{"type": "error", "msg": "❌ 未识别到任何章节，请检查目录格式或页码偏移量"}]

    # --- 修复：按章节号去重，只保留每章最后一次出现的范围 (解决截图中的重复显示问题) ---
    chapter_dict = {}
    for ch in raw_chapter_map:
        chapter_dict[ch['num']] = ch
    chapter_map = sorted(chapter_dict.values(), key=lambda x: x['num'])

    issues = []

    # 2. 遍历每一章进行检查
    for ch in chapter_map:
        ch_num = ch['num']
        start_idx = ch['start_page']
        end_idx = ch['end_page']
        
        # --- 情况 A: 第一章 (通常是绪论) ---
        if ch_num == 1:
            issues.append({
                "type": "info",
                "msg": f"第 {ch_num} 章 (绪论)",
                "preview": f"页码范围: P{start_idx + 1} - P{end_idx + 1}"
            })
            continue

        # --- 情况 B: 其他章节 ---
        
        # 1. 检测【本章小结】
        has_summary = False
        is_centered = False
        
        # 扩大检索范围，确保不遗漏边界页
        for p_idx in range(start_idx, end_idx + 1):
            if p_idx >= len(pdf_pages): break
            page = pdf_pages[p_idx]
            
            # 兼容处理：有些版本的 pdfplumber 使用 lines，有些使用 words
            elements = getattr(page, 'lines', []) if hasattr(page, 'lines') else []
            if not elements and hasattr(page, 'extract_words'):
                elements = page.extract_words()

            for word in elements:
                text = word.get('text', '').replace(" ", "").strip()
                if text == "本章小结":
                    has_summary = True
                    # 居中判断：根据常见 A4 页面宽度，左边距在 200-280 之间通常为居中
                    x_pos = word.get('x0', 0)
                    if 180 < x_pos < 300: 
                        is_centered = True
                    break
            if has_summary: break

        # 2. 检测【章节引言】
        has_intro = False
        # 引言通常在章节标题后、第一个小节 (X.1) 之前
        search_limit = min(start_idx + 1, end_idx) 
        
        for p_idx in range(start_idx, search_limit + 1):
            if p_idx >= len(pdf_pages): break
            page_text = pdf_pages[p_idx].text
            if not page_text: continue
            
            lines = page_text.split('\n')
            title_line_idx = -1
            section_line_idx = -1
            
            chapter_pattern = re.compile(rf"第\s*{ch_num}\s*章")
            section_pattern = re.compile(rf"^{ch_num}\.1")

            for i, line in enumerate(lines):
                line = line.strip()
                if chapter_pattern.search(line):
                    title_line_idx = i
                elif section_pattern.search(line):
                    section_line_idx = i
                    break 
            
            if title_line_idx != -1:
                # 检查标题行和第一个小节行之间是否有实质性文字
                if section_line_idx != -1:
                    for k in range(title_line_idx + 1, section_line_idx):
                        content = lines[k].strip()
                        # 过滤掉纯数字（页码）和过短的噪点
                        if len(content) > 5 and not content.isdigit():
                            has_intro = True
                            break
                    break 
                else:
                    # 如果找到了标题但还没到下一页也没找到 X.1，暂定为有引言或引言过长
                    has_intro = True 
                    break

        # --- 3. 生成报告 ---
        status_parts = []
        status_parts.append("✅ 引言存在" if has_intro else "❌ 缺失引言")
        
        if not has_summary:
            status_parts.append("❌ 缺失本章小结")
            issue_type = "error"
        else:
            status_parts.append("✅ 小结已居中" if is_centered else "⚠️ 小结未居中")
            issue_type = "info" if (is_centered and has_intro) else "warning"

        issues.append({
            "type": issue_type,
            "msg": f"第 {ch_num} 章检测: " + " | ".join(status_parts),
            "preview": f"范围: P{start_idx + 1} - P{end_idx + 1}"
        })

    return issues
