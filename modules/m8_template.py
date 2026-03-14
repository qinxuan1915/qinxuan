import re
from utils.file_reader import build_chapter_map

def check(pdf_pages, detected_offset=0):  # 修正点：添加了 detected_offset 参数，默认值为 0
    """
    对应 JS 版 modules/template.js
    检测章节完整性：引言、小结、居中格式
    """
    if not pdf_pages:
        return []

    # 1. 重新构建章节映射 (获取每一章的页码范围)
    # 注意：如果 build_chapter_map 内部需要偏移量，可以在此处传入
    chapter_map = build_chapter_map(pdf_pages)
    
    issues = []
    if not chapter_map:
        return [{"type": "error", "msg": "❌ 未识别到任何章节，请检查目录格式或页码偏移量"}]

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

        # --- 情况 B: 其他章节 (需要检测引言和小结) ---
        
        # 1. 检测【本章小结】
        has_summary = False
        is_centered = False
        
        for p_idx in range(start_idx, end_idx + 1):
            page = pdf_pages[p_idx]
            
            # 遍历所有提取出的词块
            # 注意：pdfplumber 提取的 word 对象通常包含 'text' 和坐标 'x0'
            for word in page.lines:
                text = word.get('text', '').strip()
                if re.match(r'^本\s*章\s*小\s*结$', text):
                    has_summary = True
                    # 居中判断逻辑：左边界坐标大于 200 (根据具体排版调整)
                    if word.get('x0', 0) > 200: 
                        is_centered = True
                    break
            
            if has_summary:
                break

        # 2. 检测【章节引言】
        has_intro = False
        search_limit = min(start_idx + 1, end_idx) 
        
        for p_idx in range(start_idx, search_limit + 1):
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
                if section_line_idx != -1:
                    for k in range(title_line_idx + 1, section_line_idx):
                        content = lines[k].strip()
                        if len(content) > 5 and not re.match(r'^\d+$', content):
                            has_intro = True
                            break
                    break 
                else:
                    has_intro = True 
                    break

        # --- 3. 生成报告 ---
        status_msg = f"第 {ch_num} 章检测: "
        
        if has_intro:
            status_msg += "✅ 引言存在 | "
        else:
            status_msg += "❌ 缺失引言 | "
            
        if not has_summary:
            status_msg += "❌ 缺失本章小结"
            issue_type = "error"
        else:
            if is_centered:
                status_msg += "✅ 小结已居中"
                issue_type = "info" 
                if not has_intro: issue_type = "warning"
            else:
                status_msg += "⚠️ 小结未居中"
                issue_type = "warning"

        issues.append({
            "type": issue_type,
            "msg": status_msg,
            "preview": f"范围: P{start_idx + 1} - P{end_idx + 1}"
        })

    return issues