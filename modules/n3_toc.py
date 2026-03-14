import re

def check(pdf_pages, detected_offset=0):
    """
    目录一致性检测工具：
    1. 识别目录中的章节号、标题和页码。
    2. 跳转至正文对应页码，核实标题是否存在。
    """
    results = []
    toc_items = []
    is_in_toc_area = False
    
    # --- 第一步：解析目录区域 ---
    for i in range(min(20, len(pdf_pages))):
        page = pdf_pages[i]
        text = ""
        if isinstance(page, dict):
            text = page.get("raw", page.get("text", ""))
        elif hasattr(page, 'get_text'):
            text = page.get_text("text")
        else:
            text = getattr(page, 'text', "")

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        for line in lines:
            if not is_in_toc_area:
                # 识别目录入口
                if re.search(r'^(目\s*录|CONTENTS)$', line.replace(" ", "")):
                    is_in_toc_area = True
                continue
            
            # 正则捕获：Section(章节号), Gap(间距), Title(标题), Page(页码)
            # 兼容：1.1 标题...1 或 第一章 标题...1
            pattern = r'^((?:第\s*[0-9一二三四五六七八九十]+\s*[章节])|(?:[0-9\.]+))(.*?)(\S.*?)(?:\s*[\.·—… \s]+\s*|\s+)(\d+)$'
            match = re.match(pattern, line)
            
            if match:
                section, gap, title, p_str = match.groups()
                page_val = int(p_str)
                
                # 简单的过滤逻辑：防止重复抓取
                if toc_items and page_val < toc_items[-1]["page"]:
                    continue

                toc_items.append({
                    "section": section.replace(" ", ""),
                    "title": title.strip(". "),
                    "page": page_val,
                    "raw_line": line
                })

    if not toc_items:
        return [{"type": "error", "msg": "未在文档前部识别到有效的目录结构，无法进行比对。"}]

    # --- 第二步：检测目录与正文的对应关系 ---
    verification_details = []
    # 尝试自动计算偏移量（假设目录中第一项的页码对应 PDF 实际的物理页码）
    # 通常物理页码 = 目录页码 + offset
    # 这里的逻辑可以根据实际 PDF 情况调整，默认先按 1:1 比对
    
    success_count = 0
    for item in toc_items:
        target_page_idx = item["page"] + detected_offset - 1 # 转为从0开始的索引
        
        if target_page_idx >= len(pdf_pages):
            status = "❌"
            reason = "页码超出文档范围"
        else:
            # 获取目标页内容
            target_page = pdf_pages[target_page_idx]
            page_text = ""
            if isinstance(target_page, dict):
                page_text = target_page.get("raw", target_page.get("text", ""))
            elif hasattr(target_page, 'get_text'):
                page_text = target_page.get_text("text")
            else:
                page_text = getattr(target_page, 'text', "")
            
            # 清理字符串进行模糊比对
            clean_title = item["title"].replace(" ", "")
            clean_page_text = page_text.replace(" ", "").replace("\n", "")
            
            # 检查标题是否出现在该页的前 500 个字符内（通常标题在页首）
            if clean_title in clean_page_text:
                status = "✅"
                reason = "匹配成功"
                success_count += 1
            else:
                status = "❌"
                reason = "正文页未找到匹配标题"

        verification_details.append(
            f"{status} **{item['section']} {item['title']}** (目录页码: {item['page']})\n"
            f"   - 结果: {reason}"
        )

    # --- 第三步：生成报告 ---
    summary_status = "info" if success_count == len(toc_items) else "warning"
    results.append({
        "type": summary_status,
        "msg": f"📊 **目录与正文一致性检测报告**\n\n"
               f"检测到目录项: {len(toc_items)} 个\n"
               f"匹配成功: {success_count} 个\n"
               f"匹配失败: {len(toc_items) - success_count} 个\n\n"
               + "\n\n".join(verification_details)
    })

    return results