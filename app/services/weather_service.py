import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.services.settings_service import get_settings


class WeatherService:
    """天气服务 - 提供天气预报功能（使用模拟数据）"""

    def __init__(self):
        self._cache: Dict[str, tuple[datetime, Dict[str, Any]]] = {}
        self._cache_duration = timedelta(minutes=30)  # 缓存30分钟

    def _get_config(self):
        """从 settings_service 获取最新配置"""
        settings = get_settings()
        return {
            "api_key": settings.get("WEATHER_API_KEY", ""),
            "api_url": settings.get("WEATHER_API_URL", "https://devapi.qweather.com/v7"),
            "default_city": settings.get("WEATHER_CITY", "北京"),
        }

    def is_configured(self) -> bool:
        """检查天气API是否已配置（始终返回True，使用模拟数据）"""
        return True

    async def get_weather(self, city: str = None) -> Optional[Dict[str, Any]]:
        """
        获取天气信息（使用模拟数据）

        Args:
            city: 城市名称，如果不提供则使用默认城市

        Returns:
            天气信息字典
        """
        config = self._get_config()
        target_city = city or config["default_city"]
        cache_key = target_city

        # 检查缓存
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_duration:
                return cached_data

        # 使用模拟数据
        result = self._get_mock_weather(target_city)

        # 缓存结果
        if result:
            self._cache[cache_key] = (datetime.now(), result)

        return result

    def _get_mock_weather(self, city: str) -> Dict[str, Any]:
        """获取模拟天气数据"""
        today = datetime.now()
        city_name = city if not str(city).isdigit() else city

        # 根据城市名调整模拟数据
        temp_base = 20
        if "上海" in city_name or "广州" in city_name or "深圳" in city_name:
            temp_base = 25
        elif "成都" in city_name or "重庆" in city_name:
            temp_base = 22
        elif "北京" in city_name or "天津" in city_name:
            temp_base = 18

        conditions = ["晴", "多云", "阴", "小雨"]
        import random
        condition = random.choice(conditions)

        return {
            "city": city_name,
            "temperature": temp_base + random.randint(-3, 5),
            "condition": condition,
            "humidity": 45 + random.randint(0, 30),
            "wind_speed": 8 + random.randint(0, 15),
            "aqi": 35 + random.randint(0, 40),
            "forecast": [
                {
                    "date": today.strftime("%Y-%m-%d"),
                    "high": temp_base + 6 + random.randint(-2, 3),
                    "low": temp_base - 2 + random.randint(-2, 2),
                    "condition": random.choice(["晴", "多云", "阴"])
                },
                {
                    "date": (today + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "high": temp_base + 8 + random.randint(-2, 3),
                    "low": temp_base + random.randint(-2, 2),
                    "condition": random.choice(["晴", "多云", "小雨"])
                },
                {
                    "date": (today + timedelta(days=2)).strftime("%Y-%m-%d"),
                    "high": temp_base + 5 + random.randint(-2, 3),
                    "low": temp_base - 3 + random.randint(-2, 2),
                    "condition": random.choice(["多云", "阴", "小雨"])
                },
            ]
        }

    def get_weather_suggestion(self, weather: Dict[str, Any]) -> str:
        """根据天气给出建议"""
        if not weather:
            return "暂无天气信息"

        suggestions = []
        condition = weather.get("condition", "")
        temp = weather.get("temperature", 999)
        aqi = weather.get("aqi", 999)

        # 温度建议
        if temp <= 5:
            suggestions.append("天气寒冷，注意保暖，多穿衣服哦🧥")
        elif temp >= 30:
            suggestions.append("天气炎热，注意防晒，多喝水🥤")

        # 天气状况建议
        if "雨" in condition:
            suggestions.append("今天有雨，出门记得带伞☔")
        elif "雪" in condition:
            suggestions.append("今天有雪，注意路滑🧤")
        elif "晴" in condition:
            suggestions.append("今天天气晴朗，适合户外活动🌞")

        # 空气质量建议
        if aqi > 100:
            suggestions.append("空气质量一般，敏感人群减少户外活动😷")

        if not suggestions:
            return "今天天气不错，适合正常活动😊"

        return "\n".join(suggestions)
