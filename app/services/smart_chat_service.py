"""智能聊天服务 - 让管家更聪明地回应用户"""

import json
import httpx
from datetime import date, datetime
from typing import Dict, Any, List, Optional

from app.database import SessionLocal
from app.models import Event, Priority
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.services.weather_service import WeatherService
from app.services.preferences_service import PreferencesService


def build_system_prompt(style_config: Dict[str, Any]) -> str:
    """根据管家风格构建系统提示词"""
    name = style_config.get('name', '管家')
    call_user = style_config.get('call_user', '{user_name}')
    self_call = style_config.get('self_call', '我')
    tone = style_config.get('tone', 'professional')
    emoji = style_config.get('emoji', '🎩')

    tone_descriptions = {
        'professional': '专业、稳重、优雅',
        'cute': '可爱、活泼、带有喵~尾音',
        'polite': '恭敬、温柔、周到',
        'elegant': '英式管家风格，完美、优雅',
        'tsundere': '嘴上不饶人，其实很关心您',
        'gentle': '温柔、体贴、包容',
        'samurai': '忠诚、刚毅、守信',
        'robot': '高效、精准、不带感情',
    }

    tone_desc = tone_descriptions.get(tone, '专业、稳重')

    return f"""你是"小管"，{call_user}的私人AI管家兼人生导师。{emoji}

管家风格设定：{name}
性格特点：{tone_desc}

重要规则：
1. 称呼用户为"{call_user}"
2. 自称为"{self_call}"
3. 语气要{tone_desc}
4. 回答要贴心、自然，符合管家风格
5. 从自然语言中提取日程安排并保存
6. 回答各种问题（天气、日程、生活常识等）
7. 主动关心用户的状态
8. 给出贴心的建议和提醒

只返回JSON，格式如下：
{{
  "reply": "管家的回复",
  "events": [
    {{
      "title": "事件标题",
      "start_time": "HH:MM",
      "date_offset": 0,
      "duration": 60,
      "priority": "medium",
      "description": ""
    }}
  ]
}}

events可以是空数组[]，如果没有需要添加的日程。
date_offset: 0=今天, 1=明天, 2=后天, 以此类推。"""


BASE_SYSTEM_PROMPT = """你是"小管"，少爷的私人AI管家兼人生导师。

性格设定：
- 温柔、体贴、无微不至，真正关心少爷
- 聪明、机智，能理解少爷的需求
- 回答要贴心、自然，不要太机械

只返回JSON，格式如下：
{{
  "reply": "管家的回复",
  "events": []
}}
"""


class SmartChatService:
    """智能聊天服务"""

    def __init__(self):
        self.db = SessionLocal()
        self.prefs = PreferencesService()

    def close(self):
        self.db.close()
        self.prefs.close()

    def _get_today_events_text(self) -> str:
        """获取今日事件文本"""
        from sqlalchemy import func
        events = self.db.query(Event).filter(
            func.date(Event.start_time) == date.today()
        ).order_by(Event.start_time).all()
        if not events:
            return "今天还没有安排"
        lines = []
        for e in events:
            status_icon = "✅" if e.status.value == "completed" else ""
            lines.append(
                f"- {e.start_time.strftime('%H:%M')}-{e.end_time.strftime('%H:%M')} "
                f"[{e.priority.value}] {e.title} {status_icon}"
            )
        return "\n".join(lines)

    def _get_current_context(self) -> str:
        """获取当前上下文信息"""
        today = date.today()
        hour = datetime.now().hour

        # 时间问候
        if hour < 12:
            time_greet = "早上好"
        elif hour < 14:
            time_greet = "中午好"
        elif hour < 18:
            time_greet = "下午好"
        else:
            time_greet = "晚上好"

        # 星期
        weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]

        context = f"""当前日期：{today.isoformat()} ({weekday_cn})
当前时间：{datetime.now().strftime('%H:%M')}
问候：{time_greet}

今日已有安排：
{self._get_today_events_text()}
"""
        return context

    async def chat(self, user_message: str) -> Dict[str, Any]:
        """智能聊天"""
        user_msg_lower = user_message.lower()

        # 获取管家风格
        style_config = self.prefs.get_butler_style_config()
        system_prompt = build_system_prompt(style_config)

        # 快速回复：今天有什么安排
        if any(keyword in user_msg_lower for keyword in ["今天", "安排", "日程"]):
            events_text = self._get_today_events_text()
            if events_text == "今天还没有安排":
                return {
                    "reply": f"{style_config.get('call_user', '少爷')}，今天还没有安排呢。需要我帮您规划一下吗？",
                    "events": []
                }
            else:
                return {
                    "reply": f"{style_config.get('call_user', '少爷')}，这是今天的安排：\n\n{events_text}",
                    "events": []
                }

        # 快速回复：天气
        if any(keyword in user_msg_lower for keyword in ["天气", "温度", "下雨", "晴天"]):
            weather_svc = WeatherService()
            try:
                weather = await weather_svc.get_weather()
                if weather:
                    suggestion = weather_svc.get_weather_suggestion(weather)
                    return {
                        "reply": f"{style_config.get('call_user', '少爷')}，今天的天气：{weather.weather_text}，温度 {weather.temperature}℃。{suggestion}",
                        "events": []
                    }
            finally:
                pass
            return {
                "reply": f"{style_config.get('call_user', '少爷')}，天气信息暂时无法获取，请稍后再试。",
                "events": []
            }

        # 使用 LLM 进行智能回复
        if not LLM_API_KEY:
            return self._fallback_reply(user_message, style_config)

        try:
            prompt = f"""{self._get_current_context()}

{style_config.get('call_user', '用户')}说：{user_message}

请给出贴心的回复。"""

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                    json={
                        "model": LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.7,
                    },
                    timeout=httpx.Timeout(60.0, connect=10.0),
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                content = self._extract_json(content)
                return json.loads(content)
        except Exception as e:
            print(f"[智能聊天] LLM调用失败: {e}")
            return self._fallback_reply(user_message, style_config)

    def _extract_json(self, text: str) -> str:
        """提取JSON"""
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:]
                try:
                    json.loads(part)
                    return part
                except json.JSONDecodeError:
                    continue
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end+1]
        return text

    def _fallback_reply(self, user_message: str, style_config: Dict[str, Any]) -> Dict[str, Any]:
        """本地回退回复（应用管家风格）"""
        user_msg_lower = user_message.lower()
        call_user = style_config.get('call_user', '少爷')
        self_call = style_config.get('self_call', '我')
        emoji = style_config.get('emoji', '')

        # 问候
        if any(keyword in user_msg_lower for keyword in ["早", "早上好", "早安"]):
            return {
                "reply": f"{call_user}早上好！新的一天开始了，今天想做些什么呢？{emoji}",
                "events": []
            }
        if any(keyword in user_msg_lower for keyword in ["晚", "晚上好", "晚安"]):
            return {
                "reply": f"{call_user}晚上好！辛苦了一天，早点休息吧。{emoji}",
                "events": []
            }

        # 简单对话
        if any(keyword in user_msg_lower for keyword in ["你好", "您好", "嗨", "hi", "hello"]):
            return {
                "reply": f"您好，{call_user}！{self_call}是您的管家小管，有什么可以为您效劳的吗？{emoji}",
                "events": []
            }

        if any(keyword in user_msg_lower for keyword in ["谢谢", "感谢", "多谢"]):
            return {
                "reply": f"不用谢，{call_user}！这是{self_call}应该做的。{emoji}",
                "events": []
            }

        # 默认回复
        return {
            "reply": f"{call_user}，{self_call}在。有什么需要帮忙的吗？您可以告诉我要安排什么日程。{emoji}",
            "events": []
        }

    def save_events(self, events_data: list[dict]) -> list[dict]:
        """保存事件"""
        from datetime import timedelta
        saved = []
        for ev in events_data:
            try:
                date_offset = int(ev.get("date_offset", 0))
                target_date = date.today() + timedelta(days=date_offset)
                start = self._parse_time(ev.get("start_time", ""), target_date)
                duration = int(ev.get("duration", 30))
                end = start + timedelta(minutes=duration)
                priority = Priority(ev.get("priority", "medium"))

                event = Event(
                    title=ev["title"],
                    start_time=start,
                    end_time=end,
                    priority=priority,
                    description=ev.get("description", ""),
                    is_ai_scheduled=True,
                )
                self.db.add(event)
                saved.append({
                    "title": event.title,
                    "start": event.start_time.strftime("%H:%M"),
                    "end": event.end_time.strftime("%H:%M"),
                    "date": event.start_time.strftime("%m/%d"),
                })
            except Exception as e:
                print(f"[智能聊天] 解析事件失败: {e}, 数据: {ev}")

        if saved:
            self.db.commit()
            for s in saved:
                evt = self.db.query(Event).filter(
                    Event.title == s["title"],
                    Event.start_time == self._parse_date_time(s["date"], s["start"]),
                ).first()
                if evt:
                    s["id"] = evt.id
                    s["time"] = s["start"]

        return saved

    def _parse_date_time(self, date_str: str, time_str: str) -> datetime:
        """解析日期时间"""
        try:
            m, d = map(int, date_str.split("/"))
            h, mi = map(int, time_str.split(":"))
            return datetime(date.today().year, m, d, h, mi)
        except (ValueError, AttributeError):
            return datetime.now()

    def _parse_time(self, time_str: str, target_date: date) -> datetime:
        """解析时间"""
        if "T" in time_str:
            return datetime.fromisoformat(time_str)
        try:
            h, m = map(int, time_str.split(":"))
            return datetime(target_date.year, target_date.month, target_date.day, h, m)
        except (ValueError, AttributeError):
            return datetime.now()
