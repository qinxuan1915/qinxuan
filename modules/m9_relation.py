import re
from collections import defaultdict

# 匹配中文汉字的正则
chinese_pattern = re.compile(r'[\u4e00-\u9fa5]+')
# ===================== 内置黑名单（可自定义） =====================
INTERNAL_BLACKLIST = {
    "测试", "临时", "草稿", "作废", "示例", "模板", "占位", "删除",
    "无效", "空值", "默认", "演示", "样例", "草稿箱"
}
# ===================== 标题修饰词列表（已加入你论文的特定后缀修饰词） =====================
MODIFIER_WORDS = {
    "基于", "针对", "面向", "对于", "关于", "以", "从",
    "的", "之",
    "研究", "分析", "探讨", "初探", "探析", "述评", "综述",
    "方法", "设计", "实现", "应用", "开发", "构建",
    "现状", "进展", "趋势", "调查", "考察",
    "及其", "以及", "与", "和",
    "下", "中", "上",
    "浅谈", "浅析", "简论", "试论",
    "的研究", "的分析", "的探讨", "的设计", "的实现",
    "业务活动分析", "模块实现", "用例", "UI构件设计", "构件设计"
}


# ==================================================================================
def extract_core_keywords(text):
    sorted_modifiers = sorted(MODIFIER_WORDS, key=len, reverse=True)
    core_text = text
    for modifier in sorted_modifiers:
        core_text = core_text.replace(modifier, "")
    return core_text


def parse_title_level(section_str):
    match_chapter = re.match(r'第\s*(\d+)\s*章', section_str)
    if match_chapter:
        return [int(match_chapter.group(1))]
    match_num = re.match(r'^([\d.]+)$', section_str)
    if match_num:
        num_str = match_num.group(1)
        parts = [int(p) for p in num_str.split('.') if p]
        return parts if parts else None
    return None


def is_parent_child(level_a, level_b):
    if not level_a or not level_b:
        return False
    if len(level_a) > len(level_b):
        level_a, level_b = level_b, level_a
    if len(level_b) - len(level_a) != 1:
        return False
    return level_a == level_b[:len(level_a)]


def extract_clean_toc_items(pdf_pages):
    toc_items = []
    is_in_toc_area = False
    total_pages = len(pdf_pages)
    valid_title_start = re.compile(r'^(第\s*[0-9一二三四五六七八九十]+\s*[章节]|\d+(\.\d+)*)')
    garbage_chars = re.compile(r'[%℃$&*@#]')
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
            pattern = r'^((?:第\s*[0-9一二三四五六七八九十]+\s*[章节])|(?:[0-9\.]+))(.*?)(?:\s*[\.·—…]{2,}\s*|\s{3,})(\d{1,4})$'
            match = re.match(pattern, line)
            if match:
                section_raw, title_raw, p_str = match.groups()
                page_val = int(p_str)
                if page_val == 0 or page_val > total_pages: continue
                section_clean = section_raw.replace(" ", "")
                title_clean = title_raw.strip(". ")
                full_title = f"{section_clean}{title_clean}"
                chinese_text_list = chinese_pattern.findall(title_clean)
                pure_chinese_text = "".join(chinese_text_list)
                core_text = extract_core_keywords(pure_chinese_text)
                if not core_text: continue
                if len(full_title) < 3: continue
                if not valid_title_start.match(full_title): continue
                if garbage_chars.search(full_title) or "。" in full_title: continue
                if re.match(r'^[0-9\.\s\-\,]+$', title_clean): continue
                level = parse_title_level(section_clean)
                if level:
                    toc_items.append({
                        "full": full_title,
                        "section": section_clean,
                        "level": level,
                        "pure_text": pure_chinese_text,
                        "core_text": core_text
                    })
    seen = set()
    unique_items = []
    for item in toc_items:
        if item["full"] not in seen:
            seen.add(item["full"])
            unique_items.append(item)
    return unique_items


def custom_offset_match(core_a, core_b):
    if len(core_a) > len(core_b):
        core_a, core_b = core_b, core_a
    return core_b.startswith(core_a)


# 【关键修复】增加 detected_offset 参数及 **kwargs 以适配 app.py 的调用逻辑
def check(pdf_pages, detected_offset=None, **kwargs):
    toc_data = extract_clean_toc_items(pdf_pages)
    if not toc_data:
        return [{"type": "info", "msg": "未在目录中识别到有效的标题列表。"}]

    # 1. 第一组：3.2业务活动分析 <-> 6系统实现
    list_32 = [item for item in toc_data if item["section"].startswith("3.2.")]
    list_32.sort(key=lambda x: x["level"])
    count_32 = len(list_32)
    list_6 = [item for item in toc_data if len(item["level"]) == 2 and item["level"][0] == 6]
    list_6.sort(key=lambda x: x["level"])
    list_6 = list_6[:count_32]

    # 2. 第二组：3.3需求用例 <-> 5.1构件结构
    list_33 = [item for item in toc_data if item["section"].startswith("3.3.")]
    list_33.sort(key=lambda x: x["level"])
    count_33 = len(list_33)
    list_51 = [item for item in toc_data if item["section"].startswith("5.1.")]
    list_51.sort(key=lambda x: x["level"])
    list_51 = list_51[:count_33]

    issues = []
    # 第一组分隔标题
    issues.append({
        "type": "info",
        "msg": "### 1-一致性校验.3.2业务活动分析<->6系统实现"
    })
    # 第一组对比
    if count_32 == 0:
        issues.append({"type": "info", "msg": "未找到3.2章节下的三级小节标题，无法完成第一组对比。"})
    else:
        if len(list_6) < count_32:
            issues.append(
                {"type": "error", "msg": f"6章节下的二级小节数量不足，仅找到{len(list_6)}个，需要{count_32}个。"})
        else:
            for i in range(count_32):
                item_32 = list_32[i]
                item_6 = list_6[i]
                is_match = custom_offset_match(item_32["core_text"], item_6["core_text"])
                sec_32 = f"3.2.{i + 1}"
                sec_6 = f"6.{i + 1}"
                if is_match:
                    issues.append({
                        "type": "info",
                        "msg": f"""✅ {sec_32} 与 {sec_6} 匹配成功
**{sec_32}:** {item_32['pure_text']}
**{sec_6}:** {item_6['pure_text']}"""
                    })
                else:
                    issues.append({
                        "type": "error",
                        "msg": f"❌ {sec_32} 与 {sec_6} 匹配失败，可能存在错别字、缺字或顺序错误。\n**{sec_32}:** {item_32['pure_text']}\n**{sec_6}:** {item_6['pure_text']}"
                    })

    # 第二组分隔标题
    issues.append({
        "type": "info",
        "msg": "### 2-一致性校验.3.3需求用例<->5.1构件结构"
    })
    # 第二组对比
    if count_33 == 0:
        issues.append({"type": "info", "msg": "未找到3.3章节下的三级小节标题，无法完成第二组对比。"})
    else:
        if len(list_51) < count_33:
            issues.append(
                {"type": "error", "msg": f"5.1章节下的三级小节数量不足，仅找到{len(list_51)}个，需要{count_33}个。"})
        else:
            for i in range(count_33):
                item_33 = list_33[i]
                item_51 = list_51[i]
                is_match = custom_offset_match(item_33["core_text"], item_51["core_text"])
                sec_33 = f"3.3.{i + 1}"
                sec_51 = f"5.1.{i + 1}"
                if is_match:
                    issues.append({
                        "type": "info",
                        "msg": f"""✅ {sec_33} 与 {sec_51} 匹配成功
**{sec_33}:** {item_33['pure_text']}
**{sec_51}:** {item_51['pure_text']}"""
                    })
                else:
                    issues.append({
                        "type": "error",
                        "msg": f"❌ {sec_33} 与 {sec_51} 匹配失败，可能存在错别字、缺字或顺序错误。\n**{sec_33}:** {item_33['pure_text']}\n**{sec_51}:** {item_51['pure_text']}"
                    })
    return issues