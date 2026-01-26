import streamlit as st
import time
import os

# 导入核心模块
from core.search import PolicySearcher
from core.analyzer import PolicyAnalyzer
from core.document_gen import ReportGenerator
from core.router_agent import RouterAgent, Intent
from core.compare_agent import CompareAgent
from core.ranking_v2 import HybridRanker

# 页面配置
st.set_page_config(
    page_title="政策检索分析Agent",
    page_icon="📜",
    layout="wide"
)

# --- 易方达品牌配色 ---
EFUND_BLUE = "#004e9d"

st.markdown(f"""
    <style>
    /* 全局背景色 */
    .stApp {{
        background-color: #f8f9fa;
    }}
    
    /* 对齐侧边栏 Logo */
    [data-testid="stSidebar"] {{
        background-color: white;
        border-right: 1px solid #e0e0e0;
    }}
    
    /* 聊天消息气泡基础 */
    .chat-bubble {{
        padding: 12px 18px;
        border-radius: 20px;
        margin: 10px 0;
        max-width: 85%;
        font-size: 1rem;
        line-height: 1.5;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }}
    
    /* 用户消息 (右侧，浅蓝底) */
    .user-container {{
        display: flex;
        justify-content: flex-end;
        margin-bottom: 15px;
    }}
    .user-bubble {{
        background-color: #e8eaf6;
        color: #1a1a1a;
        border-bottom-right-radius: 5px;
        border-left: 3px solid #7986cb;
    }}
    
    /* 助手消息 (左侧，白底) */
    .agent-container {{
        display: flex;
        justify-content: flex-start;
        margin-bottom: 15px;
    }}
    .agent-bubble {{
        background-color: white;
        color: #1a1a1a;
        border-bottom-left-radius: 5px;
        border-left: 3px solid #28a745;
        border: 1px solid #eee;
    }}
    
    /* 搜索结果卡片 (Wireframe 2) */
    .result-card {{
        background: white;
        border: 1px solid #e0e0ff;
        border-left: 5px solid #004e9d;
        border-radius: 12px;
        padding: 18px;
        margin: 15px 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    }}
    
    .result-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }}
    
    .result-title {{
        font-weight: 600;
        font-size: 1.05rem;
        color: #333;
    }}
    
    .result-meta {{
        color: #777;
        font-size: 0.85rem;
    }}
    
    .result-snippet {{
        color: #555;
        font-size: 0.92rem;
        line-height: 1.6;
        padding: 10px;
        background: #fcfcff;
        border-radius: 6px;
        margin: 10px 0;
    }}
    
    /* 侧边栏“购物车”卡片样式 */
    .cart-item {{
        background: white;
        border: 1px solid #eee;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 8px;
        font-size: 0.85rem;
    }}
    
    /* 按钮样式微调 */
    div.stButton > button {{
        border-radius: 20px !important;
        font-weight: 500 !important;
        border: none !important;
    }}
    
    /* 针对侧边栏小按钮的特殊样式 */
    .side-small-btn {{
        font-size: 10px !important;
        padding: 2px 6px !important;
    }}
    
    /* 查看原文链接样式 */
    .source-link {{
        color: #004e9d;
        text-decoration: none;
        font-weight: 500;
        font-size: 0.85rem;
    }}
    .source-link:hover {{
        text-decoration: underline;
    }}

    /* 报告摘要汇总气泡 */
    .report-summary-bubble {{
        background-color: #f0f4ff;
        border: 1px solid #d0deff;
        border-radius: 15px;
        padding: 15px;
        margin: 15px 0;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- Session State 初始化 ---
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'policy_cache' not in st.session_state:
    st.session_state.policy_cache = []  # 暂存池
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'router' not in st.session_state:
    st.session_state.router = RouterAgent()
if 'compare_agent' not in st.session_state:
    st.session_state.compare_agent = CompareAgent()
if 'analysis_direction' not in st.session_state:
    st.session_state.analysis_direction = None
if 'trigger_compare' not in st.session_state:
    st.session_state.trigger_compare = False
if 'trigger_single_analysis' not in st.session_state:
    st.session_state.trigger_single_analysis = False
if 'active_stage' not in st.session_state:
    st.session_state.active_stage = "WELCOME"

# --- 侧边栏 (政策购物车) ---
with st.sidebar:
    logo_path = "assets/efund_logo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=180)
    else:
        st.markdown("### 📊 EFund")
    st.caption("版本号: v2.5-Agent")
    st.divider()
    
    # 政策购物车展示
    st.subheader("🛒 政策购物车")
    if st.session_state.policy_cache:
        for i, p in enumerate(st.session_state.policy_cache):
            with st.container():
                st.markdown(f"""
                <div class="cart-item">
                    <b>{i+1}. {p['title'][:20]}...</b>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🔍 分析", key=f"side_ana_{i}", use_container_width=True):
                        st.session_state.selected_for_analysis = p
                        st.session_state.active_stage = "ANALYSIS"
                        st.session_state.trigger_single_analysis = True
                        st.rerun()
                with c2:
                    if st.button("🗑️ 删除", key=f"side_del_{i}", use_container_width=True):
                        st.session_state.policy_cache.pop(i)
                        st.rerun()
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💼 组合分析", key="side_compare", use_container_width=True):
                st.session_state.active_stage = "ANALYSIS"
                st.session_state.trigger_compare = True
                st.rerun()
        with col2:
            if st.button("🧹 清空", key="side_clear", use_container_width=True):
                st.session_state.policy_cache = []
                st.rerun()
    else:
        st.info("购物车空空如也，快去检索并加入吧~")

# --- 主界面渲染控制 ---
if st.session_state.active_stage == "WELCOME":
    st.markdown("""
        <div style="text-align: center; padding: 40px 20px;">
            <h2 style="color: #004e9d;">您好，我是您的政策检索分析助手</h2>
            <p style="color: #666; font-size: 1.1rem;">
                您可以输入关键词或者通过自然语言向我发起查询询问～<br>
                也可以通过左侧或下方上传PDF文件进行分析。<br>
                我会尽力帮你找到匹配的政策，并协助展开分析。
            </p>
            <div style="margin-top: 30px; background: white; padding: 20px; border-radius: 15px; border: 1px dashed #ccc;">
                <p style="color: #888; margin-bottom: 10px;">您可以试试从这个开始：</p>
                <code style="background: #f0f4ff; padding: 5px 15px; border-radius: 5px; color: #004e9d; font-weight: bold; cursor: pointer;">
                    “帮我寻找公募基金业绩比较基准新规”
                </code>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- 对话历史展示 (在非欢迎阶段显示，或根据需要调整) ---
if st.session_state.active_stage != "WELCOME":
    chat_container = st.container()
    with chat_container:
        recent_messages = st.session_state.messages[-4:] if len(st.session_state.messages) > 4 else st.session_state.messages
        for msg in recent_messages:
            if msg["role"] == "user":
                st.markdown(f'<div class="user-container"><div class="chat-bubble user-bubble">👤 {msg["content"]}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="agent-container"><div class="chat-bubble agent-bubble">🤖 {msg["content"]}</div></div>', unsafe_allow_html=True)

# --- 进度感知占位符 ---
progress_container = st.container()

# --- 阶段 2: 搜索结果展示 ---
if st.session_state.active_stage == "SEARCH_RESULTS" and st.session_state.search_results:
    st.markdown('### 📊 精选检索结果', unsafe_allow_html=True)
    
    for idx, r in enumerate(st.session_state.search_results):
        is_cached = any(p['link'] == r['link'] for p in st.session_state.policy_cache)
        
        st.markdown(f"""
        <div class="result-card">
            <div class="result-header">
                <span class="result-title">{idx+1}. {r.get('source', '未知')}: {r['title']} [{r.get('date', '近期')}]</span>
                <a href="{r["link"]}" target="_blank" class="source-link">🔗 查看原文</a>
            </div>
            <div class="result-snippet">{r.get("snippet", "")}</div>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([1, 1, 4])
        with c1:
            if not is_cached:
                if st.button("🛒 加入购物车", key=f"cache_{idx}", use_container_width=True):
                    st.session_state.policy_cache.append(r)
                    st.rerun()
            else:
                st.button("✅ 已在库中", key=f"added_{idx}", disabled=True, use_container_width=True)
        with c2:
            if st.button("🔍 深度分析", key=f"analyze_{idx}", use_container_width=True):
                st.session_state.selected_for_analysis = r
                st.session_state.active_stage = "ANALYSIS"
                st.session_state.trigger_single_analysis = True
                st.rerun()
        st.divider()

# --- 阶段 3: 分析结果展示 ---
if st.session_state.active_stage == "ANALYSIS" and st.session_state.analysis_result:
    res = st.session_state.analysis_result
    
    st.markdown('<h3 style="color: #004e9d;">📝 报告要点汇总</h3>', unsafe_allow_html=True)
    
    # 核心观点气泡
    bullets_html = "".join([f"<li>{b}</li>" for b in res.get('chat_bullets', [])])
    st.markdown(f"""
    <div class="report-summary-bubble">
        <ul style="margin-bottom: 0px;">
            {bullets_html}
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # 操作栏 (展开详情 + 下载)
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        show_details = st.toggle("📄 展开报告详情", value=False)
    
    with c2:
        report_file = "EFund_Policy_Report.docx"
        ReportGenerator.generate_docx(res, report_file)
        p_info = res.get('selected_policy', {})
        fn = f"政策解读_{p_info.get('title', '报告')[:10]}.docx" if p_info else "分析报告.docx"
        
        with open(report_file, "rb") as f:
            st.download_button("📥 下载Word报告", f, file_name=fn, use_container_width=True)
            
    with c3:
        pdf_url = res.get('pdf_download_url')
        if pdf_url:
            st.link_button("📄 查看原始PDF", pdf_url, use_container_width=True)
    
    if show_details:
        st.divider()
        content = res.get('docx_content', {})
        for section, paragraphs in content.items():
            st.markdown(f"#### {section}")
            for p in paragraphs:
                st.write(p)
            st.divider()

st.divider()

# --- 用户输入区 ---
with st.container():
    # PDF 上传增强 (Wireframe 1)
    uploaded_file = st.file_uploader("📂 上传政策 PDF 进行深度分析 (可选)", type=['pdf'])
    if uploaded_file:
         if st.button("🚀 开始分析上传文件", use_container_width=True):
             st.info("🔄 正在解析上传的 PDF 文件...")
             # 这里后续可以接入 pdf_extractor 处理解析内容
             
    user_input = st.chat_input("请输入您的问题或指令（如：帮我找2024年减持新规）")

if user_input:
    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 意图解析
    context = {
        "search_results": st.session_state.search_results,
        "cached_policies": st.session_state.policy_cache
    }
    parsed = st.session_state.router.parse(user_input, context)
    
    # 根据意图执行不同操作
    if parsed.intent == Intent.SEARCH:
        # 进度展示 (在输入框上方)
        with progress_container.status("🔍 正在开启投研智能检索...", expanded=True) as status:
            st.write("📡 提取意图关键词...")
            search_params = st.session_state.router.extract_keywords(parsed.search_query)
            
            st.write(f"🌐 正在检索: {search_params['refined_query']}...")
            results = PolicySearcher.search(
                search_params['refined_query'],
                source_preference=search_params.get('source_preference', 'all'),
                time_range=search_params.get('time_range')
            )
            
            st.write("⚖️ 正在执行权威度与相关性混合排序 (Ranking V2)...")
            ranker = HybridRanker()
            results = ranker.rank(results, parsed.search_query)
            
            status.update(label="✅ 检索与排序完成！", state="complete", expanded=False)
        
        st.session_state.search_results = results
        st.session_state.active_stage = "SEARCH_RESULTS"
        if results:
            msg = f"✅ 已为您精选 {len(results)} 条政策，并按投研权威度排序。"
        else:
            msg = f"❌ 未找到与“{search_params.get('refined_query', parsed.search_query)}”相关的权威政策。建议尝试更简短的关键词。"
            
        st.session_state.messages.append({
            "role": "assistant",
            "content": msg
        })
    
    elif parsed.intent == Intent.SELECT_AND_CONTINUE:
        # 暂存 + 继续搜索
        if parsed.select_indices and st.session_state.search_results:
            for idx in parsed.select_indices:
                if 1 <= idx <= len(st.session_state.search_results):
                    policy = st.session_state.search_results[idx - 1]
                    if not any(p['link'] == policy['link'] for p in st.session_state.policy_cache):
                        st.session_state.policy_cache.append(policy)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"✅ 已暂存选中的政策。正在继续搜索: {parsed.search_query}..."
            })
        
        if parsed.search_query:
            with progress_container.status(f"🔍 正在继续搜索: {parsed.search_query}...", expanded=True) as status:
                st.write("📡 提取意图关键词...")
                search_params = st.session_state.router.extract_keywords(parsed.search_query)
                
                st.write(f"🌐 正在检索: {search_params['refined_query']}...")
                results = PolicySearcher.search(
                    search_params['refined_query'],
                    source_preference=search_params.get('source_preference', 'all'),
                    time_range=search_params.get('time_range')
                )
                
                st.write("⚖️ 正在执行权威度与相关性混合排序...")
                ranker = HybridRanker()
                results = ranker.rank(results, parsed.search_query)
                
                status.update(label="✅ 搜索更新完成！", state="complete", expanded=False)
                
            st.session_state.search_results = results
            st.session_state.active_stage = "SEARCH_RESULTS"
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"✅ 已根据您的新需求找到 {len(results)} 条相关政策。"
            })
    
    elif parsed.intent == Intent.SELECT_ONLY:
        # 仅暂存
        if parsed.select_indices and st.session_state.search_results:
            added = []
            for idx in parsed.select_indices:
                if 1 <= idx <= len(st.session_state.search_results):
                    policy = st.session_state.search_results[idx - 1]
                    if not any(p['link'] == policy['link'] for p in st.session_state.policy_cache):
                        st.session_state.policy_cache.append(policy)
                        added.append(policy['title'][:15])
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"✅ 已暂存: {', '.join(added)}..."
            })
    
    elif parsed.intent == Intent.ANALYZE_COMBINED:
        # 组合分析
        if len(st.session_state.policy_cache) >= 2:
            st.session_state.analysis_direction = parsed.analysis_direction
            st.session_state.active_stage = "ANALYSIS"
            st.session_state.trigger_compare = True
            st.rerun()
        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "❌ 组合分析需要至少2个政策，请先暂存更多政策。"
            })
    
    elif parsed.intent == Intent.ANALYZE_SINGLE:
        # 单篇分析 (通过自然语言触发)
        if parsed.select_indices and st.session_state.search_results:
            idx = parsed.select_indices[0]
            if 1 <= idx <= len(st.session_state.search_results):
                st.session_state.selected_for_analysis = st.session_state.search_results[idx - 1]
                st.session_state.active_stage = "ANALYSIS"
                st.session_state.trigger_single_analysis = True
                st.rerun()
    
    elif parsed.intent == Intent.CLEAR_CACHE:
        st.session_state.policy_cache = []
        st.session_state.messages.append({
            "role": "assistant",
            "content": "✅ 暂存池已清空。"
        })
    
    else:
        # 普通对话
        st.session_state.messages.append({
            "role": "assistant",
            "content": parsed.message or "我可以帮您检索政策、暂存感兴趣的文件、进行单独或组合分析。请告诉我您的需求。"
        })
    
    st.rerun()

# --- 触发单政策分析 ---
if st.session_state.get('trigger_single_analysis'):
    policy = st.session_state.get('selected_for_analysis')
    if policy:
        # 进度展示 (在输入框上方)
        progress_bar = progress_container.progress(0)
        status_text = progress_container.empty()
        
        def update_progress(msg, p):
            status_text.text(msg)
            progress_bar.progress(p)

        try:
            analyzer = PolicyAnalyzer()
            analysis_json = analyzer.analyze(policy, stage_callback=update_progress)
            
            if "error" not in analysis_json:
                st.session_state.analysis_result = analysis_json
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"✅ 《{policy['title']}》分析完成，报告已生成，请在下方查看或下载。"
                })
            else:
                st.error(f"分析失败: {analysis_json['error']}")
        
        except Exception as e:
            st.error(f"发生错误: {e}")
        
        finally:
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()
            st.session_state.trigger_single_analysis = False
            st.session_state.selected_for_analysis = None
            st.rerun()

# --- 触发组合分析 ---
if st.session_state.get('trigger_compare'):
    if len(st.session_state.policy_cache) >= 2:
        # 进度展示 (在输入框上方)
        progress_bar = progress_container.progress(0)
        status_text = progress_container.empty()
        
        def update_compare_progress(msg, p):
            status_text.text(msg)
            progress_bar.progress(p)

        try:
            result = st.session_state.compare_agent.analyze(
                st.session_state.policy_cache, 
                stage_callback=update_compare_progress,
                user_direction=st.session_state.get('analysis_direction')
            )
            
            if "error" not in result:
                st.session_state.analysis_result = result
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "✅ 组合分析完成，已为您生成 2000 字深度纵深研报。"
                })
            else:
                st.error(f"分析失败: {result['error']}")
        except Exception as e:
            st.error(f"发生错误: {e}")
        finally:
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()
            st.session_state.trigger_compare = False
            st.session_state.analysis_direction = None
            st.rerun()
    else:
        st.warning("组合分析需要至少2个政策，请先暂存更多政策。")
        st.session_state.trigger_compare = False
