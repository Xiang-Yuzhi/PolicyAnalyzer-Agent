import requests
import json
from typing import List, Dict
import sys
import os

# 确保能导入同级模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ranker import PolicyRanker

try:
    from config import Config
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config

class PolicySearcher:
    """
    负责联网检索并调用 Ranker 进行排序 (适配 SerpApi 版本)
    """
    
    @staticmethod
    def search(query: str, num_results: int = 10) -> List[Dict]:
        """
        执行搜索 -> 清洗 -> 排序 -> 返回 Top N
        """
        print(f"🔍 [SerpApi] 正在检索关键词: {query} ...")
        
        # SerpApi 的标准端点
        url = "https://serpapi.com/search"
        
        # SerpApi 使用 GET 请求参数
        params = {
            "engine": "google",
            "q": query,
            "api_key": Config.SERPER_API_KEY, # 复用配置里的变量名
            "gl": "cn",       # 地理位置：中国
            "hl": "zh-cn",    # 语言：简体中文
            "num": 20         # 多抓一些供 Ranker 筛选
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"❌ 搜索 API 调用失败: {e}")
            return []

        # 1. 提取原始结果 (SerpApi 的 key 是 'organic_results')
        raw_results = data.get("organic_results", [])
        
        # 2. 数据标准化 (Standardize)
        candidates = []
        for item in raw_results:
            # 提取 Source，SerpApi 有时放在 source 字段，有时需解析
            source_info = item.get("source", "")
            if not source_info and "displayed_link" in item:
                source_info = item["displayed_link"]

            candidates.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                # SerpApi 的日期字段可能叫 'date'
                "date": item.get("date", ""),
                "source": source_info
            })

        print(f"📥 [SerpApi] 原始抓取: {len(candidates)} 条")

        # 3. 核心步骤：调用 Ranker 进行权威性排序
        sorted_results = PolicyRanker.sort_policies(candidates, query=query)
        
        # 4. 截取 Top N
        final_results = sorted_results[:num_results]
        
        return final_results