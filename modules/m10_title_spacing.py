import re
from typing import List, Dict, Any, Optional

# ---------- 目录解析（完全恢复原版 n3_toc 的逻辑，确保能识别） ----------
def extract_toc_items(pdf_pages, max_pages=20):
    toc_items = []
    is_in_toc_area = False
    total_pages = len(pdf_pages)

    for i in range(min(max_pages, total_pages)):
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

            # 原版正则：支持点线或至少3个空格分隔符
            pattern = r'^((?:第\s*[0-9一二三四五六七八九十]+\s*[章节])|(?:[0-9\.]+))(.*?)(\S.*?)(?:\s*[\.·—…]{2,}\s*|\s{3,})(\d{1,4})$'
            match = re.match(pattern, line)
            if match:
                section, gap, title, p_str = match.groups()
                page_val = int(p_str)
                if page_val == 0 or page_val > total_pages:
                    continue
                if re.match(r'^[0-9\.\s\-\,]+$', title):
                    continue
                if toc_items and page_val < toc_items[-1]["page"]:
                    continue
                toc_items.append({
                    "section": section.replace(" ", ""),
                    "title": title.strip(". "),
                    "page": page_val,
                })
    return toc_items


def get_title_level(section: str) -> int:
    if re.match(r'^第\s*[0-9一二三四五六七八九十]+\s*章$', section):
        return 1
    if re.match(r'^\d+$', section):
        return 1
    if re.match(r'^\d+\.\d+$', section):
        return 2
    if re.match(r'^\d+\.\d+\.\d+$', section):
        return 3
    return 0


# ---------- 从页面提取文本行（保持原版不变） ----------
def extract_lines_from_page(page) -> List[Dict[str, Any]]:
    """
    从页面对象中提取所有文本行，返回每行的 text, y_min, y_max, avg_font_size。
    支持三种数据来源：
    1. page.lines（来自 file_reader.py 的 word 列表）
    2. page.words（pdfplumber 原生）
    3. page.text（回退方案）
    """
    lines = []

    # ----- 优先处理 page.lines (PDFPageData 对象) -----
    if hasattr(page, 'lines') and isinstance(page.lines, list) and page.lines:
        words = page.lines
        normalized = []
        for w in words:
            if not isinstance(w, dict):
                continue
            text = w.get('text', '')
            if not text:
                continue
            y0 = w.get('y0', w.get('top', 0))
            y1 = w.get('y1', w.get('bottom', 0))
            size = w.get('size', w.get('fontsize', 12))
            normalized.append({
                'text': text,
                'y0': y0,
                'y1': y1,
                'size': size,
                'x0': w.get('x0', w.get('x0', 0))
            })
        if normalized:
            normalized.sort(key=lambda w: (w['y0'], w['x0']))
            y_tolerance = 5
            cur_line_words = []
            last_y0 = None
            for w in normalized:
                if last_y0 is None or abs(w['y0'] - last_y0) <= y_tolerance:
                    cur_line_words.append(w)
                else:
                    if cur_line_words:
                        line_text = ''.join([w['text'] for w in cur_line_words])
                        y_min = min(w['y0'] for w in cur_line_words)
                        y_max = max(w['y1'] for w in cur_line_words)
                        avg_size = sum(w['size'] for w in cur_line_words) / len(cur_line_words)
                        lines.append({
                            'text': line_text,
                            'y0': y_min,
                            'y1': y_max,
                            'font_size': avg_size
                        })
                    cur_line_words = [w]
                last_y0 = w['y0']
            if cur_line_words:
                line_text = ''.join([w['text'] for w in cur_line_words])
                y_min = min(w['y0'] for w in cur_line_words)
                y_max = max(w['y1'] for w in cur_line_words)
                avg_size = sum(w['size'] for w in cur_line_words) / len(cur_line_words)
                lines.append({
                    'text': line_text,
                    'y0': y_min,
                    'y1': y_max,
                    'font_size': avg_size
                })
            return lines

    # ----- 使用 page.words (pdfplumber) -----
    if hasattr(page, 'words') and page.words:
        words = page.words
        words.sort(key=lambda w: (w['y0'], w['x0']))
        y_tolerance = 5
        cur_line = []
        last_y0 = None
        for w in words:
            y0 = w['y0']
            if last_y0 is None or abs(y0 - last_y0) <= y_tolerance:
                cur_line.append(w)
            else:
                if cur_line:
                    line_text = ''.join([w['text'] for w in cur_line])
                    y_min = min(w['y0'] for w in cur_line)
                    y_max = max(w['y1'] for w in cur_line)
                    avg_size = sum(w.get('size', 12) for w in cur_line) / len(cur_line)
                    lines.append({
                        'text': line_text,
                        'y0': y_min,
                        'y1': y_max,
                        'font_size': avg_size
                    })
                cur_line = [w]
            last_y0 = y0
        if cur_line:
            line_text = ''.join([w['text'] for w in cur_line])
            y_min = min(w['y0'] for w in cur_line)
            y_max = max(w['y1'] for w in cur_line)
            avg_size = sum(w.get('size', 12) for w in cur_line) / len(cur_line)
            lines.append({
                'text': line_text,
                'y0': y_min,
                'y1': y_max,
                'font_size': avg_size
            })
        return lines

    # ----- 回退：使用 page.text 按行分割（仅用于扫描版）-----
    text = ""
    if hasattr(page, 'get_text'):
        text = page.get_text("text")
    else:
        text = getattr(page, 'text', "")
    raw_lines = [line.rstrip() for line in text.split('\n') if line.strip()]
    base_y = 800
    for line in raw_lines:
        line_stripped = line.strip()
        if not line_stripped:
            base_y -= 12
            continue
        if re.match(r'^(第\d+章|\d+\.\d+|\d+\.\d+\.\d+)', line_stripped):
            font_size = 18
        else:
            font_size = 12
        lines.append({
            'text': line_stripped,
            'y0': base_y,
            'y1': base_y - font_size,
            'font_size': font_size
        })
        base_y -= (font_size + 6)
    return lines


# ---------- 改进的鲁棒标题匹配函数（仅这部分是新增/修改的） ----------
def normalize_text(text: str) -> str:
    """移除所有空白字符、转小写、移除常见标点"""
    text = re.sub(r'\s+', '', text)
    text = text.lower()
    text = re.sub(r'[，,。？?！!；;：:“”""''、\-\—\(\)（）【】《》]', '', text)
    return text


def extract_keywords(text: str) -> set:
    """提取标题中的关键词：数字编号、连续汉字、英文单词"""
    number_part = re.findall(r'\d+(?:\.\d+)*', text)
    chinese_part = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
    english_part = re.findall(r'[A-Za-z]+', text)
    keywords = set(number_part + chinese_part + english_part)
    if 'ui' in text.lower():
        keywords.add('ui')
    return keywords


def match_title_by_keywords(toc_title: str, line_text: str, threshold: float = 0.5) -> bool:
    """关键词集合匹配：正文行包含目录标题中超过 threshold 比例的关键词"""
    toc_keywords = extract_keywords(toc_title)
    if not toc_keywords:
        return False
    line_lower = line_text.lower()
    matched = sum(1 for kw in toc_keywords if kw.lower() in line_lower)
    return matched / len(toc_keywords) >= threshold


def find_title_line(lines: List[Dict], title: str, section: str = "") -> Optional[int]:
    """
    多级匹配策略：
    1. 若提供了章节编号，优先定位包含该编号的行，并验证关键词相似度
    2. 归一化完全匹配或包含匹配
    3. 关键词集合匹配
    4. 超宽松匹配（去除非字母数字）
    """
    norm_title = normalize_text(title)

    # 策略0：利用章节编号定位
    if section:
        num_match = re.search(r'[\d\.]+', section)
        if num_match:
            sec_num = num_match.group()
            for idx, line in enumerate(lines):
                if sec_num in line['text']:
                    if match_title_by_keywords(title, line['text']):
                        return idx
                    norm_line = normalize_text(line['text'])
                    if norm_title in norm_line or norm_line in norm_title:
                        return idx

    # 策略1：归一化包含匹配
    for idx, line in enumerate(lines):
        norm_line = normalize_text(line['text'])
        if norm_title == norm_line or norm_title in norm_line or norm_line in norm_title:
            return idx

    # 策略2：关键词集合匹配
    for idx, line in enumerate(lines):
        if match_title_by_keywords(title, line['text']):
            return idx

    # 策略3：超宽松匹配（去除非字母数字）
    def ultra_normalize(s: str) -> str:
        s = re.sub(r'\s+', '', s)
        s = re.sub(r'[^\w\u4e00-\u9fa5]', '', s)
        return s.lower()
    ultra_title = ultra_normalize(title)
    for idx, line in enumerate(lines):
        ultra_line = ultra_normalize(line['text'])
        if ultra_title == ultra_line or ultra_title in ultra_line:
            return idx

    return None


def points_to_cm(pt: float) -> float:
    return pt / 72.0 * 2.54


def check(pdf_pages: List, detected_offset: int = 0) -> List[Dict[str, str]]:
    # 1. 从目录提取标题（使用原版函数）
    toc_items = extract_toc_items(pdf_pages)
    if not toc_items:
        return [{"type": "error", "msg": "未在文档前部识别到有效的目录结构，无法进行标题间距检测。"}]

    filtered = [item for item in toc_items if get_title_level(item["section"]) in (1, 2, 3)]
    if not filtered:
        return [{"type": "warning", "msg": "目录中未找到一级、二级或三级标题，无法进行间距检测。"}]

    COMPENSATION = 0.2
    NORMAL_MAX_PT = 24
    NORMAL_MAX_CM = round(NORMAL_MAX_PT * points_to_cm(1), 2)

    report_lines = []
    warning_count = 0

    for item in filtered:
        page_idx = item["page"] + detected_offset - 1
        if page_idx < 0 or page_idx >= len(pdf_pages):
            report_lines.append(f"❌ **{item['section']} {item['title']}** (目录页码: {item['page']}) - 页码超出范围")
            warning_count += 1
            continue

        page = pdf_pages[page_idx]
        lines = extract_lines_from_page(page)
        if not lines:
            report_lines.append(f"⚠️ **{item['section']} {item['title']}** (第{page_idx+1}页) - 无法提取文本行信息")
            warning_count += 1
            continue

        # 使用改进的匹配函数
        title_idx = find_title_line(lines, item["title"], section=item["section"])
        if title_idx is None:
            report_lines.append(f"⚠️ **{item['section']} {item['title']}** (第{page_idx+1}页) - 未在页面中找到匹配的标题")
            warning_count += 1
            continue

        title_line = lines[title_idx]

        # 上行间距
        up_cm = None
        up_status = "无上一行"
        if title_idx > 0:
            prev = lines[title_idx - 1]
            raw_gap = title_line['y0'] - prev['y1']
            if raw_gap <= 0:
                compensated = prev['font_size'] * COMPENSATION
            else:
                compensated = raw_gap + prev['font_size'] * COMPENSATION
            up_pt = max(0, compensated)
            up_cm = round(points_to_cm(up_pt), 2)
            up_status = "正常" if up_pt <= NORMAL_MAX_PT else f"间距过大 (>{NORMAL_MAX_CM}cm)"

        # 下行间距
        down_cm = None
        down_status = "无下一行"
        if title_idx + 1 < len(lines):
            nxt = lines[title_idx + 1]
            raw_gap = nxt['y0'] - title_line['y1']
            if raw_gap <= 0:
                compensated = title_line['font_size'] * COMPENSATION
            else:
                compensated = raw_gap + title_line['font_size'] * COMPENSATION
            down_pt = max(0, compensated)
            down_cm = round(points_to_cm(down_pt), 2)
            down_status = "正常" if down_pt <= NORMAL_MAX_PT else f"间距过大 (>{NORMAL_MAX_CM}cm)"

        if (up_status not in ["无上一行", "正常"]) or (down_status not in ["无下一行", "正常"]):
            warning_count += 1

        line_text = f"{'✅' if (up_status in ['正常','无上一行'] and down_status in ['正常','无下一行']) else '⚠️'} **{item['section']} {item['title']}** (第{page_idx+1}页)"
        if up_cm is not None:
            line_text += f"\n- 上行间距: {up_cm}cm  判定: {up_status}"
        else:
            line_text += "\n- 上行间距: 无"
        if down_cm is not None:
            line_text += f"\n- 下行间距: {down_cm}cm  判定: {down_status}"
        else:
            line_text += "\n- 下行间距: 无"
        report_lines.append(line_text)

    if not report_lines:
        return [{"type": "info", "msg": "未检测到任何标题间距异常。"}]

    summary = f"📊 **论文标题间距检测报告**\n\n检测到 {len(filtered)} 个标题，其中 {warning_count} 个存在间距异常。\n\n"
    full_report = summary + "\n\n".join(report_lines)
    return [{"type": "warning" if warning_count > 0 else "info", "msg": full_report}]