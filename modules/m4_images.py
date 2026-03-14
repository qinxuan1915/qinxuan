import re

def check(pdf_pages, detected_offset=0):
    """
    严格图表编号检测模块 - Markdown 罗列版
    """
    found_items = []
    # 匹配标签和编号 (图/表 n-n)
    strict_pattern = r'(图|表)\s*(\d+)\s*[\-\u2013\u2014\u2212]\s*(\d+)'
    # 用于记录每章图/表的当前最大序号
    chapter_counters = {"图": {}, "表": {}}

    for page in pdf_pages:
        try:
            p_num = page.page_num + detected_offset
            # 适配 PDFPageData 对象
            if hasattr(page, 'lines') and isinstance(page.lines, list):
                raw_text = " ".join([w.get('text', '') if isinstance(w, dict) else "" for w in page.lines])
            elif hasattr(page, 'text'):
                raw_text = page.text
            else:
                continue
            clean_text = raw_text.replace("\t", " ")
        except:
            continue

        matches = re.finditer(strict_pattern, clean_text)
        for m in matches:
            found_items.append({
                "page": p_num,
                "label": m.group(1),
                "chapter": int(m.group(2)),
                "num": int(m.group(3)),
                "full": f"{m.group(1)} {m.group(2)}-{m.group(3)}"
            })

    if not found_items:
        return []

    # 使用 Markdown 列表罗列所有结果，避免 HTML 渲染失败
    md_content = "### 📊 图表逻辑\n\n"
    
    for item in found_items:
        label, ch, num, p_num = item['label'], item['chapter'], item['num'], item['page']
        is_valid, reason = True, "符合规范"

        if ch not in chapter_counters[label]:
            if num != 1:
                is_valid, reason = False, f"起始错误：应为 {ch}-1"
            chapter_counters[label][ch] = num
        else:
            expected = chapter_counters[label][ch] + 1
            if num != expected:
                if num == chapter_counters[label][ch]: continue 
                is_valid, reason = False, f"顺序错误：预期 {ch}-{expected}"
            chapter_counters[label][ch] = num

        status_icon = "✅" if is_valid else "❌"
        # 罗列格式：状态 编号 (位置) - 备注
        md_content += f"* {status_icon} **{item['full']}** (第 {p_num} 页) — *{reason}*\n"

    # 返回 app.py 能够解析的格式
    # 注意：在 app.py 中，如果是 html_report 类型，它会执行 st.markdown
    return [{"type": "html_report", "html_content": md_content}]