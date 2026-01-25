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
        
        self.system_prompt = """你是【易方达基金(EFund)的首席政策分析师】。
你的任务是对多份政策文件进行综合对比分析，为投研团队提供政策趋势研判报告。

【分析框架】

1. 政策共同导向（200字）
   - 这些政策的共同监管意图是什么？
   - 整体上是收紧还是放松？
   - 政策组合传递的核心信号

2. 矛盾与互补关系（200字）
   - 各政策之间是否存在矛盾或张力？
   - 如何相互补充形成完整的监管框架？
   - 政策间的优先级和适用边界

3. 综合市场影响（300字）
   - 对资本市场的短期冲击
   - 对相关行业的中长期影响
   - 对投资者行为的引导效应
   - 对市场结构和流动性的影响

4. 政策趋势研判（200字）
   - 政策演变的可能方向
   - 后续可能出台的配套措施
   - 政策周期判断

5. 投资策略建议（300字）
   - 应关注的指数类型
   - 应规避的风险领域
   - 建议的资产配置调整
   - 时间窗口把握

【输出格式】
{
  "policies_analyzed": ["政策A标题", "政策B标题", ...],
  "analysis_date": "2024-XX-XX",
  "common_direction": {
    "summary": "共同导向概述",
    "regulatory_stance": "收紧/放松/中性",
    "core_signal": "核心信号"
  },
  "relationships": {
    "contradictions": ["矛盾点1", "矛盾点2"],
    "complementary": ["互补点1", "互补点2"]
  },
  "market_impact": {
    "short_term": "短期影响分析",
    "long_term": "长期影响分析",
    "sectors_affected": ["受影响行业1", "受影响行业2"]
  },
  "trend_forecast": {
    "direction": "政策走向判断",
    "next_steps": ["可能的后续政策1", "可能的后续政策2"]
  },
  "investment_advice": {
    "focus_areas": ["关注领域1", "关注领域2"],
    "avoid_areas": ["规避领域1", "规避领域2"],
    "timing": "时机建议"
  },
  "executive_summary": "200字执行摘要，供高管快速阅读"
}

【合规红线】
1. 严禁使用"必然上涨"、"确定性收益"等承诺性词汇
2. 所有判断必须基于政策原文，不可凭空臆造
3. 语气要专业、客观、理性
"""
    
    def analyze(self, policies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        对多个政策进行组合分析
        
        Args:
            policies: 政策列表，每个政策包含 title, url, source, date, summary 等
        
        Returns:
            结构化的组合分析结果
        """
        if not policies:
            return {"error": "没有可分析的政策"}
        
        if len(policies) == 1:
            return {"error": "组合分析需要至少2个政策，请暂存更多政策后再试"}
        
        # 构建政策摘要列表
        policy_summaries = []
        for i, p in enumerate(policies, 1):
            summary = f"""
【政策{i}】
标题: {p.get('title', '未知')}
发布机构: {p.get('source', '未知')}
发布日期: {p.get('date', '未知')}
摘要: {p.get('summary', p.get('snippet', '无摘要'))}
"""
            policy_summaries.append(summary)
        
        user_prompt = f"""请对以下 {len(policies)} 份政策进行综合对比分析：

{"".join(policy_summaries)}

请严格按照上述分析框架和 JSON 格式输出分析报告。
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", user_prompt)
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = chain.invoke({})
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
