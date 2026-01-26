import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

class Config:
    # 模型配置
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
    MODEL_NAME = "qwen-flash"
    
    # 搜索配置
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")
    
    # 业务规则配置 (对应 PRD 2.2)
    MAX_SEARCH_RESULTS = 10
    MAX_INPUT_TOKENS = 20000
    MAX_OUTPUT_TOKENS = 5000

    @staticmethod
    def validate():
        """启动时检查 Key 是否存在"""
        if not Config.DASHSCOPE_API_KEY:
            raise ValueError("缺少 DASHSCOPE_API_KEY，请检查 .env 文件")
        if not Config.SERPER_API_KEY:
            raise ValueError("缺少 SERPER_API_KEY，请检查 .env 文件")