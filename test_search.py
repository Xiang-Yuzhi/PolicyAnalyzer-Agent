import os
from core.search import PolicySearcher

def test_real_search():
    # 测试关键词：故意选一个有官方文件也有新闻解读的词
    query = "上市公司减持管理办法 2024"
    
    results = PolicySearcher.search(query, num_results=10)
    
    print("\n" + "="*80)
    print(f"🚀 搜索结果展示 (关键词: {query})")
    print("="*80)
    
    if not results:
        print("❌ 未找到结果，请检查 API Key 或网络连接。")
        return

    print(f"{'Level':<6} | {'Date':<12} | {'Source':<20} | {'Title'}")
    print("-" * 80)
    
    for idx, r in enumerate(results):
        # 截断过长的标题以便展示
        title = (r['title'][:35] + '...') if len(r['title']) > 35 else r['title']
        source = (r['source'][:18] + '..') if len(r['source']) > 18 else r['source']
        date = r.get('date', '') if r.get('date') else '-'
        level = r.get('authority_level', 8)
        
        print(f"{level:<6} | {date:<12} | {source:<20} | {idx+1}. {title}")
        print(f"       🔗 {r['link']}")
        print("-" * 80)

if __name__ == "__main__":
    test_real_search()