import re

def check(pdf_pages, detected_offset=0):
    """
    图表编号检测模块（最终稳定版：只识别图表标题）
    """

    found_items = []
    strict_pattern = r'(图|表)\s*(\d+)\s*[-–—]\s*(\d+)'
    chapter_counters = {"图": {}, "表": {}}

    for page in pdf_pages:
        try:
            p_num = getattr(page, 'page_num', None)
            if not p_num:
                continue

            if hasattr(page, 'text'):
                lines = page.text.split("\n")
            else:
                continue

        except:
            continue

        # ✅ 逐行处理（关键）
        for line in lines:
            clean_line = line.strip()

            if not clean_line:
                continue

            # ❌ 强过滤：正文句子（关键！）
            if any(x in clean_line for x in [
                "如图", "见图", "如下图", "参见图",
                "可以看出", "所示", "展示了", "说明了"
            ]):
                continue

            # ✅ 必须“接近标题结构”
            # 特征：以图/表开头 或 前面只有少量空格
            if not re.match(r'^\s*(图|表)\s*\d+\s*[-–—]\s*\d+', clean_line):
                continue

            matches = re.finditer(strict_pattern, clean_line)
            for m in matches:
                found_items.append({
                    "page": p_num,
                    "label": m.group(1),
                    "chapter": int(m.group(2)),
                    "num": int(m.group(3)),
                    "full": f"{m.group(1)} {m.group(2)}-{m.group(3)}"
                })

    # ========================
    # 输出（不变）
    # ========================
    md_content = "### 📊 图表逻辑\n\n"

    if not found_items:
        md_content += "* ⚠️ 未检测到图表\n"
        return [{"type": "html_report", "html_content": md_content}]

    for item in found_items:
        label = item['label']
        ch = item['chapter']
        num = item['num']
        p_num = item['page']

        is_valid = True
        reason = "符合规范"

        if ch not in chapter_counters[label]:
            if num != 1:
                is_valid = False
                reason = f"起始错误：应为 {ch}-1"
            chapter_counters[label][ch] = num
        else:
            expected = chapter_counters[label][ch] + 1
            if num != expected:
                if num == chapter_counters[label][ch]:
                    continue
                is_valid = False
                reason = f"顺序错误：预期 {ch}-{expected}"
            chapter_counters[label][ch] = num

        status_icon = "✅" if is_valid else "❌"

        md_content += (
            f"* {status_icon} **{item['full']}** — *{reason}* （PDF页码：{p_num}）\n"
        )

    return [{"type": "html_report", "html_content": md_content}]