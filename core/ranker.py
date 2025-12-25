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
    def sort_policies(policies: List[Dict]) -> List[Dict]:
        """
        排序规则：
        1. 权威性 (Level 升序: 1 -> 8)
        2. 发布时间 (Timestamp 降序: 新 -> 旧)
        """
        for p in policies:
            p['authority_level'] = PolicyRanker.get_authority_level(
                p.get('source', ''), 
                p.get('link', '')
            )
            if 'date' not in p or not p['date']:
                 p['_sort_date'] = "1970-01-01"
            else:
                 p['_sort_date'] = p['date']

        # 1. 先按时间降序 (次要条件)
        policies.sort(key=lambda x: x.get('_sort_date', ''), reverse=True)
        
        # 2. 再按权威等级升序 (主要条件)
        # Python 的 sort 是稳定的，这一步会把 Level 1 提到最前，
        # 同时保留 Level 1 内部已经在第1步排好的时间顺序
        policies.sort(key=lambda x: x['authority_level'], reverse=False)
        
        return policies