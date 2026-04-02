import re

def check(pdf_pages, detected_offset=0):
    """
    目录一致性检测工具（增强版）：
    1. 优化正则匹配，强制要求引导符或明显间距。
    2. 增加非法数据过滤，防止误读正文表格/坐标。
    3. 强化校验逻辑：必须【序号 + 标题】完整匹配。
    """
    results = []
    toc_items = []
    is_in_toc_area = False
    total_pages = len(pdf_pages)
    
    # --- 第一步：解析目录区域 ---
    for i in range(min(20, total_pages)):
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
                if re.search(r'^(目\s*录|CONTENTS)$', line.replace(" ", "")):
                    is_in_toc_area = True
                continue
            
            # 核心改进：加强版正则表达式
            pattern = r'^((?:第\s*[0-9一二三四五六七八九十]+\s*[章节])|(?:[0-9\.]+))(.*?)(\S.*?)(?:\s*[\.·—…]{2,}\s*|\s{3,})(\d{1,4})$'
            match = re.match(pattern, line)
            
            if match:
                section, gap, title, p_str = match.groups()
                page_val = int(p_str)
                
                # 过滤逻辑
                if page_val == 0 or page_val > total_pages:
                    continue
                if re.match(r'^[0-9\.\s\-\,]+$', title): 
                    continue

                if toc_items and page_val < toc_items[-1]["page"]:
                    continue

                toc_items.append({
                    "section": section.replace(" ", ""), # 序号：如 1.1.1
                    "title": title.strip(". "),         # 标题：如 课题背景
                    "page": page_val,
                    "raw_line": line
                })

    if not toc_items:
        return [{"type": "error", "msg": "未在文档前部识别到有效的目录结构，无法进行比对。"}]

    # --- 第二步：检测目录与正文的对应关系 ---
    verification_details = []
    success_count = 0
    
    for item in toc_items:
        target_page_idx = item["page"] + detected_offset - 1
        
        if target_page_idx < 0 or target_page_idx >= total_pages:
            status = "❌"
            reason = f"页码 {item['page']} 超出文档范围"
        else:
            target_page = pdf_pages[target_page_idx]
            page_text = ""
            if isinstance(target_page, dict):
                page_text = target_page.get("raw", target_page.get("text", ""))
            elif hasattr(target_page, 'get_text'):
                page_text = target_page.get_text("text")
            else:
                page_text = getattr(target_page, 'text', "")
            
            # --- 修改核心：拼接 序号 + 标题 进行比对 ---
            full_search_text = (item["section"] + item["title"]).replace(" ", "")
            clean_page_text = page_text.replace(" ", "").replace("\n", "")
            
            if full_search_text in clean_page_text:
                status = "✅"
                reason = "匹配成功"
                success_count += 1
            else:
                status = "❌"
                reason = f"正文页未找到完整标题: {full_search_text}"

        verification_details.append(
            f"{status} **{item['section']} {item['title']}** (在目录中显示的页码: {item['page']})\n"
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
