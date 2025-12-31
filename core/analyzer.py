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
        # 初始化 LLM (使用 Qwen-Plus)
        self.llm = ChatOpenAI(
            api_key=Config.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=Config.MODEL_NAME, # qwen-plus
            temperature=0.1, # 保持低创造性，确保事实准确
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
        system_prompt = """你现在是【易方达基金(EFund)的资深指数基金经理】。
你的任务是阅读一篇政策文件，并为公司内部投研团队撰写一份专业的分析报告。

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
    "这里是第1条核心要点（需包含政策核心变化）",
    "这里是第2条监管导向判断",
    "这里是第3条对指数/行业的潜在影响",
    "这里是第4条投资建议（必须客观，偏配置或偏审慎）",
    "这里是第5条易方达产品策略应对",
    "这里是第6条主要风险提示"
  ],
  "docx_content": {{
    "摘要": ["段落1", "段落2"],
    "政策要点与变化": ["要点1", "要点2", "要点3"],
    "对指数与行业的影响": ["分析1", "分析2"],
    "对指数基金管理人的投资建议": ["建议1", "建议2"],
    "EFund_战略与行动建议": ["建议1", "建议2"],
    "引用区块": [
      {{
        "claim": "这里写你的分析结论",
        "evidence": "这里摘录原文的具体条款或段落",
        "source_url": "{url}"
      }}
    ]
  }}
}}

【合规红线 (必须遵守)】
1. 严禁使用“必然上涨”、“确定性收益”、“保本”等承诺性词汇。
2. 所有判断必须基于原文，不可凭空臆造。
3. 语气要专业、客观、理性，符合金融机构行文规范。
4. "chat_bullets" 数组严格控制在 6 条以内。
"""
        
        user_prompt = """
请分析以下政策文本：
================
{content}
================
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