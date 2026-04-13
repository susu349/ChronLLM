import json
import httpx
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from app.database import SessionLocal
from app.models import Event, Priority
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


TASK_SPLITTER_PROMPT = """你是"小管"，少爷的私人AI管家兼时间管理专家。

性格：专业、高效、关心少爷的时间安排。

职责：当少爷提出一个大任务时，将其智能拆分成多个可执行的子任务。

判断大任务的标准：
- 任务时长预计超过 2 小时
- 任务内容复杂，需要多个步骤完成
- 任务需要跨多天完成

拆分子任务的原则：
1. 每个子任务时长 30-90 分钟，避免过长或过短
2. 子任务之间要有合理的时间间隔（缓冲时间）
3. 考虑少爷的日常作息（从 preferences 获取）
4. 优先安排在工作效率高的时间段
5. 子任务之间逻辑连贯，有明确的递进关系
6. 重要的任务优先安排

返回 JSON 格式：
{
  "needs_split": true/false,  // 是否需要拆分
  "reason": "判断理由",
  "original_task": {
    "title": "原任务标题",
    "description": "原任务描述",
    "estimated_duration": 120  // 预估总时长（分钟）
  },
  "subtasks": [
    {
      "title": "子任务标题",
      "description": "子任务详细描述",
      "duration": 60,  // 时长（分钟）
      "priority": "high/medium/low",
      "suggested_date_offset": 0,  // 0=今天，1=明天，以此类推
      "suggested_time": "09:00"  // 建议开始时间
    }
  ]
}"""


@dataclass
class SubTask:
    """子任务数据结构"""
    title: str
    description: str
    duration: int
    priority: str
    suggested_date_offset: int
    suggested_time: str


@dataclass
class SplitResult:
    """任务拆分结果"""
    needs_split: bool
    reason: str
    original_task: Dict[str, Any]
    subtasks: List[SubTask]


class TaskSplitter:
    """任务智能拆分器"""

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    async def analyze_and_split(
        self,
        user_message: str,
        user_preferences: Dict[str, Any]
    ) -> SplitResult:
        """分析用户输入并决定是否拆分任务"""

        prompt = f"""当前日期：{date.today().isoformat()}

少爷的日常习惯：
- 起床时间：{user_preferences.get('wake_up_time', '07:00')}
- 工作开始：{user_preferences.get('work_start_time', '09:00')}
- 午餐时间：{user_preferences.get('lunch_time', '12:00')}
- 工作结束：{user_preferences.get('work_end_time', '18:00')}
- 晚餐时间：{user_preferences.get('dinner_time', '18:30')}
- 睡觉时间：{user_preferences.get('bed_time', '23:00')}

少爷说：{user_message}

请分析这个任务是否需要拆分成多个子任务，按照要求返回JSON。"""

        if not LLM_API_KEY:
            return self._fallback_analysis(user_message)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                    json={
                        "model": LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": TASK_SPLITTER_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.7,
                    },
                    timeout=httpx.Timeout(60.0, connect=10.0),
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                content = self._extract_json(content)
                result_dict = json.loads(content)
                return self._dict_to_split_result(result_dict)
        except Exception as e:
            print(f"[任务拆分] LLM调用失败: {e}")
            return self._fallback_analysis(user_message)

    def _fallback_analysis(self, user_message: str) -> SplitResult:
        """简单的启发式分析（无 LLM 时使用）"""
        # 简单判断：如果提到"完成项目"、"准备考试"、"写报告"等复杂词汇，就建议拆分
        complex_keywords = [
            "项目", "考试", "报告", "论文", "策划", "方案",
            "准备", "完成", "整理", "复习", "学习", "工作",
        ]

        needs_split = any(keyword in user_message for keyword in complex_keywords)

        if needs_split:
            return SplitResult(
                needs_split=True,
                reason="这个任务看起来比较复杂，建议拆分成多个步骤",
                original_task={
                    "title": user_message[:30] + "..." if len(user_message) > 30 else user_message,
                    "description": user_message,
                    "estimated_duration": 180,
                },
                subtasks=[
                    SubTask(
                        title="第一步：规划与准备",
                        description="制定详细的执行计划",
                        duration=30,
                        priority="high",
                        suggested_date_offset=0,
                        suggested_time="09:00",
                    ),
                    SubTask(
                        title="第二步：核心执行",
                        description="完成主要工作内容",
                        duration=60,
                        priority="high",
                        suggested_date_offset=0,
                        suggested_time="10:00",
                    ),
                    SubTask(
                        title="第三步：检查与完善",
                        description="检查成果并完善细节",
                        duration=30,
                        priority="medium",
                        suggested_date_offset=0,
                        suggested_time="11:30",
                    ),
                ],
            )
        else:
            return SplitResult(
                needs_split=False,
                reason="这个任务比较简单，可以直接安排",
                original_task={
                    "title": user_message[:30] + "..." if len(user_message) > 30 else user_message,
                    "description": user_message,
                    "estimated_duration": 60,
                },
                subtasks=[],
            )

    def _extract_json(self, text: str) -> str:
        """从文本中提取 JSON"""
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

    def _dict_to_split_result(self, data: Dict) -> SplitResult:
        """将字典转换为 SplitResult 对象"""
        subtasks = []
        for st_data in data.get("subtasks", []):
            subtasks.append(SubTask(
                title=st_data.get("title", ""),
                description=st_data.get("description", ""),
                duration=int(st_data.get("duration", 60)),
                priority=st_data.get("priority", "medium"),
                suggested_date_offset=int(st_data.get("suggested_date_offset", 0)),
                suggested_time=st_data.get("suggested_time", "09:00"),
            ))

        return SplitResult(
            needs_split=data.get("needs_split", False),
            reason=data.get("reason", ""),
            original_task=data.get("original_task", {}),
            subtasks=subtasks,
        )

    def preview_subtasks(self, split_result: SplitResult) -> List[Dict]:
        """生成子任务预览数据"""
        result = []
        today = date.today()
        for i, subtask in enumerate(split_result.subtasks):
            target_date = today + timedelta(days=subtask.suggested_date_offset)
            result.append({
                "index": i + 1,
                "title": subtask.title,
                "description": subtask.description,
                "duration": subtask.duration,
                "priority": subtask.priority,
                "date": target_date.isoformat(),
                "time": subtask.suggested_time,
            })
        return result

    def save_subtasks(self, split_result: SplitResult) -> List[Event]:
        """保存确认的子任务到数据库"""
        saved_events = []
        today = date.today()

        for subtask in split_result.subtasks:
            try:
                target_date = today + timedelta(days=subtask.suggested_date_offset)
                time_parts = subtask.suggested_time.split(":")
                start_datetime = datetime.combine(
                    target_date,
                    datetime.strptime(subtask.suggested_time, "%H:%M").time()
                )
                end_datetime = start_datetime + timedelta(minutes=subtask.duration)
                priority = Priority(subtask.priority)

                event = Event(
                    title=subtask.title,
                    start_time=start_datetime,
                    end_time=end_datetime,
                    priority=priority,
                    description=subtask.description,
                    is_ai_scheduled=True,
                    is_split_task=True,
                )
                self.db.add(event)
                saved_events.append(event)
            except Exception as e:
                print(f"[任务拆分] 保存子任务失败: {e}")

        if saved_events:
            self.db.commit()
            # 刷新获取 ID
            for event in saved_events:
                self.db.refresh(event)

        return saved_events
