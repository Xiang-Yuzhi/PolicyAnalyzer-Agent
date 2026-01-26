"""
Ranking V2: 混合排序算法

实现两阶段检索中的精排层：
1. 权威度评分 (Authority Score)
2. BM25 关键词相关性
3. 语义相似度 (Embedding Cosine Similarity)
4. 时效性评分 (Recency Score)

最终分数 = 加权组合
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

# BM25 算法
try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False
    print("⚠️ rank_bm25 未安装，将跳过 BM25 评分")


@dataclass
class ScoredPolicy:
    """带评分的政策对象"""
    policy: Dict[str, Any]
    authority_score: float = 0.0
    bm25_score: float = 0.0
    semantic_score: float = 0.0
    recency_score: float = 0.0
    final_score: float = 0.0


class HybridRanker:
    """
    混合排序器：多维度评分 + 加权融合
    """
    
    # 权威度层级 (与原 ranker.py 保持一致)
    AUTHORITY_LEVELS = {
        1: ["国务院", "中央", "全国人大", "国家发改委", "财政部"],
        2: ["证监会", "银保监会", "央行", "中国人民银行", "国家金融监督管理总局"],
        3: ["交易所", "上交所", "深交所", "北交所", "中登", "中国结算"],
        4: ["证券业协会", "基金业协会", "期货业协会"],
        5: ["地方金融局", "地方证监局"],
        6: ["券商", "证券公司", "银行", "保险公司"],
        7: ["财经媒体", "第一财经", "财新", "证券时报", "中国证券报"],
        8: ["门户网站", "新浪", "网易", "搜狐", "百度"]
    }
    
    # 官方域名白名单
    GOV_DOMAINS = [
        ".gov.cn", ".org.cn", "csrc.gov.cn", "sse.com.cn", 
        "szse.cn", "pbc.gov.cn", "nafmii.org.cn", "amac.org.cn",
        "circ.gov.cn", "mof.gov.cn", "ndrc.gov.cn"
    ]
    
    # 新闻媒体域名黑名单 (降权处理)
    NEWS_DOMAINS = [
        "eastmoney.com", "hexun.com", "10jqka.com.cn", "cnstock.com",
        "yicai.com", "caixin.com", "wallstreetcn.com", "cls.cn"
    ]
    
    # 噪音关键词黑名单 (针对系统、门户、报考以及明显的公司财务/招股类文件)
    # 移除了 "公告" 和 "摘要"，因为许多政策原文以这些词结尾
    NOISE_KEYWORDS = [
        "系统", "登录", "登入", "注册", "报考", "培训", "考试", "报名", 
        "下载中心", "工作门户", "管理平台", "网上信息系统", "人员管理系统",
        "招股书", "招股说明书", "招募说明书", "中报", "年报", "季报",
        "上市公告书", "分红公告", "业绩快报"
    ]
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        初始化排序器
        
        Args:
            weights: 各维度权重，默认 {"authority": 0.3, "bm25": 0.3, "semantic": 0.3, "recency": 0.1}
        """
        # 调整权重：提升权威度权重，减少新闻媒体结果
        self.weights = weights or {
            "authority": 0.45,  # 提升权威度权重
            "bm25": 0.25,
            "semantic": 0.20,
            "recency": 0.10
        }
    
    def rank(self, policies: List[Dict], query: str, 
             filter_official_only: bool = False) -> List[Dict]:
        """
        对政策列表进行混合排序 (两阶段逻辑)
        1. 根据相关性(BM25+语义)和时效性初步排序
        2. 取前15个候选，根据权威度重新排序
        """
        if not policies:
            return []
        
        # 1. 预过滤：官方来源筛选
        if filter_official_only:
            policies = self._filter_official(policies)
        
        scored = [ScoredPolicy(policy=p) for p in policies]
        
        # 2. 计算各维度分数
        # 2.1 权威度
        for sp in scored:
            sp.authority_score = self._calc_authority(sp.policy)
        
        # 2.2 相关性 (BM25)
        if HAS_BM25:
            self._calc_bm25_scores(scored, query)
        
        # 2.3 相关性 (语义)
        self._calc_semantic_scores(scored, query)
        
        # 2.4 时效性
        for sp in scored:
            sp.recency_score = self._calc_recency(sp.policy)
        
        # 3. 第一阶段：初步筛选 (相关性 + 时效性)
        # 权重: 相关性 0.7, 时效性 0.3
        for sp in scored:
            relevance = (sp.bm25_score + sp.semantic_score) / 2
            sp.final_score = 0.7 * relevance + 0.3 * sp.recency_score
            
        scored.sort(key=lambda x: x.final_score, reverse=True)
        
        # 取前 15 个作为精排候选
        candidates = scored[:15]
        
        # 4. 第二阶段：权威度重排
        # 在相关候选人中，权威度越高越靠前
        # 最终得分 = 0.6 * 权威度 + 0.4 * 初始得分
        # 新增：官方书名加成 (如果标题命中关键词)
        for sp in candidates:
            bonus = 0.0
            title = sp.policy.get('title', '').lower()
            # 简单判断：如果查询词中有较长片段出现在标题中，给予加成
            if len(query) > 4 and query.lower() in title:
                bonus = 0.2
            elif any(len(kw) > 2 and kw.lower() in title for kw in query.split()):
                bonus = 0.1
                
            sp.final_score = 0.6 * (sp.authority_score + bonus) + 0.4 * sp.final_score
            
        candidates.sort(key=lambda x: x.final_score, reverse=True)
        
        # 5. 返回结果 (过滤掉权威度极低的新闻，但保障至少有5条列表)
        result = []
        for sp in candidates:
            # 如果结果已经超过5条，则按之前逻辑进行权威度过滤
            if len(result) >= 5 and sp.authority_score < 0.25:
                continue
                
            policy = sp.policy.copy()
            policy["_scores"] = {
                "authority": round(sp.authority_score, 3),
                "relevance": round((sp.bm25_score + sp.semantic_score) / 2, 3),
                "recency": round(sp.recency_score, 3),
                "final": round(sp.final_score, 3)
            }
            result.append(policy)
            
        # 补齐逻辑：如果过滤后结果不足5条，从 candidates 中按序补齐（不带过滤）
        if len(result) < 5 and len(candidates) > len(result):
            seen_links = {p['link'] for p in result}
            for sp in candidates:
                if len(result) >= 5:
                    break
                if sp.policy['link'] not in seen_links:
                    policy = sp.policy.copy()
                    policy["_scores"] = {
                        "authority": round(sp.authority_score, 3),
                        "final": round(sp.final_score, 3),
                        "note": "backfill"
                    }
                    result.append(policy)

        return result
    
    def _filter_official(self, policies: List[Dict]) -> List[Dict]:
        """过滤仅保留官方来源"""
        filtered = []
        for p in policies:
            link = p.get("link", "").lower()
            source = p.get("source", "").lower()
            
            # 检查域名
            is_gov = any(domain in link for domain in self.GOV_DOMAINS)
            
            # 检查来源名称
            is_official_source = any(
                keyword in source 
                for keywords in list(self.AUTHORITY_LEVELS.values())[:5]
                for keyword in keywords
            )
            
            if is_gov or is_official_source:
                filtered.append(p)
        
        return filtered if filtered else policies  # 如果全被过滤，返回原列表
    
    def _calc_authority(self, policy: Dict) -> float:
        """计算权威度分数 (0-1)"""
        source = policy.get("source", "")
        link = policy.get("link", "")
        combined = f"{source} {link}".lower()
        
        # 1. 检查是否为噪音页面 (报考、系统、金融披露等) - 最高优先级拦截
        combined_text = f"{policy.get('title', '')} {policy.get('snippet', '')}".lower()
        
        # 优化：如果是官方域名 (.gov.cn 或 .org.cn)，对“公告”类噪音豁免
        is_high_auth_domain = ".gov.cn" in link or ".org.cn" in link
        
        for noise in self.NOISE_KEYWORDS:
            if noise.lower() in combined_text:
                # 如果是高权威域名且仅仅是包含“系统”以外的次级噪音词，可以适当放宽
                if is_high_auth_domain and noise not in ["系统", "登录", "报考", "考试"]:
                    continue
                return 0.0  # 彻底降权
        
        # 2. 检查各层级权威度
        for level, keywords in self.AUTHORITY_LEVELS.items():
            for kw in keywords:
                if kw.lower() in combined:
                    # Level 1 得分最高 (1.0)，Level 8 得分最低 (0.125)
                    return 1.0 - (level - 1) * 0.125
        
        # 3. 检查是否为官方域名
        if ".gov.cn" in link:
            return 0.9
        if ".org.cn" in link: # 中基协等
            return 0.85
        
        # 4. 检查是否为新闻媒体 (降权处理)
        for news_domain in self.NEWS_DOMAINS:
            if news_domain in link.lower():
                return 0.1  # 新闻媒体给低分但非零分
                
        return 0.3  # 默认分数
    
    def _calc_bm25_scores(self, scored_list: List[ScoredPolicy], query: str):
        """计算 BM25 分数"""
        # 构建语料库
        corpus = []
        for sp in scored_list:
            text = f"{sp.policy.get('title', '')} {sp.policy.get('snippet', '')}"
            # 简单分词
            tokens = self._tokenize(text)
            corpus.append(tokens)
        
        if not corpus:
            return
        
        # 构建 BM25 索引
        bm25 = BM25Okapi(corpus)
        
        # 查询分词
        query_tokens = self._tokenize(query)
        
        # 计算分数
        scores = bm25.get_scores(query_tokens)
        
        # 归一化到 0-1
        max_score = max(scores) if max(scores) > 0 else 1
        for i, sp in enumerate(scored_list):
            sp.bm25_score = scores[i] / max_score
    
    def _calc_semantic_scores(self, scored_list: List[ScoredPolicy], query: str):
        """
        计算语义相似度分数
        
        TODO: 后续可接入 DashScope Embedding API 或 sentence-transformers
        当前使用关键词重叠度作为简化实现
        """
        query_tokens = set(self._tokenize(query))
        
        for sp in scored_list:
            text = f"{sp.policy.get('title', '')} {sp.policy.get('snippet', '')}"
            text_tokens = set(self._tokenize(text))
            
            if not query_tokens or not text_tokens:
                sp.semantic_score = 0.0
                continue
            
            # Jaccard 相似度
            intersection = len(query_tokens & text_tokens)
            union = len(query_tokens | text_tokens)
            sp.semantic_score = intersection / union if union > 0 else 0.0
    
    def _calc_recency(self, policy: Dict) -> float:
        """计算时效性分数 (0-1)"""
        date_str = policy.get("date", "")
        
        if not date_str:
            return 0.3  # 无日期给默认分
        
        # 尝试解析日期
        try:
            # 常见格式
            for fmt in ["%Y年%m月%d日", "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月"]:
                try:
                    date = datetime.strptime(date_str, fmt)
                    break
                except:
                    continue
            else:
                # 尝试提取年份
                year_match = re.search(r"(\d{4})", date_str)
                if year_match:
                    date = datetime(int(year_match.group(1)), 6, 15)  # 假设年中
                else:
                    return 0.3
            
            # 计算距今天数
            days_ago = (datetime.now() - date).days
            
            # 时效性衰减
            if days_ago <= 30:      # 1个月内
                return 1.0
            elif days_ago <= 90:    # 3个月内
                return 0.9
            elif days_ago <= 180:   # 半年内
                return 0.8
            elif days_ago <= 365:   # 1年内
                return 0.6
            elif days_ago <= 730:   # 2年内
                return 0.4
            else:
                return 0.2
                
        except Exception as e:
            return 0.3
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词（中文按字符，英文按空格）"""
        # 移除标点
        text = re.sub(r'[^\w\s]', ' ', text)
        
        tokens = []
        for word in text.split():
            if re.match(r'^[\u4e00-\u9fff]+$', word):  # 中文
                tokens.extend(list(word))  # 按字符拆分
            else:
                tokens.append(word.lower())
        
        return tokens


# 测试代码
if __name__ == "__main__":
    ranker = HybridRanker()
    
    test_policies = [
        {"title": "证监会发布上市公司减持新规", "link": "https://www.csrc.gov.cn/xxx", "source": "证监会", "date": "2024-05-24", "snippet": "减持规定..."},
        {"title": "解读减持新规的影响", "link": "https://www.sina.com.cn/xxx", "source": "新浪财经", "date": "2024-05-25", "snippet": "分析减持..."},
        {"title": "上交所发布减持问答", "link": "https://www.sse.com.cn/xxx", "source": "上交所", "date": "2024-05-20", "snippet": "问答..."},
    ]
    
    results = ranker.rank(test_policies, "减持新规")
    
    for r in results:
        print(f"\n{r['title']}")
        print(f"  分数: {r['_scores']}")
