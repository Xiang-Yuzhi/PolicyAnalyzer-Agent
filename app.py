import streamlit as st
import time
import os

# 导入核心模块
from core.search import PolicySearcher
from core.analyzer import PolicyAnalyzer
from core.document_gen import ReportGenerator
from core.router_agent import RouterAgent, Intent, ParsedIntent
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
    
    .section-header {{
        font-size: 1.1rem;
        font-weight: bold;
        color: #004e9d;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }}

    /* 搜索结果摘要样式 */
    .snippet-text {{
        color: #555;
        font-size: 0.9rem;
        line-height: 1.6;
        margin-top: 6px;
        min-height: 4.2em; /* 确保至少3行空间 */
    }}
    
    .source-link {{
        color: #004e9d;
        text-decoration: none;
        font-size: 0.85rem;
        margin-left: 10px;
    }}
    .source-link:hover {{
        text-decoration: underline;
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

    /* 粘性底部容器 (进度条 + 输入框) */
    .sticky-bottom {{
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background: white;
        padding: 10px 20px;
        z-index: 999;
        border-top: 1px solid #eee;
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
if 'search_cache' not in st.session_state:
    st.session_state.search_cache = {}  # 搜索结果缓存：{query: results}
if 'current_raw_query' not in st.session_state:
    st.session_state.current_raw_query = None
if 'is_result_from_cache' not in st.session_state:
    st.session_state.is_result_from_cache = False

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
    col_h1, col_h2 = st.columns([5, 1])
    with col_h1:
        header_text = "📋 精选检索结果"
        if st.session_state.is_result_from_cache:
            header_text += " (来自缓存 ♻️)"
        st.markdown(f'<p class="section-header">{header_text}</p>', unsafe_allow_html=True)
    with col_h2:
        if st.session_state.is_result_from_cache:
            if st.button("🔄 重新检索", use_container_width=True, help="清除当前搜索缓存并尝试生成新的结果"):
                # 清除当前缓存
                q = st.session_state.current_raw_query
                if q in st.session_state.search_cache:
                    del st.session_state.search_cache[q]
                # 注入一个特殊消息来触发强制检索
                st.session_state.messages.append({"role": "user", "content": f"强制刷新检索: {q}"})
                st.rerun()
    st.divider()
    
    for idx, r in enumerate(st.session_state.search_results):
        is_cached = any(p['link'] == r['link'] for p in st.session_state.policy_cache)
        
        # 统一标题格式：标题 + 日期 + 机构
        full_title = f"{r['title']} [{r.get('date', '未知')}] ({r.get('source', '未知')})"
        
        with st.container():
            col1, col2 = st.columns([6, 1])
            with col1:
                st.markdown(f"**{idx+1}. {r['title']}**")
                
                # 元信息行（日期、机构、链接）
                meta_parts = []
                if r.get('date'):
                    meta_parts.append(f"📅 {r['date']}")
                if r.get('source'):
                    meta_parts.append(f"🏛️ {r['source']}")
                if is_cached:
                    meta_parts.append('<span class="cached-tag">已暂存</span>')
                meta_parts.append(f'<a href="{r["link"]}" target="_blank" class="source-link">🔗 查看原文</a>')
                st.markdown(" | ".join(meta_parts), unsafe_allow_html=True)
                
                # 完整原文摘要 (保持真实3行)
                st.markdown(f'<div class="snippet-text">{r.get("snippet", "")}</div>', unsafe_allow_html=True)
            
            with col2:
                if not is_cached:
                    if st.button("📌 暂存", key=f"cache_{idx}", use_container_width=True):
                        st.session_state.policy_cache.append(r)
                        st.rerun()
                
                if st.button("🔍 分析", key=f"analyze_{idx}", use_container_width=True):
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
        
        # 处理文件名
        p_info = res.get('selected_policy', {})
        pa_list = res.get('policies_analyzed', [])
        if p_info:
            fn = f"政策解读_{p_info.get('title', '报告')[:10]}.docx"
        else:
            fn = f"组合分析报告_{len(pa_list)}份.docx"
            
        with open(report_file, "rb") as file:
            st.download_button(
                label="📥 下载word报告",
                data=file,
                file_name=fn,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
        
        # 新增：原始 PDF 下载链接
        pdf_url = res.get('pdf_download_url')
        if pdf_url:
            st.link_button("📄 查看原始PDF", pdf_url, use_container_width=True)
    
    if res.get('policies_analyzed'):
        st.subheader(f"📊 组合分析结果 ({len(res['policies_analyzed'])} 份)")
    
    # 详细内容折叠
    with st.expander("📄 查看完整分析"):
        content = res.get('docx_content', {})
        for section, paragraphs in content.items():
            st.markdown(f"### {section}")
            for p in paragraphs:
                st.write(p)
            st.divider()

# --- 底部固定区 (进度条 + 输入框) ---
# 将进度条放置在最下方，紧邻输入框
progress_container = st.container()

# --- 用户输入区 ---
user_input = st.chat_input("请输入您的问题或指令（如：帮我找2024年减持新规）")

if user_input:
    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 意图解析
    if user_input.startswith("强制刷新检索:"):
        parsed = ParsedIntent(intent=Intent.SEARCH, search_query=user_input.replace("强制刷新检索:", "").strip())
    else:
        context = {
            "search_results": st.session_state.search_results,
            "cached_policies": st.session_state.policy_cache
        }
        parsed = st.session_state.router.parse(user_input, context)
    
    # 根据意图执行不同操作
    if parsed.intent == Intent.SEARCH:
        # 首先检查缓存
        raw_query = parsed.search_query.strip()
        # 处理强制刷新指令
        is_force_refresh = user_input.startswith("强制刷新检索:")
        if is_force_refresh:
            raw_query = user_input.replace("强制刷新检索:", "").strip()
            if raw_query in st.session_state.search_cache:
                del st.session_state.search_cache[raw_query]

        if raw_query in st.session_state.search_cache and not is_force_refresh:
            st.session_state.search_results = st.session_state.search_cache[raw_query]
            st.session_state.is_result_from_cache = True
            st.session_state.current_raw_query = raw_query
            msg = f"♻️ 已从缓存为您恢复 “{raw_query}” 的精选结果。"
        else:
            # 进度展示 (在输入框上方)
            with progress_container.status("🔍 正在开启投研智能检索...", expanded=True) as status:
                st.write("📡 提取意图关键词...")
                # 刷新时：稍微调高温度以增加多样性
                temp = 0.2 if is_force_refresh else 0.0
                search_params = st.session_state.router.extract_keywords(parsed.search_query, temperature=temp) 
                
                st.write(f"🌐 正在检索: {search_params['refined_query']}...")
                results = PolicySearcher.search(
                    search_params['refined_query'],
                    source_preference=search_params.get('source_preference', 'all'),
                    time_range=search_params.get('time_range')
                )
                
                st.write("⚖️ 正在执行权威度与相关性混合排序 (Ranking V2)...")
                ranker = HybridRanker()
                results = ranker.rank(results, parsed.search_query, temperature=temp)
                
                
                # --- 自动补齐重试逻辑 ---
                if not results and search_params.get('source_preference') == 'gov':
                    st.write("⚠️ 官方渠道未找到，正在尝试扩大搜索范围...")
                    results = PolicySearcher.search(
                        search_params['refined_query'],
                        source_preference='all',
                        time_range=search_params.get('time_range')
                    )
                    results = ranker.rank(results, parsed.search_query, temperature=temp)
                
                # --- 终极兜底 ---
                if not results:
                    st.write("📡 正在尝试使用原始指令进行补全搜索...")
                    results = PolicySearcher.search(
                        parsed.search_query,
                        source_preference='all'
                    )
                    results = ranker.rank(results, parsed.search_query, temperature=temp)
                
                status.update(label="✅ 检索与排序完成！", state="complete", expanded=False)
            
            st.session_state.search_results = results
            st.session_state.is_result_from_cache = False
            st.session_state.current_raw_query = raw_query
            
            # 将结果存入缓存
            if results:
                st.session_state.search_cache[raw_query] = results
                msg = f"✅ 已为您精选 {len(results)} 条政策，并按投研权威度排序。"
            else:
                msg = f"❌ 未找到与“{raw_query}”相关的权威政策。建议尝试更简短的关键词。"
            
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
