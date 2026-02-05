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
from .pdf_extractor import pdf_extractor

class PolicyAnalyzer:
    """
    核心分析引擎 (RAG 增强版 + PDF 支持)：
    1. 抓取 URL 内容
    2. 检测并提取嵌入的 PDF 文件
    3. 使用 RAG 引擎进行语义切片与索引
    4. 检索关键词原文依据
    5. 调用 LLM 进行深度投研分析
    6. 输出结构化 JSON (含 PDF 下载链接)
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=Config.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=Config.MODEL_NAME,
            temperature=0.1,  # 降低温度以减少幻觉风险
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
        核心分析逻辑 (支持 RAG、PDF解析 和 阶段回调)
        """
        url = policy_data.get('link')
        pdf_download_url = None
        
        # Step 1: 抓取网页
        if stage_callback: stage_callback("📖 正在阅读政策网页...", 10)
        raw_text = self.scrape_url(url)
        
        # Step 1.5: 尝试提取 PDF (如果网页内容过短或包含 PDF)
        if stage_callback: stage_callback("📄 正在检测 PDF 附件...", 20)
        pdf_result = pdf_extractor.extract_and_parse(url)
        
        if pdf_result["pdf_content"] and len(pdf_result["pdf_content"]) > len(raw_text):
            print(f"📄 检测到 PDF 内容更丰富，切换至 PDF 解析模式")
            raw_text = pdf_result["pdf_content"]
            pdf_download_url = pdf_result["source_pdf_url"]
        elif pdf_result["pdf_links"]:
            # 即使没用 PDF 内容，也记录下载链接
            pdf_download_url = pdf_result["pdf_links"][0]["url"]
        
        if not raw_text:
            return {"error": "无法获取网页或PDF内容"}

        # Step 2: RAG 索引
        if stage_callback: stage_callback("🧠 正在构建语义索引 (RAG)...", 30)
        vector_store = rag_engine.create_index(raw_text)
        
        # Step 3: 原文检索
        if stage_callback: stage_callback("🔍 正在检索原文关键条款...", 50)
        search_queries = [
            "核心监管要求和限制条件",
            "合规义务与法律责任",
            "生效日期与过渡期安排",
            "对指数基金及管理人的相关规定",
            "具体数量限制和比例要求",  # 新增：锁定数字细节
            "违规处罚和法律责任条款"   # 新增：锁定关键条款
        ]
        original_citations = rag_engine.get_context_for_analysis(vector_store, search_queries, k=4)  # 增加检索数量

        # Step 4: LLM 分析
        if stage_callback: stage_callback("📊 正在调用 Qwen-Max 进行投研深度分析...", 70)
        
        system_prompt = """你是【易方达基金首席政策分析师】，请严格基于政策原文撰写专业投研报告。

【核心要求】
1. **严禁虚构**：所有数字、日期、百分比、条款编号必须直接来自原文，不可推测或编造
2. **原文锚定**：每个核心观点必须标注原文出处，如"根据第X条..."或直接引用原文
3. **不确定性标注**：如原文未明确某信息，需明确注明"原文未明确说明"
4. **区分短期/长期影响**

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

⚠️ 【幻觉防范机制 - 务必严格遵守】：
- 如果原文中没有具体数字，严禁编造任何数字（如百分比、金额、天数、比例）
- 如果无法确认某条款的具体内容，请明确写出"原文未明确规定"或"需进一步确认"
- 每个"chat_bullets"必须附带一个可验证的原文片段作为依据
- 禁止使用"据悉"、"预计"、"可能会"等推测性表述，除非原文如此表述
- "原文摘录"部分必须是政策文件中的真实原句，不可改写或总结

📝 输出要求：
- chat_bullets 每条需简洁有力，约30-50字，必须包含原文依据
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
            result = json.loads(response_str)
            
            # 注入 PDF 下载链接
            if pdf_download_url:
                result["pdf_download_url"] = pdf_download_url
                
            return result
            
        except Exception as e:
            print(f"❌ LLM 分析失败: {e}")
            return {"error": str(e)}