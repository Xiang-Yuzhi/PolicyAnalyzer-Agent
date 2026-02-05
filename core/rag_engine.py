"""
RAG Engine: 检索增强生成核心

负责政策文档的切片、向量化存储及语义检索，支持精准原文引用。
"""

import os
from typing import List, Dict, Any
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 引入配置
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

class RAGEngine:
    """
    RAG 引擎：处理文档索引与检索
    """
    
    def __init__(self):
        # 初始化 Embedding 模型 (适配 DashScope 兼容模式)
        self.embeddings = OpenAIEmbeddings(
            api_key=Config.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="text-embedding-v3"
        )
        
        # 定义切片器 (增大切片长度保留更完整上下文)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,  # 增大切片以保留更多上下文
            chunk_overlap=200,  # 增加重叠防止关键信息被切断
            separators=["\n\n", "\n", "。", "！", "？", " ", ""]
        )

    def create_index(self, text: str):
        """
        对单份政策文本建立向量索引
        """
        if not text:
            print("⚠️ RAG: 输入文本为空，跳过索引创建")
            return None
        
        # 1. 文本切片
        chunks = self.text_splitter.split_text(text)
        print(f"📚 RAG: 文本切片完成，共 {len(chunks)} 个片段 (原文 {len(text)} 字)")
        
        if not chunks:
            print("⚠️ RAG: 切片结果为空")
            return None
        
        # 2. 建立向量库
        try:
            vector_store = FAISS.from_texts(chunks, self.embeddings)
            print(f"✅ RAG: 向量索引创建成功")
            return vector_store
        except Exception as e:
            print(f"❌ RAG: 建立向量索引失败: {e}")
            return None

    def retrieve_relevant_chunks(self, vector_store, query: str, k: int = 5) -> List[str]:
        """
        从向量库中检索与查询最相关的文本块
        """
        if not vector_store:
            return []
        
        try:
            docs = vector_store.similarity_search(query, k=k)
            return [doc.page_content for doc in docs]
        except Exception as e:
            print(f"❌ 检索失败: {e}")
            return []

    def get_context_for_analysis(self, vector_store, queries: List[str], k: int = 3) -> str:
        """
        为多个分析维度获取综合上下文
        
        Args:
            k: 每个query检索的文档数量，默认3条
        """
        if not vector_store:
            print("⚠️ RAG: vector_store 为空，无法检索")
            return ""
        
        all_chunks = []
        for q in queries:
            chunks = self.retrieve_relevant_chunks(vector_store, q, k=k)
            print(f"  🔎 Query '{q[:20]}...' -> 检索到 {len(chunks)} 个片段")
            all_chunks.extend(chunks)
        
        # 去重并合并
        unique_chunks = list(set(all_chunks))
        result = "\n---\n".join(unique_chunks)
        print(f"📊 RAG 检索汇总: 总 {len(all_chunks)} 个片段, 去重后 {len(unique_chunks)} 个, 共 {len(result)} 字符")
        return result

# 单例模式供外部调用
rag_engine = RAGEngine()
