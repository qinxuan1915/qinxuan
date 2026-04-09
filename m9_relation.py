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
# 仅关注关键词的错误，忽略这些修饰词的差异
MODIFIER_WORDS = {
    # 通用修饰词
    "基于", "针对", "面向", "对于", "关于", "以", "从",
    "的", "之",
    "研究", "分析", "探讨", "初探", "探析", "述评", "综述",
    "方法", "设计", "实现", "应用", "开发", "构建",
    "现状", "进展", "趋势", "调查", "考察",
    "及其", "以及", "与", "和",
    "下", "中", "上",
    "浅谈", "浅析", "简论", "试论",
    "的研究", "的分析", "的探讨", "的设计", "的实现",
    # 你这组论文的特定后缀修饰词（自动去掉这些固定后缀，只对比前面的关键词）
    "业务活动分析", "模块实现", "用例", "UI构件设计", "构件设计"
}


# ==================================================================================
def extract_core_keywords(text):
    """
    从标题文本中提取核心关键词，移除修饰词
    先移除长修饰词，避免短修饰词干扰
    """
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
                # 提取核心关键词，移除修饰词
                core_text = extract_core_keywords(pure_chinese_text)
                # 只过滤空的核心关键词，不再过滤短的！避免把正常的短标题过滤掉
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
    """
    完全按照你的逻辑：
    短的字符串必须是长的字符串的前缀，也就是开头必须完全一模一样
    允许长的字符串后面多几个字符（因为修饰词可能没去干净）
    绝对不允许开头缺字/错字，完全严格匹配
    """
    if len(core_a) > len(core_b):
        core_a, core_b = core_b, core_a
    # 现在a是短的，b是长的，检查b的开头是不是和a完全一样
    return core_b.startswith(core_a)


def check(pdf_pages, detected_offset=None):
    """
    补上了detected_offset参数，兼容原来的系统调用，不会再报错了
    """
    toc_data = extract_clean_toc_items(pdf_pages)
    if not toc_data:
        return [{"type": "info", "msg": "未在目录中识别到有效的标题列表。"}]

    # 1. 第一组：3.2业务活动分析 <-> 6系统实现
    # 提取所有的3.2的项，不再截断
    list_32 = [item for item in toc_data if item["section"].startswith("3.2.")]
    list_32.sort(key=lambda x: x["level"])
    # 提取所有的6的项，不再只取前N个，所有的都要用来匹配
    list_6 = [item for item in toc_data if len(item["level"]) == 2 and item["level"][0] == 6]
    list_6.sort(key=lambda x: x["level"])

    # 2. 第二组：3.3需求用例 <-> 5.1构件结构
    # 提取所有的3.3的项，不再截断
    list_33 = [item for item in toc_data if item["section"].startswith("3.3.")]
    list_33.sort(key=lambda x: x["level"])
    # 提取所有的5.1的项，不再只取前N个，所有的都要用来匹配
    list_51 = [item for item in toc_data if item["section"].startswith("5.1.")]
    list_51.sort(key=lambda x: x["level"])

    issues = []

    # 第一组的分组标题，保留你要的1-RCC的显示格式
    issues.append({
        "type": "info",
        "msg": "### 第一组关联对比：1-RCC-一致性校验.3.2业务活动分析<->6系统实现"
    })

    # 处理第一组：每个3.2的项，去6的所有项里找，用过的6的项不能再用
    if len(list_32) == 0:
        issues.append({"type": "info", "msg": "未找到3.2章节下的三级小节标题，无法完成第一组对比。"})
    else:
        if len(list_6) == 0:
            issues.append({"type": "error", "msg": "6章节下没有找到二级小节，无法完成第一组对比。"})
        else:
            # 标记6的项有没有被用过
            used_6 = [False] * len(list_6)
            for item_32 in list_32:
                matched = False
                match_idx = -1
                # 挨个遍历所有的6的项，找没被用过的、内容匹配的
                for idx, item_6 in enumerate(list_6):
                    if not used_6[idx] and custom_offset_match(item_32["core_text"], item_6["core_text"]):
                        # 找到匹配的了
                        used_6[idx] = True
                        matched = True
                        match_idx = idx
                        break
                if matched:
                    # 匹配成功
                    sec_32 = item_32["section"]
                    sec_6 = list_6[match_idx]["section"]
                    issues.append({
                        "type": "info",
                        "msg": f"""✅ {sec_32} 与 {sec_6} 匹配成功

**{sec_32}:** {item_32['pure_text']}
**{sec_6}:** {list_6[match_idx]['pure_text']}"""
                    })
                else:
                    # 所有的6的项都找遍了，一个都没匹配上
                    sec_32 = item_32["section"]
                    issues.append({
                        "type": "error",
                        "msg": f"""❌ {sec_32} 未找到对应的6章节小节

**{sec_32}:** {item_32['pure_text']}

遍历了6章节的所有二级小节，都没有找到匹配的内容，且没有可用的未匹配项。"""
                    })

    # 第二组的分组标题，保留你要的2-RCC的显示格式
    issues.append({
        "type": "info",
        "msg": "### 第二组关联对比：2-RCC-一致性校验.3.3需求用例<->5.1构件结构"
    })

    # 处理第二组：每个3.3的项，去5.1的所有项里找，用过的5.1的项不能再用
    if len(list_33) == 0:
        issues.append({"type": "info", "msg": "未找到3.3章节下的三级小节标题，无法完成第二组对比。"})
    else:
        if len(list_51) == 0:
            issues.append({"type": "error", "msg": "5.1章节下没有找到三级小节，无法完成第二组对比。"})
        else:
            # 标记5.1的项有没有被用过
            used_51 = [False] * len(list_51)
            for item_33 in list_33:
                matched = False
                match_idx = -1
                # 挨个遍历所有的5.1的项，找没被用过的、内容匹配的
                for idx, item_51 in enumerate(list_51):
                    if not used_51[idx] and custom_offset_match(item_33["core_text"], item_51["core_text"]):
                        # 找到匹配的了
                        used_51[idx] = True
                        matched = True
                        match_idx = idx
                        break
                if matched:
                    # 匹配成功
                    sec_33 = item_33["section"]
                    sec_51 = list_51[match_idx]["section"]
                    issues.append({
                        "type": "info",
                        "msg": f"""✅ {sec_33} 与 {sec_51} 匹配成功

**{sec_33}:** {item_33['pure_text']}
**{sec_51}:** {list_51[match_idx]['pure_text']}"""
                    })
                else:
                    # 所有的5.1的项都找遍了，一个都没匹配上
                    sec_33 = item_33["section"]
                    issues.append({
                        "type": "error",
                        "msg": f"""❌ {sec_33} 未找到对应的5.1章节小节

**{sec_33}:** {item_33['pure_text']}

遍历了5.1章节的所有三级小节，都没有找到匹配的内容，且没有可用的未匹配项。"""
                    })

    return issues