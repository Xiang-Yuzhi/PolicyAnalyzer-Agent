"""
Summary Agent: Generates a "Knowledge Snippet" (Featured Result) from search results.
"""

import json
import os
import re
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Ensure we can import config
try:
    from config import Config
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config

class SummaryAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name="qwen-max",
            openai_api_key=Config.DASHSCOPE_API_KEY,
            openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0.3
        )

    def generate_snippet(self, query: str, results: List[Dict]) -> str:
        """
        Generates a concise 'Knowledge Snippet' from the top search results.
        Returns a markdown string.
        """
        if not results:
            return ""

        # Use top 5 results for summary
        candidates = results[:5]
        context = ""
        for i, r in enumerate(candidates):
            context += f"Result {i+1}: {r.get('title')} | {r.get('snippet')}\n"

        prompt_text = """You are a professional financial research assistant. 
Based on the following search results for the user's query, provide a concise "Featured Snippet" summary (Knowledge Panel).

Goal: 
1. Directly answer the user's implicit question (e.g., if they query "减持新规", summarize what the new rule is).
2. Highlight the most authoritative source and the enactment date.
3. Keep it professional, objective, and under 150 words.

User Query: "{query}"

Search Results:
{context}

Output Requirements:
- Use clear bullet points if needed.
- Focus on the "Latest" and "Most Authoritative" information.
- Provide the summary in Chinese.
- Do not add conversational filler.
"""

        prompt = ChatPromptTemplate.from_messages([("user", prompt_text)])
        chain = prompt | self.llm | StrOutputParser()

        try:
            summary = chain.invoke({"query": query, "context": context})
            return summary.strip()
        except Exception as e:
            print(f"⚠️ SummaryAgent Error: {e}")
            return ""

if __name__ == "__main__":
    agent = SummaryAgent()
    test_results = [
        {"title": "证监会发布上市公司减持新规", "snippet": "证监会近日发布《上市公司股东减持股份管理办法》...", "source": "证监会"},
        {"title": "减持新规解读", "snippet": "专家认为新规严厉打击绕道减持...", "source": "证券时报"}
    ]
    print(agent.generate_snippet("减持新规", test_results))
