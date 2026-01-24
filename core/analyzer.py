import os
import json
from datetime import datetime
from typing import Dict, Any

# --- 修改引用开始 ---
from langchain_community.document_loaders import WebBaseLoader
from langchain_openai import ChatOpenAI
# [关键修改] 改用 langchain_core，这是最稳健的写法
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
# --- 修改引用结束 ---

# 引入配置
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

class PolicyAnalyzer:
    """
    核心分析引擎：
    1. 抓取 URL 内容
    2. 调用 LLM 进行角色扮演分析
    3. 输出结构化 JSON
    """

    def __init__(self):
        # 初始化 LLM (使用 Qwen-Max 以获得更好的长文本生成质量)
        self.llm = ChatOpenAI(
            api_key=Config.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=Config.MODEL_NAME, # qwen-plus 或 qwen-max
            temperature=0.3, # 提高至 0.3，在保持准确性的同时增加分析的深度和多样性
            model_kwargs={
                "response_format": {"type": "json_object"} # 强制 JSON 模式
            }
        )

    def scrape_url(self, url: str) -> str:
        """简单的网页抓取，实际生产可能需要更强的 Scraper 应对反爬"""
        print(f"🕷️ 正在读取网页内容: {url} ...")
        try:
            loader = WebBaseLoader(url)
            # 设置超时
            loader.requests_kwargs = {'verify': False, 'timeout': 10}
            docs = loader.load()
            content = "\n\n".join([d.page_content for d in docs])
            # 简单的截断，防止爆 Token (保留前 15000 字符)
            return content[:15000]
        except Exception as e:
            print(f"❌ 网页抓取失败: {e}")
            return ""

    def analyze(self, policy_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        核心分析逻辑
        policy_data: 包含 title, url, source, date 等
        """
        url = policy_data.get('link')
        raw_text = self.scrape_url(url)
        
        if not raw_text:
            return {"error": "无法获取网页内容"}

        print("🧠 正在进行深度分析 (Qwen-Max)...")

        # --- Prompt 设计 (核心资产) ---
        system_prompt = """你现在是【易方达基金(EFund)的资深指数基金经理和首席分析师】。
你的任务是阅读一篇政策文件，并为公司内部投研团队撰写一份专业的深度分析报告。


【报告结构与字数要求 - 严格遵守】
⚠️ 重要：报告总字数必须达到 2000 字（不含 chat_bullets），这是硬性要求！

1. 摘要 - 严格 300 字
   - 精炼、简洁，用语专业
   - 从正文中提炼核心内容进行总结
   - 需涵盖政策背景、核心变化、主要影响
   - 分为2个段落，每段约150字
   - ⚠️ 必须写满 300 字，不得少于 280 字

2. 政策要点与变化 - 严格 300 字
   - 用语凝练专业
   - 重点总结政策对涉及主体行为动作的规定和引导
   - 包括但不限于：合规、监管、机构调整、行业动态、国家投资关注方向
   - 以流畅连贯的成段文字进行阐述
   - 分为3个段落，每段约100字
   - ⚠️ 必须写满 300 字，不得少于 280 字

3. 对指数及其行业的影响 - 严格 500 字
   - 用语凝练专业
   - 重点把握或科学性地联想与指数行业、指数基金行业、指数投资、指数产品管理运作等相关主题的牵连内容
   - 从以下视角进行影响分析：
     * 短期影响（3-6个月）vs 长期影响（1-3年）
     * 细分指数类型（宽基指数、行业指数、主题指数、Smart Beta等）
     * 市场结构性变化
   - 以流畅连贯的成段文字进行阐述
   - 分为3个段落：短期影响约200字、长期影响约200字、细分领域影响约100字
   - ⚠️ 必须写满 500 字，不得少于 480 字

4. 对指数基金管理公司的建议 - 严格 500 字
   - 用语凝练专业
   - 从总体上捕捉并分析基金公司可以学习、借鉴、参考、优化工作流程、创新产品的大体方向
   - 从以下视角提供建议：
     * 短期应对措施 vs 长期战略布局
     * 细分指数领域的机会与挑战
     * 细分指数产品类型的创新方向
     * 风险管理与合规优化
   - 以流畅连贯的成段文字进行阐述
   - 分为3个段落：短期应对约200字、长期战略约200字、创新方向约100字
   - ⚠️ 必须写满 500 字，不得少于 480 字

5. 对易方达的战略行动建议 - 严格 400 字
   - 用语凝练专业
   - 站在易方达公司的视角，分析针对该政策需要在何种程度上、何种方向上、何种具体措施上进行响应
   - 从以下视角提供建议：
     * 短期行动计划（3-6个月）
     * 中长期战略调整（1-3年）
     * 细分指数领域的布局重点
     * 细分指数产品类型的开发优先级
     * 团队能力建设与资源配置
   - 以流畅连贯的成段文字进行阐述
   - 分为3个段落：短期行动约150字、中长期战略约150字、资源配置约100字
   - ⚠️ 必须写满 400 字，不得少于 380 字

⚠️ 字数检查要求：
- 总字数必须在 1950-2050 字之间
- 每个章节的字数必须达到规定字数的 95% 以上
- 如果字数不足，请扩充内容深度和分析维度，而非简单重复

【输出格式要求】
必须严格输出标准的 JSON 格式，不要包含 Markdown 代码块标记（如 ```json），直接输出 JSON 字符串。
JSON 结构如下：
{{
  "selected_policy": {{
    "title": "{title}",
    "issuer": "{source}",
    "publish_date": "{date}",
    "url": "{url}"
  }},
  "chat_bullets": [
    "政策核心变化概述内容。具体影响分析。",
    "监管导向判断内容。政策意图解读。",
    "对指数/行业的关键影响分析。市场影响预测。",
    "对基金公司的核心建议内容。具体应对措施。",
    "易方达产品策略应对方案。战略调整建议。",
    "主要风险提示内容。注意事项说明。"
  ],
  "docx_content": {{
    "摘要": ["第一段（约150字）", "第二段（约150字）"],
    "政策要点与变化": ["第一段（约100字）", "第二段（约100字）", "第三段（约100字）"],
    "对指数及其行业的影响": ["短期影响分析段落（约200字）", "长期影响分析段落（约200字）", "细分领域影响段落（约100字）"],
    "对指数基金管理公司的建议": ["短期应对建议段落（约200字）", "长期战略建议段落（约200字）", "创新方向建议段落（约100字）"],
    "对易方达的战略行动建议": ["短期行动计划段落（约150字）", "中长期战略段落（约150字）", "资源配置建议段落（约100字）"]
  }},
  "word_count_check": {{
    "摘要": 300,
    "政策要点与变化": 300,
    "对指数及其行业的影响": 500,
    "对指数基金管理公司的建议": 500,
    "对易方达的战略行动建议": 400,
    "总计": 2000
  }}
}}

【写作风格要求】
1. **专业性**：以资深行研人员和首席分析师的身份撰写
2. **语言风格**：
   - 用语凝练、专业、准确
   - 避免口语化表达
   - 使用行业术语和专业概念
   - 逻辑严密，论证充分
3. **段落结构**：
   - 每段需有明确的中心论点
   - 论据充分，引用原文支撑
   - 段落之间逻辑连贯，过渡自然
4. **分析深度**：
   - 不仅描述"是什么"，更要分析"为什么"和"怎么办"
   - 提供前瞻性判断和可操作建议
   - 结合宏观经济、行业趋势、市场环境进行综合分析

【合规红线 - 必须遵守】
1. 严禁使用"必然上涨"、"确定性收益"、"保本"等承诺性词汇
2. 所有判断必须基于原文，不可凭空臆造
3. 语气要专业、客观、理性，符合金融机构行文规范
4. "chat_bullets" 数组严格控制在 6 条，每条包含2句话（约60-80字）
5. ⚠️ 字数要求是硬性指标，必须严格达标：
   - 总字数必须在 1950-2050 字之间
   - 摘要不少于 280 字
   - 政策要点不少于 280 字
   - 影响分析不少于 480 字
   - 管理公司建议不少于 480 字
   - 易方达建议不少于 380 字
"""
        
        user_prompt = """
请分析以下政策文本，并严格按照上述要求撰写 2000 字深度分析报告：
================
{content}
================

【特别提醒】
⚠️ 字数是硬性要求，必须严格达标！
1. 各章节字数要求（必须达到）：
   - 摘要：300字（不少于280字）
   - 政策要点：300字（不少于280字）
   - 影响分析：500字（不少于480字）
   - 管理公司建议：500字（不少于480字）
   - 易方达建议：400字（不少于380字）
   - 总计：2000字（1950-2050字可接受）

2. 分析需从"短期/长期"、"细分指数类型"等多维度展开
3. 语言需专业、凝练、流畅，符合首席分析师的写作水平
4. 在 word_count_check 字段中标注各章节实际字数
5. chat_bullets 中每条需包含2句话，约60-80字

⚠️ 如果字数不足，请通过以下方式扩充：
- 增加分析深度和论证细节
- 补充具体案例和数据支撑
- 扩展多维度分析视角
- 提供更具体的操作建议
- 绝不允许简单重复或凑字数
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])

        # 注入变量
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response_str = chain.invoke({
                "title": policy_data.get('title'),
                "source": policy_data.get('source'),
                "date": policy_data.get('date'),
                "url": url,
                "content": raw_text
            })
            
            # 解析 JSON
            return json.loads(response_str)
            
        except Exception as e:
            print(f"❌ LLM 分析或 JSON 解析失败: {e}")
            # 返回一个空的结构以防前端崩溃
            return {"error": str(e)}