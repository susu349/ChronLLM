import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'assistant.db'}"

# LLM 配置
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.6-plus")

# 默认提前提醒时间（分钟）
DEFAULT_REMINDER_MINUTES = int(os.getenv("DEFAULT_REMINDER_MINUTES", "10"))

# 天气 API 配置
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_API_URL = os.getenv("WEATHER_API_URL", "")
WEATHER_CITY = os.getenv("WEATHER_CITY", "北京")
