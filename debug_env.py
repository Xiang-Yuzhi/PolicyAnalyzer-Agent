import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("SERPER_API_KEY")

if key:
    print(f"✅ 成功读取 Key: {key[:5]}****** (长度: {len(key)})")
else:
    print("❌ 未读取到 Key。请检查 .env 文件是否存在，以及变量名是否写对。")