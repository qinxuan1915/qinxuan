import re

def check(pdf_pages, detected_offset=0):
    found_items = []
    strict_pattern = r'(图|表)\s*(\d+)\s*[-–—]\s*(\d+)'
    chapter_counters = {"图": {}, "表": {}}

    last_table = None

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

        for line in lines:
            clean_line = line.strip()

            if not clean_line:
                continue

            if any(x in clean_line for x in [
                "如图", "见图", "如下图", "参见图",
                "可以看出", "所示", "展示了", "说明了"
            ]):
                continue

            if not re.match(r'^\s*(图|表)\s*\d+\s*[-–—]\s*\d+', clean_line):
                continue

            matches = re.finditer(strict_pattern, clean_line)
            for m in matches:
                label = m.group(1)
                ch = int(m.group(2))
                num = int(m.group(3))

                is_continued = ("续表" in clean_line)

                item = {
                    "page": p_num,
                    "label": label,
                    "chapter": ch,
                    "num": num,
                    "full": f"{label} {ch}-{num}",
                    "is_continued": is_continued
                }

                found_items.append(item)

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

        # 🔥 续表逻辑（现在位置是正确的）
        if label == "表" and item.get("is_continued") and last_table is not None:
            prev_ch = last_table["ch"]
            prev_num = last_table["num"]
            prev_valid = last_table["is_valid"]
            prev_reason = last_table["reason"]

            # ❌ 编号不匹配
            if (ch, num) != (prev_ch, prev_num):
                is_valid = False
                reason = f"该续表与前一张表 {prev_ch}-{prev_num} 不匹配"

            else:
                # ✅ 前一张表正确
                if prev_valid:
                    is_valid = True
                    reason = f"与前面的 {prev_ch}-{prev_num} 匹配成功"

                # ❌ 前一张表错误 → 继承错误
                else:
                    is_valid = False
                    reason = f"与前面的 {prev_ch}-{prev_num} 匹配成功；继承错误：{prev_reason}"

        else:
            # 🔵 正常表逻辑
            if ch not in chapter_counters[label]:
                if num != 1:
                    is_valid = False
                    reason = f"起始错误：应为 {ch}-1"
                chapter_counters[label][ch] = num
            else:
                expected = chapter_counters[label][ch] + 1
                if num != expected:
                    if num == chapter_counters[label][ch]:
                        pass
                    else:
                        is_valid = False
                        reason = f"顺序错误：预期 {ch}-{expected}"
                chapter_counters[label][ch] = num

        # ✅ 现在才更新 last_table（关键！！）
        if label == "表" and not item.get("is_continued"):
            last_table = {
                "ch": ch,
                "num": num,
                "is_valid": is_valid,
                "reason": reason
            }

        status_icon = "✅" if is_valid else "❌"
        prefix = "续表 " if item.get("is_continued") else ""

        md_content += (
            f"* {status_icon} **{prefix}{item['full']}** — *{reason}* （PDF页码：{p_num}）\n"
        )

    return [{"type": "html_report", "html_content": md_content}]
