import streamlit as st
import time
import os

# 导入我们的核心模块
from core.search import PolicySearcher
from core.analyzer import PolicyAnalyzer
from core.document_gen import ReportGenerator

# 页面配置
st.set_page_config(
    page_title="政策检索分析Agent",
    page_icon="📜",
    layout="wide"
)

# --- 易方达品牌配色 (EFund Deep Blue) ---
EFUND_BLUE = "#004e9d"

st.markdown(f"""
    <style>
    /* 基础按钮样式 (Global EFund Blue for both Light/Dark) */
    div.stButton > button {{
        background-color: {EFUND_BLUE} !important;
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        transition: all 0.3s;
    }}
    div.stButton > button:hover {{
        background-color: #003a75 !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }}

    /* 默认浅色模式针对性优化 */
    .dark-only {{ display: none !important; }}
    
    @media (prefers-color-scheme: light) {{
        /* 针对用户反馈的“浅灰色”部分进行强化 */
        .stMarkdown, .stText, p, span, li, [data-testid="stExpander"] p, [data-testid="stExpander"] div {{
            color: #262730 !important; /* 加深为接近黑色 */
        }}
        .stCaption {{
            color: #555 !important;
        }}
    }}
    
    /* 深色模式下的样式覆盖 (Keep Current EFund Blue Scheme) */
    @media (prefers-color-scheme: dark) {{
        .light-only {{ display: none !important; }}
        .dark-only {{ display: block !important; }}
        
        :root {{
            --efund-blue: {EFUND_BLUE};
            --button-hover: #003a75;
        }}
        
        /* 进度条颜色 */
        .stProgress > div > div > div > div {{
            background-color: var(--efund-blue);
        }}
        
        /* 标题颜色适配 */
        h1, h2, h3 {{
            color: #4da3ff !important;
            font-family: "Microsoft YaHei", sans-serif;
        }}
        
        .stMarkdown {{
            color: #e0e0e0;
        }}
        
        [data-testid="stSidebar"] {{
            border-right: 1px solid rgba(128, 128, 128, 0.2);
        }}
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 状态管理 (Session State) ---
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'is_analyzing' not in st.session_state:
    st.session_state.is_analyzing = False

# --- 侧边栏 ---
with st.sidebar:
    # 使用上传的 Logo 截图
    logo_path = r"assets/efund_logo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=200)
    else:
        st.image("https://upload.wikimedia.org/wikipedia/commons/2/2f/E_Fund_Management_Logo.png", width=180)
    
    st.divider()
    st.info("当前运行模式：Phase 1 (单文件分析)")
    
    if st.session_state.search_results:
        st.write(f"已缓存 {len(st.session_state.search_results)} 条搜索结果")

# --- 主界面 ---
st.markdown('<h1 class="light-only">📈 EFund 政策分析解读 Agent</h1>', unsafe_allow_html=True)
st.markdown('<h1 class="dark-only">📜 政策检索分析Agent</h1>', unsafe_allow_html=True)

st.markdown('<div class="light-only"><p>基于 <b>LangChain</b> + <b>Qwen-Max</b> 的智能投研助手</p></div>', unsafe_allow_html=True)
st.markdown('<div class="dark-only"><h3 style="font-size: 1.2rem; font-weight: normal;">基于 <b>LangChain</b> + <b>Qwen-Max</b> 的智能政策专家</h3></div>', unsafe_allow_html=True)
st.divider()

# 1. 搜索区域
col1, col2 = st.columns([4, 1])
with col1:
    query = st.text_input("请输入政策关键词及时间（可选）", placeholder="例如：上市公司减持管理办法 2024", label_visibility="collapsed")
with col2:
    search_btn = st.button("🔍 联网检索", use_container_width=True)

# 2. 处理搜索逻辑
if (search_btn or (query and query != st.session_state.get('last_query', ''))) and query:
    st.session_state.last_query = query
    with st.spinner("正在进行多维度检索与排序..."):
        results = PolicySearcher.search(query)
        st.session_state.search_results = results
        st.session_state.analysis_result = None 

# 3. 展示搜索结果列表
if st.session_state.search_results:
    st.subheader("📋 检索结果 (已为您智能排序)")
    
    # 修改：不显示 Level 层级
    options = []
    for idx, r in enumerate(st.session_state.search_results):
        date = r.get('date', '未知日期')
        source = r.get('source', '未知来源')
        label = f"{r['title']} ({source} - {date})"
        options.append(label)

    # 让用户选择一个文件
    selected_option = st.radio(
        "请选择需要深度解读的政策文件：",
        options,
        index=0
    )
    
    # 获取用户选中的原始数据索引
    selected_index = options.index(selected_option)
    target_policy = st.session_state.search_results[selected_index]
    
    # 显示选中文件的详情 Preview
    with st.expander("查看选中文件详情", expanded=False):
        st.write(f"**链接**: {target_policy['link']}")
        st.write(f"**摘要**: {target_policy.get('snippet', '')}")

    st.divider()

    # 4. 分析按钮
    analyze_btn = st.button("🚀 开始深度解读 (Agent)", type="primary")

    if analyze_btn:
        st.session_state.is_analyzing = True
        
        # 创建进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            analyzer = PolicyAnalyzer()
            
            # Step 1: 抓取
            status_text.text("正在访问目标网页抓取全文...")
            progress_bar.progress(30)
            
            # Step 2: 思考
            status_text.text("正在调用 Qwen-Max 进行投研逻辑分析...")
            progress_bar.progress(60)
            
            # 调用核心 Analyze 模块
            analysis_json = analyzer.analyze(target_policy)
            
            if "error" in analysis_json:
                st.error(f"分析失败: {analysis_json['error']}")
            else:
                st.session_state.analysis_result = analysis_json
                status_text.text("分析完成！")
                progress_bar.progress(100)
                
        except Exception as e:
            st.error(f"发生未知错误: {e}")
        finally:
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()

# 5. 展示分析结果
if st.session_state.analysis_result:
    res = st.session_state.analysis_result
    
    st.success("✅ 解读完成")
    
    # 分两列展示：左边是 Bullet Points (核心)，右边是下载
    result_col1, result_col2 = st.columns([2, 1])
    
    with result_col1:
        st.subheader("💡 核心观点 (Key Takeaways)")
        bullets = res.get('chat_bullets', [])
        for b in bullets:
            st.markdown(f"- {b}")
            
    with result_col2:
        st.subheader("📂 报告下载")
        st.write("获取包含详细依据的完整 Word 报告")
        
        # 实时生成 Word
        # 为了防止文件名冲突，可以使用临时文件，这里简单起见用固定文件名
        report_file = "EFund_Policy_Report.docx"
        ReportGenerator.generate_docx(res, report_file)
        
        with open(report_file, "rb") as file:
            btn = st.download_button(
                label="📥 下载 .docx 报告",
                data=file,
                file_name=f"政策解读_{res['selected_policy']['title'][:10]}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

    # 详细内容的折叠展示
    with st.expander("查看完整分析内容"):
        # 1. 政策基本信息
        st.markdown("### 📄 政策基本信息")
        policy = res.get('selected_policy', {})
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**标题**: {policy.get('title', '-')}")
            st.write(f"**发布机构**: {policy.get('issuer', '-')}")
        with col2:
            st.write(f"**发布日期**: {policy.get('publish_date', '-')}")
            st.write(f"**来源链接**: [{policy.get('url', '-')}]({policy.get('url', '#')})")
        
        st.divider()
        
        # 2. 详细分析内容
        content = res.get('docx_content', {})
        
        # 摘要
        if content.get('摘要'):
            st.markdown("### 📋 摘要")
            for para in content['摘要']:
                st.write(para)
            st.divider()
        
        # 政策要点与变化
        if content.get('政策要点与变化'):
            st.markdown("### 🔍 政策要点与变化")
            for para in content['政策要点与变化']:
                st.write(para)
            st.divider()
        
        # 对指数及其行业的影响
        if content.get('对指数及其行业的影响'):
            st.markdown("### 📊 对指数及其行业的影响")
            for para in content['对指数及其行业的影响']:
                st.write(para)
            st.divider()
        
        # 对指数基金管理公司的建议
        if content.get('对指数基金管理公司的建议'):
            st.markdown("### 💡 对指数基金管理公司的建议")
            for para in content['对指数基金管理公司的建议']:
                st.write(para)
            st.divider()
        
        # 对易方达的战略行动建议
        if content.get('对易方达的战略行动建议'):
            st.markdown("### 🎯 对易方达的战略行动建议")
            for para in content['对易方达的战略行动建议']:
                st.write(para)

