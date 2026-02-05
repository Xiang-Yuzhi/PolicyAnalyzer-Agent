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
        content_source = "webpage"  # Debug: 记录内容来源
        
        # Step 1: 先尝试提取 PDF（政策原文通常在 PDF 中）
        if stage_callback: stage_callback("📄 正在检测 PDF 政策原文...", 10)
        pdf_result = pdf_extractor.extract_and_parse(url)
        
        raw_text = ""
        
        # 优先使用 PDF 内容（只要有实质内容）
        if pdf_result["pdf_content"] and len(pdf_result["pdf_content"]) > 500:
            print(f"✅ 检测到 PDF 政策原文，优先使用 PDF 内容 ({len(pdf_result['pdf_content'])} 字)")
            raw_text = pdf_result["pdf_content"]
            pdf_download_url = pdf_result["source_pdf_url"]
            content_source = "pdf"
        else:
            # Fallback: 抓取网页内容
            if stage_callback: stage_callback("📖 未找到 PDF，正在读取网页内容...", 20)
            raw_text = self.scrape_url(url)
            content_source = "webpage"
            # 记录 PDF 提取失败的诊断信息
            pdf_extraction_error = pdf_result.get("error", "未知原因")
            pdf_links_found = pdf_result.get("pdf_links", [])
            if pdf_links_found:
                pdf_download_url = pdf_links_found[0]["url"]
                print(f"⚠️ 发现 {len(pdf_links_found)} 个 PDF 链接但解析失败: {pdf_extraction_error}")
                print(f"   首个链接: {pdf_download_url[:80]}...")
            else:
                print(f"⚠️ 未在页面中发现任何 PDF 链接")
        
        if not raw_text:
            return {"error": "无法获取网页或PDF内容"}

        # Step 2: RAG 索引
        if stage_callback: stage_callback("🧠 正在构建语义索引 (RAG)...", 30)
        vector_store = rag_engine.create_index(raw_text)
        
        # Step 3: 原文检索
        if stage_callback: stage_callback("🔍 正在检索原文关键条款...", 50)
        
        # 优化检索 query：覆盖更多政策重点场景
        search_queries = [
            "新增条款和规定",           # 新监管类
            "修订内容和调整幅度",       # 修订类
            "数量限制、比例要求、金额上限",  # 数字细节
            "生效日期、过渡期、实施时间",   # 时间节点
            "违规处罚、法律责任、监管措施",  # 合规重点
            "公募基金、指数基金、ETF相关规定",  # 行业相关
            "信息披露、报告义务、备案要求"   # 合规义务
        ]
        original_citations = rag_engine.get_context_for_analysis(vector_store, search_queries, k=4)
        
        # 打印检索结果用于调试
        print(f"🔍 RAG 检索结果: {len(original_citations)} 字符")

        # Step 4: LLM 分析
        if stage_callback: stage_callback("📊 正在调用 Qwen-Max 进行投研深度分析...", 70)
        
        system_prompt = """你是【易方达基金首席政策分析师】，请严格基于政策原文撰写专业投研报告。

【金融行业简称对照表】(分析时需理解这些对等概念)
- 公募基金 = 公开募集证券投资基金
- 私募基金 = 私募投资基金
- ETF = 交易型开放式指数基金
- LOF = 上市开放式基金
- QDII = 合格境内机构投资者
- FOF = 基金中基金
- 指数基金 = 指数型证券投资基金
- 证券公司 = 证券经营机构
- 基金公司 = 基金管理公司/基金管理人
- 托管行 = 基金托管人/托管银行
- 减持新规 = 股份减持规则/减持管理办法

【政策分类与重点识别】
请先判断政策类型，再重点关注对应内容：

1. **修订类政策**：重点关注
   - 数量/比例的大幅调整（如从X%调整为Y%）
   - 新增或删除的关键条款
   - 适用范围的扩大或缩小

2. **行业规定类政策**：重点关注
   - 新增的行业规范和标准
   - 对现有规则的重大调整
   - 新的合规义务和报告要求

3. **新监管类政策**：重点关注
   - 监管规则是收紧还是放松
   - 新增的限制性规定
   - 新的处罚条款和法律责任

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
            
            # 注入原始采集快照 (Debug 用)
            result["debug_content_source"] = content_source  # "pdf" 或 "webpage"
            result["debug_raw_text"] = raw_text[:2000] + ("..." if len(raw_text) > 2000 else "")
            result["debug_citations"] = original_citations
            result["debug_pdf_links"] = pdf_result.get("pdf_links", [])
            result["debug_pdf_error"] = pdf_result.get("error", None)
                
            return result
            
        except Exception as e:
            print(f"❌ LLM 分析失败: {e}")
            return {"error": str(e)}