"""
Router Agent: 意图识别与路由层

负责解析用户自然语言输入，识别意图，并路由到对应的下游 Agent。
支持的意图类型：
- SEARCH: 新检索请求
- SELECT_AND_CONTINUE: 暂存政策 + 继续检索
- SELECT_ONLY: 仅暂存政策
- ANALYZE_SINGLE: 分析单个政策
- ANALYZE_COMBINED: 组合分析多个政策
- CLEAR_CACHE: 清空暂存
- CHAT: 普通对话/查询状态
"""

import json
import os
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config


class Intent(Enum):
    """用户意图枚举"""
    SEARCH = "SEARCH"                       # 新检索
    SELECT_AND_CONTINUE = "SELECT_AND_CONTINUE"  # 暂存 + 继续检索
    SELECT_ONLY = "SELECT_ONLY"             # 仅暂存
    ANALYZE_SINGLE = "ANALYZE_SINGLE"       # 单政策分析
    ANALYZE_COMBINED = "ANALYZE_COMBINED"   # 组合分析
    CLEAR_CACHE = "CLEAR_CACHE"             # 清空暂存
    CHAT = "CHAT"                           # 普通对话


@dataclass
class ParsedIntent:
    """解析后的意图结构"""
    intent: Intent
    search_query: Optional[str] = None          # 检索关键词
    select_indices: Optional[List[int]] = None  # 要暂存的政策序号 (1-based)
    analysis_direction: Optional[str] = None    # 分析方向/具体指令 (仅分析意图时填写)
    message: Optional[str] = None               # 给用户的回复消息


class RouterAgent:
    """
    路由 Agent：解析用户输入，识别意图，提取参数
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=Config.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-flash",  # 切换为 qwen-flash 以获得更快的响应速度
            temperature=0.1,
            model_kwargs={
                "response_format": {"type": "json_object"}
            }
        )
        
        self.system_prompt = """你是一个智能意图识别助手。你的任务是分析用户输入，判断用户意图，并提取关键参数。

【意图类型说明】
1. SEARCH - 用户想要检索新的政策
   示例: "帮我找减持新规", "搜索2024年分红政策", "查一下证监会最新规定"

2. SELECT_AND_CONTINUE - 用户想要暂存某个/某些政策，同时继续检索新的政策
   示例: "第一个不错，存着，再帮我找分红政策", "把上面第2个存起来，继续搜索科创板规则"
   
3. SELECT_ONLY - 用户只想暂存政策，不做其他操作
   示例: "把第二个存起来", "暂存第1和第3个", "收藏一下第一条"

4. ANALYZE_SINGLE - 用户想要分析当前选中的单个政策
   示例: "分析这个政策", "解读一下这份文件", "帮我分析第一个"

5. ANALYZE_COMBINED - 用户想要综合分析暂存池中的多个政策
   示例: "综合分析我存的这些政策", "对比分析暂存的文件", "把收藏的政策一起分析"

6. CLEAR_CACHE - 用户想要清空暂存池
   示例: "清空暂存", "删除收藏的政策", "重新开始"

7. CHAT - 普通对话，不属于以上任何类型
   示例: "你好", "暂存了几个政策", "当前状态"

【输出格式】
必须输出严格的 JSON 格式：
{
  "intent": "SEARCH|SELECT_AND_CONTINUE|SELECT_ONLY|ANALYZE_SINGLE|ANALYZE_COMBINED|CLEAR_CACHE|CHAT",
  "search_query": "提取的检索关键词（仅 SEARCH 和 SELECT_AND_CONTINUE 时填写）",
  "select_indices": [1, 2, 3],  // 要暂存的政策序号（1-based）
  "analysis_direction": "用户提到的分析侧重点或具体指令（如：'对中小企业的影响'、'合规合规要求'等，仅分析意图时填写）",
  "message": "给用户的简短回复或确认信息"
}

【注意事项】
1. select_indices 使用 1-based 索引（用户说"第一个"对应 1）
2. 如果用户说"上面的"、"刚才那个"但没指定具体序号，默认为 [1]
3. search_query 应该提取用户真正想搜索的关键词，去掉"帮我找"等无关词；同时注意潜在的时间偏好，例如“新规”、“最近”之类的表述
4. analysis_direction 应该保留用户请求分析时的具体侧重点，如果用户只是通用的"分析"，填 null
5. message 应该简短、友好，确认用户的操作意图
"""

    def parse(self, user_input: str, context: Optional[Dict] = None) -> ParsedIntent:
        """
        解析用户输入，返回结构化的意图
        
        Args:
            user_input: 用户的自然语言输入
            context: 上下文信息，如当前显示的搜索结果、暂存池状态等
        
        Returns:
            ParsedIntent 对象
        """
        context_str = ""
        if context:
            if context.get("search_results"):
                context_str += f"当前显示的搜索结果数量: {len(context['search_results'])} 条\n"
            if context.get("cached_policies"):
                context_str += f"暂存池中的政策数量: {len(context['cached_policies'])} 条\n"
        
        user_prompt = f"""请分析以下用户输入，识别意图并提取参数：

【上下文信息】
{context_str if context_str else "无"}

【用户输入】
{user_input}

请输出 JSON 格式的分析结果。"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", user_prompt)
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = chain.invoke({
                "context_str": context_str if context_str else "无",
                "user_input": user_input
            })
            result = json.loads(response)
            
            return ParsedIntent(
                intent=Intent(result.get("intent", "CHAT")),
                search_query=result.get("search_query"),
                select_indices=result.get("select_indices"),
                analysis_direction=result.get("analysis_direction"),
                message=result.get("message", "")
            )
        except Exception as e:
            print(f"❌ 意图解析失败: {e}")
            # 降级处理：假设是搜索意图
            return ParsedIntent(
                intent=Intent.SEARCH,
                search_query=user_input,
                message="正在为您检索..."
            )

    def extract_keywords(self, query: str) -> Dict[str, Any]:
        """
        从自然语言查询中提取结构化的搜索参数，并推理用户可能寻找的官方文件名称
        """
        extract_prompt = """你是一名资深政策研究员。分析用户的模糊搜索需求，精准推理其可能寻找的官方政策文件。

用户输入: {query}

【你的任务】
1. 理解用户真实意图，提取核心政策领域关键词。锁定“政策原文”、“管理办法”、“指导意见”、“通知”、“指引”、“实施细则”等监管规章文件。
2. 推理最可能的官方文件全称。
3. 生成优化后的、**简洁且高针对性**的搜索引擎查询词（refined_query）。
   - **核心约束**：必须排斥“招募说明书”、“招募书”、“公司公告”、“业绩报告”、“年度报告”、“季度报告”、“招股”等企业信息披露文件。
   - **技巧**：建议在查询词后面加上“管理办法”或“指引”等后缀来收窄范围。
   - **注意**：不要堆砌冗长的解释，只需包含：[文件名或核心词] + [类型后缀] + [年份(如有)]。

输出 JSON 格式：
{{
  "inferred_official_title": "推理出的官方文件全称"，否则为检索来源标题,
  "keywords": ["核心术语1", "核心术语2"],
  "time_range": "时间范围",
  "source_preference": "gov 或 all",
  "refined_query": "简洁的搜索词（如：基金从业人员管理办法 2024）"
}}"""

        prompt = ChatPromptTemplate.from_messages([
            ("user", extract_prompt)
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = chain.invoke({"query": query})
            result = json.loads(response)
            
            # 优化：不再盲目覆盖，而是进行关键词混合
            # 这样既能搜到精准文件名，也能兼容模糊关键词
            inferred = result.get("inferred_official_title")
            keywords = " ".join(result.get("keywords", []))
            
            if inferred and inferred != "null":
                # 混合搜索：官方名 + 核心关键词
                result["refined_query"] = f"{inferred} {keywords}".strip()
            
            return result
        except Exception as e:
            print(f"❌ 关键词提取失败: {e}")
            return {
                "keywords": [query],
                "time_range": None,
                "source_preference": "all",
                "refined_query": query
            }


# 测试代码
if __name__ == "__main__":
    router = RouterAgent()
    
    test_cases = [
        "帮我找2024年的减持新规",
        "第一个不错，存着，再帮我找分红政策",
        "把第二个和第三个存起来",
        "综合分析我存的这些政策",
        "清空暂存",
        "你好"
    ]
    
    for case in test_cases:
        print(f"\n输入: {case}")
        result = router.parse(case)
        print(f"意图: {result.intent.value}")
        print(f"检索词: {result.search_query}")
        print(f"选择序号: {result.select_indices}")
        print(f"回复: {result.message}")
