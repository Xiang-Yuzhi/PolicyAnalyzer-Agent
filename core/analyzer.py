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
        
        system_prompt = """你现在是【易方达基金(EFund)的资深指数基金经理和首席分析师】。
你的任务是基于提供的政策原文和原文摘录，撰写一份专业的深度分析报告。

【分析要求】
1. **专业性**：用语凝练、准确，符合首席分析师水平。
2. **多维度**：区分短期/长期影响，涵盖不同类型的指数。
3. **真实性**：必须引用原文关键条款，严禁虚构。

【报告结构要求 - 必须达标 2000 字】
1. 摘要 (300字)
2. 政策要点与变化 (300字)
3. **政策原文摘录 (300字)** - 请选出最关键的原文条款并进行针对性解读
4. 对指数及其行业的影响 (400字)
5. 对指数基金管理公司的建议 (400字)
6. 对易方达的战略行动建议 (300字)

【输出 JSON 格式】
{{
  "selected_policy": {{ "title": "{title}", "issuer": "{source}", "publish_date": "{date}", "url": "{url}" }},
  "chat_bullets": ["引用原文条款的总结1", "总结2", "总结3", "总结4", "总结5", "总结6"],
  "docx_content": {{
    "摘要": ["..."],
    "政策要点与变化": ["..."],
    "政策原文摘录": ["原文细节1", "原文细节2", "..."],
    "对指数及其行业的影响": ["..."],
    "对指数基金管理公司的建议": ["..."],
    "对易方达的战略行动建议": ["..."]
  }},
  "word_count_check": {{ "总计": 2000 }}
}}
"""
        
        user_prompt = """
请基于以下内容撰写 2000 字报告：

【关键原文摘录】
{citations}

【全文明细】
{content}
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