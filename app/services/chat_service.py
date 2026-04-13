import json
import httpx

from app.database import SessionLocal
from app.models import Event, Priority
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from datetime import date, datetime, timedelta


SYSTEM_PROMPT = """你是"小管"，少爷的私人AI管家兼人生导师。

性格设定：
- 像父母溺爱孩子一样关心少爷的方方面面
- 温柔、体贴、无微不至，有时候会有点啰嗦
- 无论少爷问什么生活琐事，都要认真回答
- 会主动提醒少爷注意身体、注意安全、注意各种事项

职责范围：
1. 从自然语言中提取日程安排
2. 回答少爷的各种生活问题（比如：多少岁可以办身份证、怎么办银行卡、去哪里打针等等）
3. 主动关心未安排的时间段
4. 给出贴心的建议和提醒

回复风格：
- 始终称呼用户为"少爷"
- 回答要详细、贴心，像父母一样叮嘱
- 如果是日程安排，按下面的JSON格式返回
- 如果是问答，在reply中给出详细回答，events为空数组

规则：
- 如果没说具体时间，给出合理建议
- 优先级：urgent/high/medium/low，自动判断
- 日期识别：今天/明天/后天/周X/下周一等
- 时长估算：会议30-60min、吃饭60min、健身90min、就医120min等

返回纯JSON，无代码块：
{"reply":"管家回复","events":[{"title":"事件","start_time":"HH:MM","date_offset":0,"duration":60,"priority":"medium","description":""}]}

date_offset: 0=今天, 1=明天, 2=后天, 以此类推。如果没说日期，根据上下文推断。"""


class ChatService:
    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def _get_today_events_text(self) -> str:
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

    async def chat(self, user_message: str) -> dict:
        today_events = self._get_today_events_text()

        prompt = f"""当前日期：{date.today().isoformat()} ({self._weekday_cn(date.today())})
今日已有事件：
{today_events}

少爷说：{user_message}

请回复JSON。"""

        if not LLM_API_KEY:
            return self._fallback_reply(user_message)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                    json={
                        "model": LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.5,
                    },
                    timeout=httpx.Timeout(120.0, connect=10.0),
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                content = self._extract_json(content)
                return json.loads(content)
        except Exception as e:
            print(f"[对话] LLM调用失败: {e}")
            return self._fallback_reply(user_message)

    def _extract_json(self, text: str) -> str:
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

    def _fallback_reply(self, user_message: str) -> dict:
        return {
            "reply": "少爷，请开启LLM API后我才能更好地服务。您可以直接说「上午9点开会」或「下午健身」，我会自动为您安排。",
            "events": [],
        }

    def save_events(self, events_data: list[dict]) -> list[dict]:
        """批量保存从对话中提取的事件，一次性 commit"""
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
                print(f"[对话] 解析事件失败: {e}, 数据: {ev}")

        # 一次性提交所有事件
        if saved:
            self.db.commit()
            # 刷新以获取ID
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
        """解析 MM/DD + HH:MM 为 datetime"""
        try:
            m, d = map(int, date_str.split("/"))
            h, mi = map(int, time_str.split(":"))
            return datetime(date.today().year, m, d, h, mi)
        except (ValueError, AttributeError):
            return datetime.now()

    def _parse_time(self, time_str: str, target_date: date) -> datetime:
        if "T" in time_str:
            return datetime.fromisoformat(time_str)
        try:
            h, m = map(int, time_str.split(":"))
            return datetime(target_date.year, target_date.month, target_date.day, h, m)
        except (ValueError, AttributeError):
            return datetime.now()

    @staticmethod
    def _weekday_cn(d: date) -> str:
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return days[d.weekday()]
