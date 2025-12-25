import json
import sys
import os

# 确保能找到 core 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.analyzer import PolicyAnalyzer

def test_analysis():
    # 模拟从 Search 结果中用户选中的那一条数据
    target_policy = {
        "title": "【第224号令】《上市公司股东减持股份管理暂行办法》",
        # [重点修改] 这是一个纯净的字符串，没有任何 [] 或 ()
        "link": "http://www.csrc.gov.cn/csrc/c101953/c7483190/content.shtml", 
        "source": "中国证券监督管理委员会",
        "date": "2024年5月24日"
    }

    print("🏁 开始测试 Analyzer 模块...")
    print(f"📄 目标文件: {target_policy['title']}")
    
    analyzer = PolicyAnalyzer()
    
    # 执行分析
    result = analyzer.analyze(target_policy)
    
    # 展示结果
    print("\n" + "="*60)
    print("🤖 LLM 分析结果 (JSON 结构)")
    print("="*60)
    
    # 漂亮地打印 JSON
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if "chat_bullets" in result:
        print("\n✅ 测试通过：成功生成了 JSON 结构。")
        print(f"📌 生成了 {len(result['chat_bullets'])} 条 Bullet Points。")
    else:
        print("\n❌ 测试失败：未能生成正确结构。")

if __name__ == "__main__":
    test_analysis()