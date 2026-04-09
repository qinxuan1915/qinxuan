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

# --- 4. 增强版算法：物理偏移量智能定位 ---
def get_clean_text(page):
    """提取并清洗页面文本"""
    try:
        if hasattr(page, 'blocks'):
            blocks = page.blocks
            text = "".join([b.get('text', '') if isinstance(b, dict) else getattr(b, 'text', '') for b in blocks])
        else:
            text = str(getattr(page, 'text', ""))
        # 移除空格、换行符和回车符，确保匹配稳健
        return text.replace(" ", "").replace("\n", "").replace("\r", "")
    except:
        return ""

def auto_detect_offset(pdf_pages):
    """
    针对该 PDF 优化的定位法：
    1. 排除包含“....”点号的目录页。
    2. 必须同时包含：第1章绪论、1.1课题背景及研究现状。
    """
    for i in range(len(pdf_pages)):
        page_raw_text = get_clean_text(pdf_pages[i])
        
        # --- 策略 A：排除目录页干扰 ---
        if page_raw_text.count("....") > 5:
            continue
            
        # --- 策略 B：双层标题同时出现匹配 ---
        has_l1 = ("第1章绪论" in page_raw_text) or ("1绪论" in page_raw_text)
        has_l2 = ("1.1课题背景及研究现状" in page_raw_text) or ("1.1课题背景" in page_raw_text)

        if has_l1 and has_l2:
            return i 
    
    return None 

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
        
        # --- 校验结果 ---
        if detected_offset is None:
            progress_bar.empty()
            status_text.empty()
            st.error("❌ 无法自动定位正文。请检查正文第一页是否包含“第1章 绪论”及“1.1 课题背景...”标题。")
        else:
            progress_bar.progress(60)
            status_text.success(f"定位成功！正文起始于 PDF 第 {detected_offset + 1} 页")
            
            # --- 7. 结果展示区 ---
            st.markdown("---")
            tabs = st.tabs([
                "错误统计",  # 新增
                "1.目录一致性",
                "2.图表逻辑",
                "3.页眉页脚与页边距检测",
                "4.章节规范",
                "5.关联性检测",
                "6.页面格式",
                "7.标题行距检测",
                "8.页眉页脚与正文距离检测"
            ])

            modules_config = [
                {"id": "m0_error_summary", "name": "错误统计", "tab": tabs[0]},  # 新增
                {"id": "m8_template", "name": "章节规范", "tab": tabs[4]},  # 原 tabs[3] -> tabs[4]
                {"id": "n3_toc", "name": "目录一致性", "tab": tabs[1]},  # 原 tabs[0] -> tabs[1]
                {"id": "m6_header_footer", "name": "页眉距离", "tab": tabs[3]},  # 原 tabs[2] -> tabs[3]
                {"id": "m4_images", "name": "图表逻辑", "tab": tabs[2]},  # 原 tabs[1] -> tabs[2]
                {"id": "m9_relation", "name": "关联性检测", "tab": tabs[5]},  # 原 tabs[4] -> tabs[5]
                {"id": "m99", "name": "页面格式检测", "tab": tabs[6]},  # 原 tabs[5] -> tabs[6]
                {"id": "m10_title_spacing", "name": "标题间距检测", "tab": tabs[7]},  # 原 tabs[6] -> tabs[7]
                {"id": "m11_body_header_footer_distance", "name": "正文与页眉页脚距离", "tab": tabs[8]},
                # 原 tabs[7] -> tabs[8]
            ]

            for mod_cfg in modules_config:
                with mod_cfg["tab"]:
                    try:
                        module = importlib.import_module(f"modules.{mod_cfg['id']}")
                        importlib.reload(module)

                        # --- 核心修改点 ---
                        # m99和m0模块，都显式传入 pdf_file 参数，触发内部原生读取逻辑
                        if mod_cfg["id"] == "m99" or mod_cfg["id"] == "m0_error_summary":
                            result_issues = module.check(pdf_pages, detected_offset=detected_offset,
                                                         pdf_file=uploaded_pdf)
                        else:
                            result_issues = module.check(pdf_pages, detected_offset=detected_offset)
                        if not result_issues:
                            st.success(f"✅ {mod_cfg['name']} 未发现明显异常")
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
