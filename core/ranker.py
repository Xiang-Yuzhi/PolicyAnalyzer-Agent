import re
from datetime import datetime
from typing import List, Dict

class PolicyRanker:
    """
    实现 PRD 5.2 节定义的权威性排序逻辑
    """
    
    # PRD 定义的优先级字典
    # 这里的 Key 是 Level (1最高), Value 是关键词列表
    AUTHORITY_DICT = {
        # [修改点] 将 "gov.cn" 改为 "www.gov.cn"，防止误伤 csrc.gov.cn 等子部门网站
        1: ["国务院", "全国人大", "www.gov.cn", "state council"], 
        
        2: ["证监会", "csrc", "人民银行", "pbc", "金融监管总局", "cbirc"],
        3: ["发改委", "ndrc", "财政部", "mof", "工信部", "商务部"],
        4: ["部", "局", "委员会"], 
        5: ["省", "自治区", "直辖市"], 
        6: ["市", "区", "县"],       
        7: ["人民网", "新华", "news.cn", "people.com.cn"], 
        8: [] 
    }

    @staticmethod
    def get_authority_level(source: str, url: str) -> int:
        """
        根据来源名称和 URL 判断权威等级 (1-8)
        """
        source = source if source else ""
        url = url if url else ""
        
        content_to_check = (source + " " + url).lower()
        
        for level, keywords in PolicyRanker.AUTHORITY_DICT.items():
            for kw in keywords:
                # 简单的字符串包含匹配
                if kw in content_to_check:
                    return level
        return 8 

    @staticmethod
    def get_relevance_score(title: str, snippet: str, query: str) -> float:
        """
        计算简单的相关性得分：关键词在标题和摘要中出现的频率
        """
        if not query:
            return 0.0
        
        score = 0.0
        title = title.lower()
        snippet = snippet.lower()
        query_words = query.lower().split()
        
        for word in query_words:
            if word in title:
                score += 10.0 # 标题匹配权重更高
            if word in snippet:
                score += 2.0
                
        return score

    @staticmethod
    def sort_policies(policies: List[Dict], query: str = "") -> List[Dict]:
        """
        排序规则：
        1. 关键词相关性 (Score 降序)
        2. 权威性 (Level 升序: 1 -> 8)
        3. 发布时间 (Timestamp 降序: 新 -> 旧)
        """
        for p in policies:
            # 1. 相关性
            p['relevance_score'] = PolicyRanker.get_relevance_score(
                p.get('title', ''), 
                p.get('snippet', ''), 
                query
            )
            # 2. 权威性
            p['authority_level'] = PolicyRanker.get_authority_level(
                p.get('source', ''), 
                p.get('link', '')
            )
            # 3. 时间处理
            if 'date' not in p or not p['date']:
                 p['_sort_date'] = "1970-01-01"
            else:
                 p['_sort_date'] = p['date']

        # 多级排序：Python 的 sort 是稳定的，按优先级从低到高反向操作
        # 第一步：按时间降序 (次次要)
        policies.sort(key=lambda x: x.get('_sort_date', ''), reverse=True)
        
        # 第二步：按权威等级升序 (次要)
        policies.sort(key=lambda x: x['authority_level'], reverse=False)

        # 第三步：按相关性评分降序 (主要)
        policies.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return policies