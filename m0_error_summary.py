# modules/m0_error_summary.py
import streamlit as st
import importlib
import re
from typing import List, Dict, Any

ERROR_TYPES = ['error', 'warning']

OTHER_MODULES = [
    {"id": "n3_toc", "name": "目录一致性"},
    {"id": "m4_images", "name": "图表逻辑"},
    {"id": "m6_header_footer", "name": "页眉距离"},
    {"id": "m8_template", "name": "章节规范"},
    {"id": "m9_relation", "name": "关联性检测"},
    {"id": "m99", "name": "页面格式检测"},
    {"id": "m10_title_spacing", "name": "标题间距检测"},
    {"id": "m11_body_header_footer_distance", "name": "正文与页眉页脚距离"},
]


# ========== 专用解析函数 ==========
def extract_errors_from_n3_toc_report(msg: str) -> List[str]:
    """从 n3_toc 返回的 msg 中提取所有 ❌ 行"""
    errors = []
    for line in msg.split('\n'):
        line = line.strip()
        if line.startswith('❌'):
            # 去掉开头的 ❌ 和可能的 ** 标记，保留完整内容
            clean = re.sub(r'^❌\s*\*{0,2}', '', line)
            clean = re.sub(r'\*{2}', '', clean)  # 去掉剩余的 **
            errors.append(clean)
    return errors


def extract_errors_from_m10_title_spacing_report(msg: str) -> List[str]:
    """从 m10_title_spacing 返回的 msg 中提取所有 ⚠️ 行"""
    errors = []
    for line in msg.split('\n'):
        line = line.strip()
        if line.startswith('⚠️'):
            # 去掉 ⚠️ 前缀
            clean = re.sub(r'^⚠️\s*', '', line)
            errors.append(clean)
    return errors


def extract_errors_from_html_report(html_content: str, module_id: str) -> List[str]:
    """通用 html_report 解析（保留，供其他模块使用）"""
    errors = []
    for line in html_content.split('\n'):
        line = line.strip()
        if line and ('❌' in line or '⚠️' in line):
            errors.append(line)
    return errors


# ========== 核心调用函数 ==========
def get_module_errors(module_id: str, module_name: str,
                      pdf_pages: List, detected_offset: int,
                      pdf_file=None) -> List[str]:
    try:
        module = importlib.import_module(f"modules.{module_id}")
        importlib.reload(module)
        if module_id == "m99":
            result = module.check(pdf_pages, detected_offset=detected_offset, pdf_file=pdf_file)
        else:
            result = module.check(pdf_pages, detected_offset=detected_offset)

        errors = []
        if result is None:
            return errors
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    item_type = item.get('type')
                    # 特殊处理：对于 n3_toc 和 m10_title_spacing，解析它们的 msg
                    if module_id == "n3_toc" and item_type in ERROR_TYPES:
                        msg = item.get('msg', '')
                        if msg:
                            extracted = extract_errors_from_n3_toc_report(msg)
                            errors.extend(extracted)
                    elif module_id == "m10_title_spacing" and item_type in ERROR_TYPES:
                        msg = item.get('msg', '')
                        if msg:
                            extracted = extract_errors_from_m10_title_spacing_report(msg)
                            errors.extend(extracted)
                    elif item_type in ERROR_TYPES:
                        msg = item.get('msg', '')
                        if msg:
                            errors.append(msg)
                    elif item_type == 'html_report':
                        html_content = item.get('html_content', '')
                        if html_content:
                            extracted = extract_errors_from_html_report(html_content, module_id)
                            errors.extend(extracted)
                elif isinstance(item, str):
                    errors.append(item)
                else:
                    errors.append(str(item))
        elif isinstance(result, str):
            errors.append(result)
        else:
            errors.append(str(result))
        return errors
    except Exception as e:
        return [f"❌ 模块运行异常: {str(e)}"]


def collect_all_errors(pdf_pages, detected_offset, pdf_file):
    modules_stats = []
    total_errors = 0
    for cfg in OTHER_MODULES:
        error_msgs = get_module_errors(cfg["id"], cfg["name"], pdf_pages, detected_offset, pdf_file)
        error_count = len(error_msgs)
        total_errors += error_count
        modules_stats.append({
            "name": cfg["name"],
            "error_msgs": error_msgs,
            "error_count": error_count,
        })
    return {
        "total_modules": len(OTHER_MODULES),
        "total_errors": total_errors,
        "modules": modules_stats,
    }


def generate_html_report(pdf_pages, detected_offset, pdf_file):
    stats = collect_all_errors(pdf_pages, detected_offset, pdf_file)

    css = """
    <style>
    .error-summary-container {
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .error-summary-container h3 {
        color: #1e3a8a;
        margin-bottom: 10px;
    }
    .error-summary-container .total-success {
        color: green;
        font-weight: bold;
        margin: 10px 0;
    }
    .error-summary-container .total-warning {
        color: #ff4b4b;
        font-weight: bold;
        margin: 10px 0;
    }
    .error-summary-container hr {
        margin: 15px 0;
    }
    .error-summary-container .module-title {
        font-size: 1.2rem;
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 5px;
        border-left: 5px solid #0a58ca;
        padding-left: 12px;
    }
    .error-summary-container .error-box-red {
        border: 2px solid #ff4b4b;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        background-color: #fff0f0;
        color: #000000;
    }
    .error-summary-container .no-error-box-blue {
        border: 2px solid #1e88e5;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        background-color: #e3f2fd;
        color: #000000;
    }

    /* 深色模式适配 */
    [data-theme="dark"] .error-summary-container .error-box-red {
        background-color: #4a1a1a;
        border-color: #ff6b6b;
        color: #f0f0f0;
    }
    [data-theme="dark"] .error-summary-container .no-error-box-blue {
        background-color: #1a3a4a;
        border-color: #4da8ff;
        color: #f0f0f0;
    }
    [data-theme="dark"] .error-summary-container h3 {
        color: #7baaf7;
    }
    [data-theme="dark"] .error-summary-container .module-title {
        border-left-color: #7baaf7;
        color: #e0e0e0;
    }
    [data-theme="dark"] .error-summary-container .total-success {
        color: #6fcf97;
    }
    [data-theme="dark"] .error-summary-container .total-warning {
        color: #ff8a8a;
    }
    [data-theme="dark"] .error-summary-container hr {
        border-color: #444;
    }
    </style>
    """

    html = f"""
    <div class="error-summary-container">
    {css}
    <h3>📊 错误统计总览（共 {stats['total_modules']} 个检测模块）</h3>
    """

    if stats['total_errors'] == 0:
        html += '<div class="total-success">✅ 所有模块均未发现格式错误，总计 0 个错误。</div>'
    else:
        html += f'<div class="total-warning">⚠️ 共发现 {stats["total_errors"]} 个格式错误，详见下方各模块明细。</div>'

    html += "<hr>"

    for module in stats['modules']:
        module_name = module['name']
        error_count = module['error_count']
        error_msgs = module['error_msgs']

        html += f'<div class="module-title">● {module_name}（错误数：{error_count}）</div>'

        if error_count == 0:
            html += '<div class="no-error-box-blue">📄 无</div>'
        else:
            for idx, err_msg in enumerate(error_msgs, 1):
                safe_msg = err_msg.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                safe_msg = safe_msg.replace('\n', '<br>')
                html += f'<div class="error-box-red">🔴 错误 {idx}:<br>{safe_msg}</div>'
        html += "<br>"

    html += "</div>"
    return html


def check(pdf_pages, detected_offset, pdf_file=None):
    html_content = generate_html_report(pdf_pages, detected_offset, pdf_file)
    return [{"type": "html_report", "html_content": html_content}]