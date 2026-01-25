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
    /* 全局按钮样式 */
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
    
    /* 聊天消息样式 */
    .user-message {{
        background-color: #e3f2fd;
        padding: 12px 16px;
        border-radius: 12px;
        margin: 8px 0;
        border-left: 4px solid {EFUND_BLUE};
    }}
    .agent-message {{
        background-color: #f5f5f5;
        padding: 12px 16px;
        border-radius: 12px;
        margin: 8px 0;
        border-left: 4px solid #28a745;
    }}
    
    /* 政策卡片样式 */
    .policy-card {{
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        transition: all 0.2s;
    }}
    .policy-card:hover {{
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }}
    
    /* 暂存标签样式 */
    .cached-tag {{
        display: inline-block;
        background-color: #28a745;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;
        margin-left: 8px;
    }}
    
    /* 浅色模式优化 */
    @media (prefers-color-scheme: light) {{
        .stMarkdown, .stText, p, span, li {{
            color: #262730 !important;
        }}
    }}
    
    /* 深色模式适配 */
    @media (prefers-color-scheme: dark) {{
        h1, h2, h3 {{
            color: #4da3ff !important;
        }}
        .stMarkdown {{
            color: #e0e0e0;
        }}
        .user-message {{
            background-color: #1e3a5f;
            color: white;
        }}
        .agent-message {{
            background-color: #2d2d2d;
            color: #e0e0e0;
        }}
        .policy-card {{
            background: #1e1e1e;
            border-color: #444;
        }}
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

# --- 侧边栏 ---
with st.sidebar:
    logo_path = "assets/efund_logo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=180)
    else:
        st.markdown("### 📊 EFund")
    
    st.divider()
    st.info("🤖 Phase 2: 对话式政策分析")
    
    # 暂存池展示
    st.subheader("📌 暂存池")
    if st.session_state.policy_cache:
        for i, p in enumerate(st.session_state.policy_cache):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{i+1}. {p['title'][:25]}...")
            with col2:
                if st.button("✕", key=f"remove_{i}"):
                    st.session_state.policy_cache.pop(i)
                    st.rerun()
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 组合分析", use_container_width=True):
                st.session_state.trigger_compare = True
        with col2:
            if st.button("🗑️ 清空", use_container_width=True):
                st.session_state.policy_cache = []
                st.rerun()
    else:
        st.caption("暂无暂存政策")
        st.caption("💡 搜索后点击[暂存]或用自然语言选择")

# --- 主界面 ---
st.title("📜 政策检索分析 Agent")
st.caption("基于 LangChain + Qwen-Max 的智能投研助手 | 支持多轮对话与组合分析")
st.divider()

# --- 对话历史展示 (仅显示最新2条) ---
chat_container = st.container()
with chat_container:
    # 只展示最后2条消息，避免界面冗余
    recent_messages = st.session_state.messages[-2:] if len(st.session_state.messages) > 2 else st.session_state.messages
    for msg in recent_messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="user-message">👤 {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="agent-message">🤖 {msg["content"]}</div>', unsafe_allow_html=True)

# --- 搜索结果展示区 ---
if st.session_state.search_results:
    st.subheader("📋 检索结果 (已为您智能排序)")
    
    for idx, r in enumerate(st.session_state.search_results):
        is_cached = any(p['link'] == r['link'] for p in st.session_state.policy_cache)
        
        col1, col2, col3 = st.columns([5, 1, 1])
        with col1:
            title_display = r['title']
            if is_cached:
                title_display += ' <span class="cached-tag">已暂存</span>'
            
            date = r.get('date', '未知日期')
            source = r.get('source', '未知来源')
            
            st.markdown(f"**{idx+1}. {r['title']}**")
            st.caption(f"📅 {date} | 🏛️ {source}")
            
            if r.get('_scores'):
                scores = r['_scores']
                st.caption(f"评分: 权威{scores.get('authority', 0):.2f} | 相关{scores.get('bm25', 0):.2f}")
        
        with col2:
            if not is_cached:
                if st.button("📌 暂存", key=f"cache_{idx}"):
                    st.session_state.policy_cache.append(r)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"✅ 已暂存《{r['title'][:20]}...》"
                    })
                    st.rerun()
        
        with col3:
            if st.button("🔍 分析", key=f"analyze_{idx}"):
                st.session_state.selected_for_analysis = r
                st.session_state.trigger_single_analysis = True
                st.rerun()
        
        st.divider()

# --- 分析结果展示 ---
if st.session_state.analysis_result:
    res = st.session_state.analysis_result
    
    st.success("✅ 分析完成")
    
    # 核心观点
    st.subheader("💡 核心观点")
    bullets = res.get('chat_bullets', [])
    for b in bullets:
        st.markdown(f"- {b}")
    
    # 报告下载
    col1, col2 = st.columns([3, 1])
    with col2:
        report_file = "EFund_Policy_Report.docx"
        ReportGenerator.generate_docx(res, report_file)
        with open(report_file, "rb") as file:
            st.download_button(
                label="📥 下载word报告",
                data=file,
                file_name=f"政策解读_{res.get('selected_policy', {}).get('title', '报告')[:10]}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
    
    # 详细内容折叠
    with st.expander("📄 查看完整分析"):
        content = res.get('docx_content', {})
        for section, paragraphs in content.items():
            st.markdown(f"### {section}")
            for p in paragraphs:
                st.write(p)
            st.divider()

# --- 用户输入区 ---
st.divider()
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
        # 1. 提取结构化关键词 (Search Agent)
        search_params = st.session_state.router.extract_keywords(parsed.search_query)
        st.session_state.messages.append({
            "role": "assistant", 
            "content": f"🔍 正在从全网为您检索: **{search_params['refined_query']}**"
        })
        
        # 2. Stage 1: Recall
        results = PolicySearcher.search(
            search_params['refined_query'],
            source_preference=search_params.get('source_preference', 'all'),
            time_range=search_params.get('time_range')
        )
        
        # 3. Stage 2: Ranking
        ranker = HybridRanker()
        results = ranker.rank(results, parsed.search_query)
        
        st.session_state.search_results = results
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"✅ 已根据投研权威度及关联性为您精选 {len(results)} 条政策。"
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
            search_params = st.session_state.router.extract_keywords(parsed.search_query)
            results = PolicySearcher.search(
                search_params['refined_query'],
                source_preference=search_params.get('source_preference', 'all'),
                time_range=search_params.get('time_range')
            )
            ranker = HybridRanker()
            results = ranker.rank(results, parsed.search_query)
            st.session_state.search_results = results
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"✅ 找到 {len(results)} 条新的相关政策。"
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
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"🔍 正在对 {len(st.session_state.policy_cache)} 份政策进行组合分析..."
            })
            
            result = st.session_state.compare_agent.analyze(st.session_state.policy_cache)
            if "error" not in result:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"✅ 组合分析完成！\n\n**政策共同导向**: {result.get('common_direction', {}).get('summary', '')}\n\n**执行摘要**: {result.get('executive_summary', '')}"
                })
            else:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"❌ 分析失败: {result['error']}"
                })
        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "❌ 组合分析需要至少2个政策，请先暂存更多政策。"
            })
    
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
        # 定义进度回调
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(msg, p):
            status_text.text(msg)
            progress_bar.progress(p)

        try:
            analyzer = PolicyAnalyzer()
            # 调用带 RAG 增强的分析方法
            analysis_json = analyzer.analyze(policy, stage_callback=update_progress)
            
            if "error" not in analysis_json:
                st.session_state.analysis_result = analysis_json
                update_progress("✅ 分析完成！", 100)
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
        with st.spinner("🔍 正在进行组合政策分析..."):
            result = st.session_state.compare_agent.analyze(st.session_state.policy_cache)
            
            if "error" not in result:
                st.subheader("📊 组合分析结果")
                
                # 共同导向
                common = result.get('common_direction', {})
                st.markdown(f"### 政策共同导向")
                st.write(f"**监管立场**: {common.get('regulatory_stance', '未知')}")
                st.write(f"**核心信号**: {common.get('core_signal', '')}")
                st.write(common.get('summary', ''))
                
                # 市场影响与易方达操作建议
                impact = result.get('market_impact', {})
                st.markdown("### 市场影响与操作建议")
                st.write(f"**短期影响**: {impact.get('short_term', '')}")
                st.write(f"**长期影响**: {impact.get('long_term', '')}")
                
                # 易方达操作建议（从 investment_advice 中提取关注领域）
                advice = result.get('investment_advice', {})
                if advice.get('focus_areas'):
                    st.write(f"**易方达应关注领域**: {', '.join(advice.get('focus_areas', []))}")
                if advice.get('timing'):
                    st.write(f"**操作时机建议**: {advice.get('timing', '')}")
                
                # 执行摘要
                st.markdown("### 📋 执行摘要")
                st.info(result.get('executive_summary', ''))
            else:
                st.error(f"分析失败: {result['error']}")
    else:
        st.warning("组合分析需要至少2个政策，请先暂存更多政策。")
    
    st.session_state.trigger_compare = False
