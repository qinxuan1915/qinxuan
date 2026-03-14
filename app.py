import streamlit as st
import time
import importlib
from utils.file_reader import read_pdf 

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="论文格式智能卫士",
    page_icon="🛡️",
    layout="wide"
)

# --- 2. 注入 CSS 样式 ---
st.markdown("""
<style>
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    .stApp { background-attachment: fixed; }
    h1 {
        background: linear-gradient(to right, #1e40af, #1e3a8a);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    [data-testid="stFileUploaderDropzone"] div div span { display: none; }
    [data-testid="stFileUploaderDropzone"] div div::after {
       content: "点击或拖拽 PDF 论文至此";
       text-align: center;
       color: #1e3a8a;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. 头部区域 ---
st.title("🛡️论文格式智能卫士")

# --- 4. 核心算法：自动计算偏移量 ---
def auto_detect_offset(pdf_pages):
    keywords = ["第一章", "第1章", "1引言", "1绪论", "1.引言"]
    for i, page in enumerate(pdf_pages):
        page_text = ""
        try:
            if hasattr(page, 'blocks'):
                page_text = "".join([b.get('text', '') if isinstance(b, dict) else getattr(b, 'text', '') for b in page.blocks[:30]])
            elif isinstance(page, list):
                page_text = "".join([block.get('text', '') for block in page[:30]])
        except: continue
        
        clean_text = page_text.replace(" ", "").replace("\n", "")
        for kw in keywords:
            if kw in clean_text:
                return i 
    return 6

# --- 5. 文件上传区 ---
uploaded_pdf = st.file_uploader("上传 PDF 论文", type=['pdf'], accept_multiple_files=False)

# --- 6. 核心处理逻辑 ---
if st.button("开始全自动扫描", type="primary"):
    if not uploaded_pdf:
        st.warning("请先上传 PDF 文件！")
    else:
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        # 1. 解析 PDF
        status_text.text("正在提取 PDF 矢量数据...")
        pdf_pages = read_pdf(uploaded_pdf)
        progress_bar.progress(40)

        # 2. 自动计算偏移量
        status_text.text("正在智能定位正文起始页...")
        detected_offset = auto_detect_offset(pdf_pages)
        time.sleep(0.5)
        progress_bar.progress(60)

        status_text.text(f"已自动匹配正文页码 (偏移量: {detected_offset})，正在运行检测...")
        
        # --- 7. 结果展示区 ---
        st.markdown("---")
        tabs = st.tabs([
            "1.目录与正文的一致性检测", "2.图表逻辑检测", "3.页眉距离检测", "4.章节检测"
        ])

        modules_config = [
            {"id": "m8_template",      "name": "模板与章节规范",     "tab": tabs[3]},
       	    {"id": "n3_toc",           "name": "目录标题与标号间距", "tab": tabs[0]}, 
            {"id": "m6_header_footer", "name": "页眉页脚与行距",     "tab": tabs[2]},
            {"id": "m4_images",        "name": "图表编号逻辑",       "tab": tabs[1]},
        ]

        for mod_cfg in modules_config:
            with mod_cfg["tab"]:
                try:
                    module = importlib.import_module(f"modules.{mod_cfg['id']}")
                    importlib.reload(module) 
                    
                    # 【核心修改点】：统一传递 detected_offset 参数
                    # 无论模块是否需要，都作为关键字参数传入
                    result_issues = module.check(pdf_pages, detected_offset=detected_offset)

                    if not result_issues:
                        st.success("✅ 该项指标符合规范")
                    else:
                        for issue in result_issues:
                            if issue.get('type') == 'html_report':
                                st.markdown(issue['html_content'], unsafe_allow_html=True)
                            else:
                                itype = issue.get('type', 'info')
                                msg = issue.get('msg', '检测到异常')
                                if itype == 'error': st.error(msg)
                                elif itype == 'warning': st.warning(msg)
                                else: st.info(msg)
                except Exception as e:
                    st.error(f"{mod_cfg['name']} 运行异常: {e}")
        
        progress_bar.progress(100)
        status_text.success(f"扫描完成！智能识别正文起始页：PDF 第 {detected_offset + 1} 页")