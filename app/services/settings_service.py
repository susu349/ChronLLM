import os
from pathlib import Path

ENV_FILE = Path(__file__).parent.parent.parent / ".env"

DEFAULTS = {
    "LLM_API_KEY": "",
    "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "LLM_MODEL": "qwen3.6-plus",
    "DEFAULT_REMINDER_MINUTES": "10",
    "USER_NAME": "少爷",
    "WEATHER_API_KEY": "",
    "WEATHER_API_URL": "https://devapi.qweather.com/v7",
    "WEATHER_CITY": "北京",
}


def get_settings() -> dict:
    settings = dict(DEFAULTS)
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key in settings:
                        settings[key] = value
    # 也检查环境变量（优先级更高）
    for key in DEFAULTS:
        env_val = os.getenv(key)
        if env_val:
            settings[key] = env_val
    return settings


def save_settings(settings: dict) -> dict:
    # 读取现有内容保留注释
    lines = []
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            lines = f.readlines()

    # 更新或追加
    updated = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=")[0].strip()
            if key in settings:
                new_lines.append(f'{key}={settings[key]}\n')
                updated.add(key)
                continue
        new_lines.append(line)

    for key, value in settings.items():
        if key not in updated:
            new_lines.append(f'{key}={value}\n')

    with open(ENV_FILE, "w") as f:
        f.writelines(new_lines)

    # 同时更新当前进程的 os.environ
    for key, value in settings.items():
        os.environ[key] = value

    return get_settings()
