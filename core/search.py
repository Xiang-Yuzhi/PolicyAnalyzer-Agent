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
    def search(query: str, num_results: int = 50, 
               source_preference: str = "all", 
               time_range: Optional[str] = None,
               raw_query: Optional[str] = None) -> List[Dict]:
        """
        执行双向量搜索 (Stage 1: Multi-Vector Recall)
        1. 原始搜索: 信任 Google 的原生理解
        2. 精炼搜索: 使用 AI 处理后的关键词 + 站点限制
        """
        queries_to_run = []
        
        # 1. 原始查询 (Raw)
        if raw_query:
            queries_to_run.append({"q": raw_query, "type": "raw"})
        
        # 2. 精炼查询 (Refined)
        refined_q = query
        if source_preference == "gov":
            refined_q += " (site:gov.cn OR site:amac.org.cn OR site:sse.com.cn OR site:szse.cn OR site:bse.cn)"
        if time_range:
            refined_q += f" {time_range}"
        queries_to_run.append({"q": refined_q, "type": "refined"})

        all_candidates = {} # url -> candidate_dict

        for q_item in queries_to_run:
            print(f"🔍 [SerpApi] 正在进行{q_item['type']}检索: {q_item['q']} ...")
            
            url = "https://serpapi.com/search"
            params = {
                "engine": "google",
                "q": q_item['q'],
                "api_key": Config.SERPER_API_KEY,
                "gl": "cn",
                "hl": "zh-cn",
                "num": num_results
            }

            try:
                response = requests.get(url, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                raw_results = data.get("organic_results", [])
                
                for idx, item in enumerate(raw_results):
                    link = item.get("link", "")
                    if not link: continue
                    
                    # 原始排名 (从1开始)
                    rank = item.get("position", idx + 1)
                    
                    source_info = item.get("source", "")
                    if not source_info and "displayed_link" in item:
                        source_info = item["displayed_link"]

                    # 如果 URL 已存在，保留更好的排名
                    if link in all_candidates:
                        if rank < all_candidates[link]['google_rank']:
                            all_candidates[link]['google_rank'] = rank
                    else:
                        all_candidates[link] = {
                            "title": item.get("title", ""),
                            "link": link,
                            "snippet": item.get("snippet", ""),
                            "date": item.get("date", ""),
                            "source": source_info,
                            "google_rank": rank, # 记录 Google 原始排名
                            "search_type": q_item['type']
                        }
            except Exception as e:
                print(f"❌ 搜索 API 调用失败 [{q_item['type']}]: {e}")

        # 转为列表并输出
        unique_candidates = list(all_candidates.values())
        print(f"📥 [SerpApi] 混合召回总量: {len(unique_candidates)} 条")
        
        return unique_candidates
