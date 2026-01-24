import sys
import os
import json

# ---------------------------------------------------------
# 环境设置：确保能导入 core 模块
# ---------------------------------------------------------
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from core.ranker import PolicyRanker
except ImportError:
    print("❌ 错误: 无法导入 PolicyRanker。请确保 core/ranker.py 存在且目录结构正确。")
    sys.exit(1)

def test_sorting_logic():
    """
    测试 PRD 5.1 & 5.2 定义的排序规则：
    1. 权威性优先级 (Level 1 -> Level 8)
    2. 发布时间 (新 -> 旧)
    """
    
    # ---------------------------------------------------------
    # 1. 构造模拟数据 (Mock Data)
    # ---------------------------------------------------------
    # 场景设计：
    # A. 商业媒体，日期最新 (干扰项，应排在最后)
    # B. 国务院，日期最旧 (权威最高，应排在最前)
    # C. 证监会，日期较新
    # D. 证监会，日期较旧 (同级比较，应排在 C 之后)
    # E. 权威媒体 (Level 7)
    
    mock_policies = [
        {
            "title": "【干扰项】某商业财经快讯：股市大涨预测",
            "source": "Sina Finance",
            "link": "https://finance.sina.com.cn/stock/...",
            "date": "2025-01-01",  # 日期最新，但 Authority Level 8
            "snippet": "分析师预测..."
        },
        {
            "title": "【Level 1】国务院关于进一步提高上市公司质量的意见",
            "source": "State Council (gov.cn)",
            "link": "http://www.gov.cn/zhengce/content/...",
            "date": "2023-01-01",  # 日期最旧，但 Authority Level 1
            "snippet": "国务院发布..."
        },
        {
            "title": "【Level 2】证监会发布2024年3月公告",
            "source": "CSRC",
            "link": "http://www.csrc.gov.cn/pub/new/...",
            "date": "2024-03-01",  # Level 2, 较新
            "snippet": "证监会决定..."
        },
        {
            "title": "【Level 2】证监会发布2024年2月公告",
            "source": "China Securities Regulatory Commission",
            "link": "http://www.csrc.gov.cn/pub/old/...",
            "date": "2024-02-01",  # Level 2, 较旧
            "snippet": "监管动态..."
        },
        {
            "title": "【Level 7】新华网转载：金融工作会议精神",
            "source": "Xinhua Net",
            "link": "http://www.news.cn/fortune/...",
            "date": "2024-12-01",  # Level 7
            "snippet": "据新华社报道..."
        }
    ]

    print(f"📊 原始数据：共 {len(mock_policies)} 条 (顺序已打乱)")
    print("-" * 60)

    # ---------------------------------------------------------
    # 2. 执行排序
    # ---------------------------------------------------------
    sorted_policies = PolicyRanker.sort_policies(mock_policies)

    # ---------------------------------------------------------
    # 3. 验证结果
    # ---------------------------------------------------------
    print("\n✅ 排序结果 (预期：Level 1->8, Level内日期 新->旧)：")
    print("-" * 60)
    print(f"{'Level':<8} | {'Date':<12} | {'Source':<20} | {'Title'}")
    print("-" * 60)

    for p in sorted_policies:
        level = p.get('authority_level', 'N/A')
        print(f"{level:<8} | {p['date']:<12} | {p['source']:<20} | {p['title']}")

    # ---------------------------------------------------------
    # 4. 自动断言 (Assertions) - CI/CD 风格
    # ---------------------------------------------------------
    print("\nRunning Assertions...")
    
    # 验证第一名必须是 Level 1 (国务院)
    assert sorted_policies[0]['authority_level'] == 1, "❌ 失败: 第一名不是 Level 1"
    
    # 验证最后一名必须是 Level 8 (商业媒体)
    assert sorted_policies[-1]['authority_level'] == 8, "❌ 失败: 最后一名不是 Level 8"
    
    # 验证同为 Level 2 的情况下，3月(New) 排在 2月(Old) 前面
    csrc_new = next(p for p in sorted_policies if "3月" in p['title'])
    csrc_old = next(p for p in sorted_policies if "2月" in p['title'])
    assert sorted_policies.index(csrc_new) < sorted_policies.index(csrc_old), "❌ 失败: 同级日期排序错误"

    print("\n✨ 所有测试通过！Ranker 逻辑符合 PRD 要求。")

if __name__ == "__main__":
    test_sorting_logic()