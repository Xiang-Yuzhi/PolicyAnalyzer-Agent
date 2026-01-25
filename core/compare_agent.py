"""
Compare Agent: 多政策组合分析

负责对用户暂存的多个政策进行综合对比分析，输出：
1. 政策共同导向
2. 矛盾与互补关系
3. 综合市场影响
4. 政策趋势研判
5. 投资策略建议
"""

import json
import os
import sys
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config


class CompareAgent:
    """
    组合分析 Agent：对多个政策进行综合对比分析
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
        
        self.system_prompt = """你是【易方达基金(EFund)首席政策分析师】。
你的任务是对多份暂存的政策文件进行纵深对比分析，撰写一份不少于 2000 字的专业投研报告。

【核心要求】
1. **深度叙述**：严禁使用点状清单（Bullet Points）。请采用成段的叙述性文字，逻辑严密，语气严谨规范。
2. **权威性**：必须深入引用各政策原文关键条款作为支撑。
3. **专业广度**：涵盖监管导向、理论深度、市场冲击、行业变迁及战略应对。

【报告结构要求】
1. 政策共同导向 (约400字): 深度解读政策组合传递出的底层监管逻辑与核心信号。
2. 政策要点对比分析 (约400字): 对比解析各文件的核心条款，深度剖析其关联与差异。
3. 政策原文与深度解读 (约400字): 选取最具指导意义的原文核心表述，进行逐条专业分析。
4. 市场影响与趋势研判 (约400字): 研判政策对资本市场、指数表现及相关行业的深层影响及演进趋势。
5. 易方达战略行动建议 (约400字): 站在基金公司战略高度，针对性地给出业务发展、产品策略及风控建议。

【输出 JSON 格式】
{{
  "policies_analyzed": ["标题1", "标题2", ...],
  "executive_summary": "200字精炼摘要",
  "chat_bullets": ["核心深度观点1", "核心深度观点2", "核心深度观点3"],
  "docx_content": {{
    "政策共同导向": ["叙述段落1...", "叙述段落2..."],
    "政策要点对比分析": ["叙述段落1...", "叙述段落2..."],
    "政策原文与深度解读": ["叙述段落1...", "叙述段落2..."],
    "市场影响与趋势研判": ["叙述段落1...", "叙述段落2..."],
    "易方达战略行动建议": ["叙述段落1...", "叙述段落2..."]
  }}
}}

【禁令】严禁使用点状列表。文字要求具备深度，逻辑连贯，语气符合专业研报规范。
"""
    
    def analyze(self, policies: List[Dict[str, Any]], stage_callback=None, user_direction=None) -> Dict[str, Any]:
        """
        对多个政策进行组合分析
        """
        if not policies:
            return {"error": "没有可分析的 政策"}
        
        if len(policies) < 2:
            return {"error": "组合分析需要至少2个政策，请先暂存更多政策后再试"}
        
        if stage_callback: stage_callback("📂 正在提取并交叉比对政策内容...", 20)
        
        # 构建政策摘要列表
        policy_summaries = []
        for i, p in enumerate(policies, 1):
            summary = f"""
【政策{i}】
标题: {p.get('title', '未知')}
发布机构: {p.get('source', '未知')}
发布日期: {p.get('date', '未知')}
内容摘要: {p.get('summary', p.get('snippet', '无摘要'))}
"""
            policy_summaries.append(summary)
        
        if stage_callback: stage_callback("🧠 正在生成 2000 字深度研判报告...", 50)
        
        direction_clause = f"\n特别侧重与侧点：{user_direction}\n" if user_direction else ""
        
        user_prompt = f"""请对以下 {len(policies)} 份政策进行综合对比分析，撰写不少于2000字的专业研报：
{direction_clause}
{"".join(policy_summaries)}

请注意：成段撰写，严禁点状清单，引用原文，字数务必充足。
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", user_prompt)
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = chain.invoke({})
            if stage_callback: stage_callback("📝 正在整理文档格式...", 90)
            result = json.loads(response)
            result["_policy_count"] = len(policies)
            return result
        except Exception as e:
            print(f"❌ 组合分析失败: {e}")
            return {"error": str(e)}
    
    def generate_comparison_table(self, policies: List[Dict]) -> str:
        """
        生成政策对比表格（Markdown 格式）
        """
        if not policies:
            return "暂无政策"
        
        header = "| 政策名称 | 发布机构 | 发布时间 | 核心内容 |\n"
        header += "|----------|----------|----------|----------|\n"
        
        rows = []
        for p in policies:
            title = p.get('title', '未知')[:20] + "..." if len(p.get('title', '')) > 20 else p.get('title', '未知')
            source = p.get('source', '未知')
            date = p.get('date', '未知')
            snippet = p.get('snippet', '')[:30] + "..." if len(p.get('snippet', '')) > 30 else p.get('snippet', '')
            rows.append(f"| {title} | {source} | {date} | {snippet} |")
        
        return header + "\n".join(rows)


# 测试代码
if __name__ == "__main__":
    agent = CompareAgent()
    
    test_policies = [
        {
            "title": "上市公司股东减持股份管理暂行办法",
            "source": "证监会",
            "date": "2024-05-24",
            "summary": "规范大股东减持行为，设置预披露要求和减持比例限制"
        },
        {
            "title": "上市公司现金分红指引",
            "source": "证监会",
            "date": "2024-04-01",
            "summary": "鼓励上市公司增加现金分红，提高投资者回报"
        }
    ]
    
    print("正在进行组合分析...")
    result = agent.analyze(test_policies)
    print(json.dumps(result, ensure_ascii=False, indent=2))
