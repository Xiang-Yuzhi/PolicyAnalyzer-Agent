import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List

from langchain_community.document_loaders import WebBaseLoader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 引入核心模块
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from .rag_engine import rag_engine

class PolicyAnalyzer:
    """
    核心分析引擎 (RAG 增强版)：
    1. 抓取 URL 内容
    2. 使用 RAG 引擎进行语义切片与索引
    3. 检索关键词原文依据
    4. 调用 LLM 进行深度投研分析
    5. 输出结构化 JSON
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=Config.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=Config.MODEL_NAME,
            temperature=0.3,
            model_kwargs={
                "response_format": {"type": "json_object"}
            }
        )

    def scrape_url(self, url: str) -> str:
        """网页抓取"""
        print(f"🕷️ 正在读取网页内容: {url} ...")
        try:
            loader = WebBaseLoader(url)
            loader.requests_kwargs = {'verify': False, 'timeout': 15}
            docs = loader.load()
            content = "\n\n".join([d.page_content for d in docs])
            return content[:25000] # 扩大抓取范围，交给 RAG 处理
        except Exception as e:
            print(f"❌ 网页抓取失败: {e}")
            return ""

    def analyze(self, policy_data: Dict[str, Any], stage_callback=None) -> Dict[str, Any]:
        """
        核心分析逻辑 (支持 RAG 和 阶段回调)
        """
        url = policy_data.get('link')
        
        # Step 1: 抓取
        if stage_callback: stage_callback("📖 正在阅读政策全文...", 10)
        raw_text = self.scrape_url(url)
        if not raw_text:
            return {"error": "无法获取网页内容"}

        # Step 2: RAG 索引
        if stage_callback: stage_callback("🧠 正在构建语义索引 (RAG)...", 30)
        vector_store = rag_engine.create_index(raw_text)
        
        # Step 3: 原文检索
        if stage_callback: stage_callback("🔍 正在检索原文关键条款...", 50)
        search_queries = [
            "核心监管要求和限制条件",
            "合规义务与法律责任",
            "生效日期与过渡期安排",
            "对指数基金及管理人的相关规定"
        ]
        original_citations = rag_engine.get_context_for_analysis(vector_store, search_queries)

        # Step 4: LLM 分析
        if stage_callback: stage_callback("📊 正在调用 Qwen-Max 进行投研深度分析...", 70)
        
        system_prompt = """你是【易方达基金首席政策分析师】，请基于政策原文撰写专业投研报告。

【核心要求】专业凝练、引用原文、区分短期/长期影响

【报告结构 (共约1800字)】
1. **摘要** (250字): 政策背景、核心变化、主要影响
2. **政策要点** (250字): 监管规定、合规要求、关键条款
3. **原文摘录** (200字): 选取最关键的2-3条原文并简要解读
4. **市场影响** (400字): 短期冲击(3-6月) + 长期趋势(1-3年)
5. **易方达行动建议** (400字): 产品策略、业务调整、资源配置
6. **风险提示** (100字): 需关注的不确定性

【输出JSON格式】
{{
  "selected_policy": {{"title": "{title}", "issuer": "{source}", "publish_date": "{date}", "url": "{url}"}},
  "chat_bullets": ["核心观点1(含原文引用)", "核心观点2", "核心观点3", "核心观点4", "核心观点5", "核心观点6"],
  "docx_content": {{
    "摘要": ["段落1", "段落2"],
    "政策要点": ["要点1", "要点2", "要点3"],
    "原文摘录": ["原文1及解读", "原文2及解读"],
    "市场影响": ["短期影响", "长期影响"],
    "易方达行动建议": ["产品策略", "业务调整建议"],
    "风险提示": ["风险点"]
  }}
}}
"""
        
        user_prompt = """请基于以下政策内容撰写约1800字的专业分析报告。

【RAG检索到的关键原文】(请优先引用这些条款)
{citations}

【政策全文参考】
{content}

⚠️ 注意事项：
- chat_bullets 每条需简洁有力，约30-50字，需包含原文依据
- 市场影响需区分短期(3-6月)和长期(1-3年)
- 易方达建议需具体可操作，涵盖产品、业务、资源三方面
- 严格输出JSON格式，勿添加markdown标记
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])

        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response_str = chain.invoke({
                "title": policy_data.get('title'),
                "source": policy_data.get('source'),
                "date": policy_data.get('date'),
                "url": url,
                "citations": original_citations,
                "content": raw_text[:12000] # 发送部分全文作为背景
            })
            
            if stage_callback: stage_callback("📝 正在整理输出最终报告...", 90)
            return json.loads(response_str)
            
        except Exception as e:
            print(f"❌ LLM 分析失败: {e}")
            return {"error": str(e)}