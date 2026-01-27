"""
Ranking V4.0: Dual-Engine Hybrid Recall & AI Reasoning
"""

import re
import json
import os
import math
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

try:
    from config import Config
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

@dataclass
class ScoredPolicy:
    policy: Dict[str, Any]
    authority_score: float = 0.0
    bm25_score: float = 0.0
    semantic_score: float = 0.0
    google_rank_score: float = 0.0
    format_bonus: float = 0.0
    recency_score: float = 0.0
    llm_score: float = 0.5
    final_score: float = 0.0
    llm_label: str = ""
    is_original: bool = False
    status: str = ""
    tag: str = ""

class HybridRanker:
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
    GOV_DOMAINS = [".gov.cn", ".org.cn", "csrc.gov.cn", "sse.com.cn", "szse.cn", "pbc.gov.cn", "amac.org.cn"]
    URL_LAW_PATTERNS = ["/law/", "/rule/", "/self_reg/", "/regulatory/", "/zcfg/", "/standard/"]
    URL_DISCLOSURE_PATTERNS = ["/disclosure/", "/listing/", "/announcement/", "/report/", "/prospectus/"]
    NEWS_DOMAINS = ["eastmoney.com", "hexun.com", "10jqka.com.cn", "cnstock.com", "yicai.com"]
    NOISE_KEYWORDS = ["系统", "登录", "注册", "报考", "培训", "考试", "报名", "招股书", "招股说明书"]

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "google_rank": 0.20,
            "content": 0.20,
            "reliability": 0.30,
            "llm_reasoning": 0.30
        }
        self.llm = ChatOpenAI(
            model_name="qwen-max",
            openai_api_key=Config.DASHSCOPE_API_KEY,
            openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0
        )

    def rank(self, policies: List[Dict], query: str, temperature: float = 0.0) -> List[Dict]:
        if not policies: return []
        scored = [ScoredPolicy(policy=p) for p in policies]
        for sp in scored:
            rank_val = sp.policy.get("google_rank", 50)
            sp.google_rank_score = 1.0 / math.log2(rank_val + 1)
            sp.authority_score = self._calc_authority(sp.policy)
            sp.format_bonus = self._calc_format_bonus(sp.policy)
            sp.recency_score = self._calc_recency(sp.policy)
        if HAS_BM25: self._calc_bm25_scores(scored, query)
        self._calc_semantic_scores(scored, query)
        for sp in scored:
            rel = min(1.0, sp.authority_score + sp.format_bonus)
            cont = (sp.bm25_score + sp.semantic_score) / 2
            sp.final_score = 0.3 * sp.google_rank_score + 0.3 * cont + 0.3 * rel + 0.1 * sp.recency_score
        scored.sort(key=lambda x: x.final_score, reverse=True)
        candidates = scored[:15]
        self._llm_verify_policy(candidates, query, temperature=temperature)
        final_results = []
        for sp in candidates:
            rel = min(1.0, sp.authority_score + sp.format_bonus)
            cont = (sp.bm25_score + sp.semantic_score) / 2
            sp.final_score = (
                self.weights["google_rank"] * sp.google_rank_score +
                self.weights["content"] * cont +
                self.weights["reliability"] * rel +
                self.weights["llm_reasoning"] * sp.llm_score
            )
            if sp.authority_score <= 0.0 and sp.format_bonus < 0.15 and sp.llm_label != "A": continue
            if sp.final_score < 0.12: continue
            policy = sp.policy.copy()
            policy["_scores"] = {
                "google": round(sp.google_rank_score, 2),
                "content": round(cont, 2),
                "reliability": round(rel, 2),
                "ai_agent": round(sp.llm_score, 2),
                "final": round(sp.final_score, 3)
            }
            # Enrich metadata
            if sp.status: policy["status"] = sp.status
            if sp.tag: policy["tag"] = sp.tag
            
            if sp.is_original: policy["title"] = "ORIGINAL: " + policy["title"]
            final_results.append(policy)
        final_results.sort(key=lambda x: x["_scores"]["final"], reverse=True)
        return final_results

    def _calc_format_bonus(self, policy: Dict) -> float:
        link = policy.get("link", "").lower()
        if link.endswith(".pdf"): return 0.20
        if any(kw in link for kw in ["/attachment/", "/download/", "/upload/", "file="]): return 0.15
        return 0.0

    def _calc_authority(self, policy: Dict) -> float:
        source = policy.get("source", "")
        link = policy.get("link", "")
        snippet = f"{policy.get('title', '')} {policy.get('snippet', '')}".lower()
        is_gov = ".gov.cn" in link or ".org.cn" in link
        for noise in self.NOISE_KEYWORDS:
            if noise in snippet:
                if is_gov and noise not in ["系统", "登录"]: continue
                return 0.0
        if ".gov.cn" in link: score = 0.9
        elif ".org.cn" in link: score = 0.85
        elif any(d in link for d in ["sse.com.cn", "szse.cn", "bse.cn"]): score = 0.7
        else:
            score = 0.3
            for level, keywords in self.AUTHORITY_LEVELS.items():
                if any(kw.lower() in f"{source} {link}".lower() for kw in keywords):
                    score = 1.0 - (level - 1) * 0.125
                    break
        if any(p in link for p in self.URL_LAW_PATTERNS): score = min(1.0, score + 0.1)
        if any(p in link for p in self.URL_DISCLOSURE_PATTERNS): score = 0.1
        return score

    def _calc_bm25_scores(self, scored_list: List[ScoredPolicy], query: str):
        corpus = [self._tokenize(f"{sp.policy.get('title')} {sp.policy.get('snippet')}") for sp in scored_list]
        if not corpus: return
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(self._tokenize(query))
        max_s = max(scores) if max(scores) > 0 else 1
        for i, sp in enumerate(scored_list): sp.bm25_score = scores[i] / max_s

    def _calc_semantic_scores(self, scored_list: List[ScoredPolicy], query: str):
        q_tokens = set(self._tokenize(query))
        for sp in scored_list:
            t_tokens = set(self._tokenize(f"{sp.policy.get('title')} {sp.policy.get('snippet')}"))
            if not q_tokens or not t_tokens: sp.semantic_score = 0.0
            else: sp.semantic_score = len(q_tokens & t_tokens) / len(q_tokens | t_tokens)

    def _calc_recency(self, policy: Dict) -> float:
        ds = policy.get("date", "")
        if not ds: return 0.3
        try:
            for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
                try:
                    dt = datetime.strptime(ds, fmt)
                    break
                except: continue
            else: return 0.3
            days = (datetime.now() - dt).days
            if days <= 30: return 1.0
            if days <= 365: return 0.7
            return 0.3
        except: return 0.3

    def _tokenize(self, text: str) -> List[str]:
        text = re.sub(r'[^\w\s]', ' ', text or "")
        tokens = []
        for word in text.split():
            if re.match(r'^[\u4e00-\u9fff]+$', word): tokens.extend(list(word))
            else: tokens.append(word.lower())
        return tokens

    def _llm_verify_policy(self, candidates: List[ScoredPolicy], query: str, temperature: float = 0.0):
        if not candidates: return
        prompt_text = """Expert Auditor. Intention: "{query}"
Task:
1. Relevance (0-1)
2. Label: [A] Policy Original [B] News/Summary [C] Noise
3. is_original: true if full official text.
4. status: Current effectiveness (e.g. "现行有效", "已失效", "征求意见").
5. tag: Brief category tag (e.g. "正式办法", "解读", "通知").

Output JSON: [{{ "index": 1, "score": 0.9, "label": "A", "is_original": true, "status": "现行有效", "tag": "正式办法" }}, ...]
Data:
{data_list}
"""
        data = ""
        for i, sp in enumerate(candidates):
            title = sp.policy.get('title') or ""
            snippet = sp.policy.get('snippet') or ""
            data += f"{i+1}. {title} | {snippet[:100]}\n"
        try:
            prompt = ChatPromptTemplate.from_messages([("user", prompt_text)])
            chain = prompt | self.llm.bind(temperature=temperature) | StrOutputParser()
            res = chain.invoke({"query": query, "data_list": data})
            match = re.search(r'\[.*\]', res, re.S)
            if match:
                judgments = json.loads(match.group())
                for j in judgments:
                    idx = j.get("index", 1) - 1
                    if 0 <= idx < len(candidates):
                        sp = candidates[idx]
                        sp.llm_score = float(j.get("score", 0.5))
                        sp.llm_label = j.get("label", "B")
                        sp.is_original = j.get("is_original", False)
                        sp.status = j.get("status", "")
                        sp.tag = j.get("tag", "")
                        if sp.llm_label == "A": sp.llm_score = min(1.0, sp.llm_score * 1.2)
                        elif sp.llm_label == "C": sp.llm_score *= 0.1
        except Exception as e:
            print(f"LLM Error: {e}")

if __name__ == "__main__":
    ranker = HybridRanker()
    test = [{"title": "Test Policy", "link": "gov.cn/1.pdf", "google_rank": 1}]
    print(ranker.rank(test, "Test"))
