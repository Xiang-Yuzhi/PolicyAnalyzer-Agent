import streamlit as st
import time
import os

# 导入我们的核心模块
from core.search import PolicySearcher
from core.analyzer import PolicyAnalyzer
from core.document_gen import ReportGenerator

# 页面配置
st.set_page_config(
    page_title="EFund 政策分析 Agent",
    page_icon="📈",
    layout="wide"
)

# --- 状态管理 (Session State) ---
# Streamlit 每次交互都会重跑代码，所以需要用 Session State 记住之前的搜索结果
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'is_analyzing' not in st.session_state:
    st.session_state.is_analyzing = False

# --- 侧边栏 ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Google_Homepage.svg/1200px-Google_Homepage.svg.png", caption="EFund Policy Agent v4.0", width=100) # 这里可以用 EFund Logo 替代
    st.markdown("### ⚙️ 设置")
    st.info("当前运行模式：Phase 1 (单文件分析)")
    
    # 简单的 Debug 信息
    if st.session_state.search_results:
        st.write(f"已缓存 {len(st.session_state.search_results)} 条搜索结果")

# --- 主界面 ---
st.title("📈 EFund 政策分析解读 Agent")
st.markdown("基于 **LangChain** + **Qwen-Max** 的智能投研助手")
st.divider()

# 1. 搜索区域
col1, col2 = st.columns([4, 1])
with col1:
    query = st.text_input("请输入政策关键词", placeholder="例如：上市公司减持管理办法 2024", label_visibility="collapsed")
with col2:
    search_btn = st.button("🔍 联网检索", use_container_width=True)

# 2. 处理搜索逻辑
if search_btn and query:
    with st.spinner("正在联网检索并进行权威性排序..."):
        # 调用核心 Search 模块
        results = PolicySearcher.search(query)
        st.session_state.search_results = results
        # 清空旧的分析结果
        st.session_state.analysis_result = None 

# 3. 展示搜索结果列表
if st.session_state.search_results:
    st.subheader("📋 检索结果 (按权威性排序)")
    
    # 构造用于 Radio 选择的标签列表
    # 格式: [Level X] 标题 (来源 - 日期)
    options = []
    for idx, r in enumerate(st.session_state.search_results):
        level = r.get('authority_level', 8)
        date = r.get('date', '未知日期')
        source = r.get('source', '未知来源')
        label = f"【Level {level}】{r['title']} ({source} - {date})"
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
        st.json(res)