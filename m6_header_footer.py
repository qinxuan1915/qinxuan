import math

def check(pdf_pages, detected_offset=0, **kwargs):
    """
    针对 PDFPageData 结构深度适配版
    1. 修正属性名：使用 p.lines (来自 file_reader.py)
    2. 修正坐标键：使用 top 和 bottom (来自 pdfplumber)
    """
    results = []
    pt_per_cm = 72 / 2.54 
    # 标准：3.6cm
    standard_cm = 3.6
    
    for i, p in enumerate(pdf_pages):
        page_num = getattr(p, 'page_num', i + 1)
        # 【关键修正】：file_reader.py 中定义的是 self.lines = words
        lines = getattr(p, 'lines', [])
        page_h = getattr(p, 'height', 842)
        
        if page_num < detected_offset:
            continue
            
        page_errors = []
        detail_data = []

        # 1. 页眉检测 (pdfplumber 提取的 word 字典包含 'top')
        header_candidates = [l for l in lines if isinstance(l, dict) and l.get('top', 0) < 200]
        if header_candidates:
            # 找最靠上的文字（top 值最小）
            header_candidates.sort(key=lambda x: x.get('top', 0))
            y_top = header_candidates[0].get('top', 0)
            real_top_cm = y_top / pt_per_cm
            detail_data.append(f"页眉实测:{real_top_cm:.2f}cm")
            
            if abs(real_top_cm - standard_cm) > 0.5:
                page_errors.append(f"页眉不合规(标3.6)")
        else:
            detail_data.append("未识别到页眉")
            page_errors.append("缺失页眉")

        # 2. 页脚检测 (pdfplumber 提取的 word 字典包含 'bottom')
        # 搜索页面底部 200pt 范围内的文字
        footer_candidates = [l for l in lines if isinstance(l, dict) and l.get('bottom', 0) > (page_h - 200)]
        if footer_candidates:
            # 找最靠下的文字（bottom 值最大）
            footer_candidates.sort(key=lambda x: x.get('bottom', 0), reverse=True)
            y_bottom = footer_candidates[0].get('bottom', 0)
            # 计算文字底边距离页面底部的物理距离
            dist_bottom_pt = page_h - y_bottom
            real_bottom_cm = dist_bottom_pt / pt_per_cm
            detail_data.append(f"页脚实测:{real_bottom_cm:.2f}cm")
            
            if abs(real_bottom_cm - standard_cm) > 0.5:
                page_errors.append(f"页脚不合规(标3.6)")
        else:
            detail_data.append("未识别到页脚")
            page_errors.append("缺失页脚")

        # 3. 结果汇总
        logic_page = max(1, page_num - detected_offset)
        status = "warning" if page_errors else "success"
        main_info = " | ".join(detail_data)
        
        if page_errors:
            display_msg = f"P{logic_page} (第{page_num}页): {main_info} => ❌ {' & '.join(page_errors)}"
        else:
            display_msg = f"P{logic_page} (第{page_num}页): {main_info} => ✅ 符合标准"

        results.append({"type": status, "msg": display_msg})

    return results