# modules/m11_body_header_footer_distance.py
"""
正文与页眉/页脚距离检测模块（改进版）
"""

import math

# 页眉/页脚候选区域高度（cm）
CANDIDATE_ZONE_CM = 5.0
# 正文与页眉/页脚的最小安全距离（cm）—— 已从0.5改为0.25
MIN_DISTANCE_CM = 0.25


def check(pdf_pages, detected_offset=0, **kwargs):
    results = []
    pt_per_cm = 72 / 2.54
    candidate_zone_pt = CANDIDATE_ZONE_CM * pt_per_cm

    for i, page in enumerate(pdf_pages):
        page_num = getattr(page, 'page_num', i + 1)
        # 修正：跳过非正文页（detected_offset 是正文起始索引，page_num 从1开始）
        if page_num <= detected_offset:
            continue

        lines = getattr(page, 'lines', [])
        page_height = getattr(page, 'height', 842)

        # 1. 页眉候选（顶部 candidate_zone_pt 内）
        header_candidates = [
            w for w in lines if isinstance(w, dict) and w.get('top', 0) <= candidate_zone_pt
        ]
        # 页脚候选（底部 candidate_zone_pt 内）
        footer_candidates = [
            w for w in lines if isinstance(w, dict) and w.get('bottom', 0) >= page_height - candidate_zone_pt
        ]

        # 2. 确定页眉文字（取最靠上的）
        header = None
        if header_candidates:
            header = min(header_candidates, key=lambda w: w['top'])

        # 3. 确定页脚文字（取最靠下的）
        footer = None
        if footer_candidates:
            footer = max(footer_candidates, key=lambda w: w['bottom'])

        # 4. 正文区域（排除页眉和页脚区域内的文字）
        body_words = [
            w for w in lines if isinstance(w, dict)
            and (header is None or w['bottom'] > header['bottom'])
            and (footer is None or w['top'] < footer['top'])
        ]

        # 5. 计算距离
        logic_page = max(1, page_num - detected_offset)
        details = []
        issues = []

        # 页眉侧
        if header is None:
            details.append("未检测到页眉")
            issues.append("缺少页眉")
        elif not body_words:
            details.append("无正文内容")
            issues.append("无正文内容")
        else:
            # 正文第一行 top
            body_top = min(w['top'] for w in body_words)
            # 页眉文字 bottom
            header_bottom = header['bottom']
            distance_pt = body_top - header_bottom
            distance_cm = distance_pt / pt_per_cm
            details.append(f"正文↘页眉: {distance_cm:.2f} cm")
            if distance_cm < MIN_DISTANCE_CM:
                issues.append(f"正文与页眉过近 ({distance_cm:.2f} < {MIN_DISTANCE_CM} cm)")

        # 页脚侧
        if footer is None:
            details.append("未检测到页脚")
            issues.append("缺少页脚")
        elif not body_words:
            if "无正文内容" not in issues:
                details.append("无正文内容")
                issues.append("无正文内容")
        else:
            # 正文最后一行 bottom
            body_bottom = max(w['bottom'] for w in body_words)
            # 页脚文字 top
            footer_top = footer['top']
            distance_pt = footer_top - body_bottom
            distance_cm = distance_pt / pt_per_cm
            details.append(f"正文↗页脚: {distance_cm:.2f} cm")
            if distance_cm < MIN_DISTANCE_CM:
                issues.append(f"正文与页脚过近 ({distance_cm:.2f} < {MIN_DISTANCE_CM} cm)")

        # 结果输出
        detail_str = " | ".join(details)
        if issues:
            msg = f"P{logic_page} (第{page_num}页): {detail_str} → ❌ {', '.join(issues)}"
            results.append({"type": "warning", "msg": msg})
        else:
            msg = f"P{logic_page} (第{page_num}页): {detail_str} → ✅ 间距合规"
            results.append({"type": "success", "msg": msg})

    return results