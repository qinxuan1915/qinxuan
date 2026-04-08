import re


def check(pdf_pages, detected_offset=0):
    """
    目录一致性检测工具（增强版+错误类型区分）：
    1. 优化正则匹配，强制要求引导符或明显间距。
    2. 增加非法数据过滤，防止误读正文表格/坐标。
    3. 强化校验逻辑：必须【序号 + 标题】完整匹配。
    4. 新增：匹配失败时，精准区分「标题完全缺失」和「标题内容不匹配」两种错误类型
    """
    results = []
    toc_items = []
    is_in_toc_area = False
    total_pages = len(pdf_pages)

    # --- 第一步：解析目录区域（完全保留你原有的逻辑，未做任何修改）---
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

            # 核心改进：加强版正则表达式（完全保留你原有的正则，未修改）
            pattern = r'^((?:第\s*[0-9一二三四五六七八九十]+\s*[章节])|(?:[0-9\.]+))(.*?)(\S.*?)(?:\s*[\.·—…]{2,}\s*|\s{3,})(\d{1,4})$'
            match = re.match(pattern, line)

            if match:
                section, gap, title, p_str = match.groups()
                page_val = int(p_str)

                # 过滤逻辑（完全保留你原有的过滤规则）
                if page_val == 0 or page_val > total_pages:
                    continue
                if re.match(r'^[0-9\.\s\-\,]+$', title):
                    continue

                if toc_items and page_val < toc_items[-1]["page"]:
                    continue

                toc_items.append({
                    "section": section.replace(" ", ""),  # 序号：如 1.1.1（已去空格）
                    "title": title.strip(". "),  # 标题：如 课题背景
                    "page": page_val,
                    "raw_line": line
                })

    if not toc_items:
        return [{"type": "error", "msg": "未在文档前部识别到有效的目录结构，无法进行比对。"}]

    # --- 第二步：检测目录与正文的对应关系（核心修改：拆分2种错误类型）---
    verification_details = []
    success_count = 0

    for item in toc_items:
        target_page_idx = item["page"] + detected_offset - 1
        target_section = item["section"]  # 目录序号（已去空格）
        target_full = (target_section + item["title"]).replace(" ", "")  # 完整匹配文本（序号+标题）
        toc_full_title = f"{item['section']} {item['title']}"  # 目录完整标题

        # 页码越界处理
        if target_page_idx < 0 or target_page_idx >= total_pages:
            status = "❌"
            verification_details.append(
                f"{status} **{toc_full_title}** (在目录中显示的页码: {item['page']})\n"
                f"   - 结果: 正文页未找到完整标题: {target_full}\n"
                f"   - 错误类型: 未在该页找到此标题，页码超出文档范围"
            )
            continue

        # 提取目标页文本（完全保留你原有的兼容逻辑）
        target_page = pdf_pages[target_page_idx]
        page_text = ""
        if isinstance(target_page, dict):
            page_text = target_page.get("raw", target_page.get("text", ""))
        elif hasattr(target_page, 'get_text'):
            page_text = target_page.get_text("text")
        else:
            page_text = getattr(target_page, 'text', "")

        # 文本预处理（和你原有逻辑完全一致：去空格、去换行）
        clean_page_text = page_text.replace(" ", "").replace("\n", "")
        page_lines = [line.strip() for line in page_text.split('\n') if line.strip()]

        # --- 核心修改：拆分2种错误类型 ---
        if target_full in clean_page_text:
            # 1. 完全匹配成功
            status = "✅"
            success_count += 1
            verification_details.append(
                f"{status} **{toc_full_title}** (在目录中显示的页码: {item['page']})\n"
                f"   - 结果: 匹配成功"
            )
        else:
            # 2. 匹配失败，拆分错误类型
            status = "❌"
            # 先判断：正文里有没有这个序号？
            if target_section not in clean_page_text:
                # 类型1：连序号都没有 → 标题完全缺失
                verification_details.append(
                    f"{status} **{toc_full_title}** (在目录中显示的页码: {item['page']})\n"
                    f"   - 结果: 正文页未找到完整标题: {target_full}\n"
                    f"   - 错误类型: 未在该页找到此标题，正文无对应序号的标题内容"
                )
            else:
                # 类型2：有这个序号，但标题内容不对 → 内容不匹配
                # 提取正文里带这个序号的实际标题，给用户看
                real_title = "未提取到完整行"
                for line in page_lines:
                    if target_section in line.replace(" ", ""):
                        real_title = line.strip()
                        break
                verification_details.append(
                    f"{status} **{toc_full_title}** (在目录中显示的页码: {item['page']})\n"
                    f"   - 结果: 匹配失败\n"
                    f"   - 错误类型: 此标题【{real_title}】与目录锁定标题【{toc_full_title}】不匹配"
                )

    # --- 第三步：生成报告（完全保留你原有的返回格式，未做任何修改）---
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
