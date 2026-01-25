import requests
import json
from typing import List, Dict, Optional
import sys
import os

# 确保能导入同级模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config import Config
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config

class PolicySearcher:
    """
    负责联网检索 (Stage 1: Recall)
    """
    
    @staticmethod
    def search(query: str, num_results: int = 20, 
               source_preference: str = "all", 
               time_range: Optional[str] = None) -> List[Dict]:
        """
        执行搜索 -> 数据清洗 -> 返回候选列表
        """
        refined_query = query
        
        # 处理官方来源偏好
        if source_preference == "gov":
            refined_query += " site:.gov.cn"
        
        # 处理时间范围
        if time_range:
            refined_query += f" {time_range}"
            
        print(f"🔍 [SerpApi] 正在检索关键词: {refined_query} ...")
        
        url = "https://serpapi.com/search"
        params = {
            "engine": "google",
            "q": refined_query,
            "api_key": Config.SERPER_API_KEY,
            "gl": "cn",
            "hl": "zh-cn",
            "num": 40 if source_preference == "all" else 20 # 广域搜索多抓一些
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"❌ 搜索 API 调用失败: {e}")
            return []

        raw_results = data.get("organic_results", [])
        
        candidates = []
        for item in raw_results:
            source_info = item.get("source", "")
            if not source_info and "displayed_link" in item:
                source_info = item["displayed_link"]

            candidates.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "date": item.get("date", ""),
                "source": source_info
            })

        print(f"📥 [SerpApi] 原始抓取: {len(candidates)} 条")
        
        # 结果去重 (基于 URL)
        seen_urls = set()
        unique_candidates = []
        for c in candidates:
            if c['link'] not in seen_urls:
                seen_urls.add(c['link'])
                unique_candidates.append(c)
                
        return unique_candidates