"""高级精细化日程规划器"""

import json
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from app.database import SessionLocal
from app.models import Event, Priority, Status, DayPlan
from app.services.preferences_service import PreferencesService


class TimeSlotType(str, Enum):
    CLASS = "class"           # 上课/工作
    STUDY = "study"           # 自习
    MEAL = "meal"             # 用餐
    REST = "rest"             # 休息
    EXERCISE = "exercise"     # 运动
    COMMUTE = "commute"       # 通勤
    PERSONAL = "personal"     # 个人事务
    SLEEP = "sleep"           # 睡觉


@dataclass
class TimeSlot:
    """时间段"""
    start: time
    end: time
    type: TimeSlotType
    name: str = ""
    location: str = ""
    priority: Priority = Priority.medium
    is_fixed: bool = False  # 是否固定不可调整
    is_repeated: bool = False  # 是否重复（每周）
    day_of_week: Optional[int] = None  # 周几（0=周一）


class AdvancedScheduler:
    """高级精细化日程规划器"""

    def __init__(self):
        self.db = SessionLocal()
        self.prefs = PreferencesService()
        self.user_profile = self._load_user_profile()
        self.fixed_schedule = self._load_fixed_schedule()
        self.daily_routines = self._load_daily_routines()

    def close(self):
        self.db.close()
        self.prefs.close()

    def _load_user_profile(self) -> Dict[str, Any]:
        """加载用户详细资料（从偏好设置）"""
        prefs = self.prefs.get_all()

        profile = {
            "profile_type": prefs.get("user_identity", "student"),
            "wake_up_time": prefs.get("wake_up_time", "07:00"),
            "sleep_time": prefs.get("bed_time", "23:00"),
            "breakfast_time": prefs.get("breakfast_time", "07:30"),
            "lunch_time": prefs.get("lunch_time", "12:00"),
            "dinner_time": prefs.get("dinner_time", "18:30"),
            "work_start_time": prefs.get("work_start_time", "09:00"),
            "work_end_time": prefs.get("work_end_time", "18:00"),
            "buffer_minutes": int(prefs.get("buffer_minutes", "15")),
            "work_block": int(prefs.get("preferred_work_block", "60")),
            "include_exercise": prefs.get("include_exercise", "true") == "true",
            "exercise_duration": int(prefs.get("exercise_duration", "45")),
            "exercise_time": prefs.get("exercise_time", "evening"),
            "deep_work_first": prefs.get("deep_work_first", "true") == "true",
            "work_label": prefs.get("work_label", "工作"),
        }

        # 学生特定配置
        if profile["profile_type"] == "student":
            profile.update({
                "school_name": "燕山大学",
                "school_location": "河北省秦皇岛市",
                "commute_time": 20,
            })

        return profile

    def _load_fixed_schedule(self) -> List[TimeSlot]:
        """加载固定课程表/日程"""
        # 默认燕山大学学生课程表示例
        # 实际使用时可从数据库加载
        default_classes = [
            # 周一
            TimeSlot(time(8, 0), time(9, 40), TimeSlotType.CLASS, "高等数学", "第一教学楼A101", Priority.high, True, True, 0),
            TimeSlot(time(10, 0), time(11, 40), TimeSlotType.CLASS, "大学英语", "第二教学楼B202", Priority.high, True, True, 0),
            # 周二
            TimeSlot(time(8, 0), time(9, 40), TimeSlotType.CLASS, "大学物理", "第三教学楼C303", Priority.high, True, True, 1),
            TimeSlot(time(14, 0), time(15, 40), TimeSlotType.CLASS, "程序设计", "计算机楼D404", Priority.high, True, True, 1),
            # 周三
            TimeSlot(time(10, 0), time(11, 40), TimeSlotType.CLASS, "线性代数", "第一教学楼A101", Priority.high, True, True, 2),
            # 周四
            TimeSlot(time(8, 0), time(9, 40), TimeSlotType.CLASS, "工程制图", "第二教学楼B202", Priority.high, True, True, 3),
            TimeSlot(time(14, 0), time(15, 40), TimeSlotType.CLASS, "体育", "体育馆", Priority.medium, True, True, 3),
            # 周五
            TimeSlot(time(8, 0), time(9, 40), TimeSlotType.CLASS, "思想品德", "第三教学楼C303", Priority.medium, True, True, 4),
        ]
        return default_classes

    def _load_daily_routines(self) -> Dict[str, List[TimeSlot]]:
        """加载每日作息模板"""
        # 工作日模板
        weekday_routine = [
            TimeSlot(time(7, 0), time(7, 30), TimeSlotType.PERSONAL, "起床洗漱", "", Priority.low, True),
            TimeSlot(time(7, 30), time(8, 0), TimeSlotType.MEAL, "早餐", "", Priority.medium, True),
            TimeSlot(time(12, 0), time(12, 40), TimeSlotType.MEAL, "午餐", "", Priority.medium, True),
            TimeSlot(time(17, 40), time(18, 20), TimeSlotType.MEAL, "晚餐", "", Priority.medium, True),
            TimeSlot(time(22, 0), time(23, 0), TimeSlotType.PERSONAL, "睡前准备", "", Priority.low, True),
            TimeSlot(time(23, 0), time(7, 0), TimeSlotType.SLEEP, "睡眠", "", Priority.low, True),
        ]

        # 周末模板
        weekend_routine = [
            TimeSlot(time(7, 30), time(8, 0), TimeSlotType.PERSONAL, "起床洗漱", "", Priority.low, True),
            TimeSlot(time(8, 0), time(8, 30), TimeSlotType.MEAL, "早餐", "", Priority.medium, True),
            TimeSlot(time(12, 0), time(13, 0), TimeSlotType.MEAL, "午餐", "", Priority.medium, True),
            TimeSlot(time(18, 0), time(19, 0), TimeSlotType.MEAL, "晚餐", "", Priority.medium, True),
            TimeSlot(time(22, 30), time(23, 30), TimeSlotType.PERSONAL, "睡前准备", "", Priority.low, True),
            TimeSlot(time(23, 30), time(7, 30), TimeSlotType.SLEEP, "睡眠", "", Priority.low, True),
        ]

        return {
            "weekday": weekday_routine,
            "weekend": weekend_routine,
        }

    def get_available_slots(self, target_date: date) -> List[Dict[str, Any]]:
        """获取指定日期的可用时间段"""
        weekday = target_date.weekday()
        is_weekend = weekday >= 5

        # 获取固定课程
        fixed_classes = [
            slot for slot in self.fixed_schedule
            if slot.is_repeated and slot.day_of_week == weekday
        ]

        # 获取作息模板
        routine = self.daily_routines["weekend" if is_weekend else "weekday"]

        # 合并所有固定时段
        all_fixed = fixed_classes + routine

        # 找出可用时段
        available = []
        current_time = time(0, 0)

        # 按开始时间排序
        all_fixed.sort(key=lambda x: x.start)

        for slot in all_fixed:
            if current_time < slot.start:
                available.append({
                    "start": current_time.strftime("%H:%M"),
                    "end": slot.start.strftime("%H:%M"),
                    "duration": self._time_diff_minutes(current_time, slot.start),
                })
            current_time = max(current_time, slot.end)

        # 添加最后一个可用时段
        if current_time < time(23, 59):
            available.append({
                "start": current_time.strftime("%H:%M"),
                "end": "23:59",
                "duration": self._time_diff_minutes(current_time, time(23, 59)),
            })

        return available

    def _time_diff_minutes(self, t1: time, t2: time) -> int:
        """计算两个时间差（分钟）"""
        dt1 = datetime.combine(date.today(), t1)
        dt2 = datetime.combine(date.today(), t2)
        if dt2 < dt1:
            dt2 += timedelta(days=1)
        return int((dt2 - dt1).total_seconds() // 60)

    def generate_day_plan(self, target_date: date, events: List[Event]) -> List[Dict[str, Any]]:
        """
        生成一天的精细化规划

        Args:
            target_date: 目标日期
            events: 已有事件列表

        Returns:
            完整的一天规划
        """
        weekday = target_date.weekday()

        # 1. 获取固定课程和作息
        plan = []

        # 添加固定课程
        for slot in self.fixed_schedule:
            if slot.is_repeated and slot.day_of_week == weekday:
                plan.append({
                    "start_time": slot.start.strftime("%H:%M"),
                    "end_time": slot.end.strftime("%H:%M"),
                    "title": slot.name,
                    "description": slot.location,
                    "priority": slot.priority.value,
                    "category": slot.type.value,
                    "is_fixed": True,
                })

        # 2. 加入用户事件（排除固定课程时间）
        for event in events:
            if event.start_time.date() == target_date:
                plan.append({
                    "start_time": event.start_time.strftime("%H:%M"),
                    "end_time": event.end_time.strftime("%H:%M"),
                    "title": event.title,
                    "description": event.description,
                    "priority": event.priority.value,
                    "category": "work" if event.priority in [Priority.high, Priority.urgent] else "personal",
                    "is_fixed": False,
                })

        # 3. 智能填充可用时间
        filled_slots = self._smart_fill_available_time(target_date)
        plan.extend(filled_slots)

        # 4. 排序并返回
        plan.sort(key=lambda x: x["start_time"])
        return plan

    def _smart_fill_available_time(self, target_date: date) -> List[Dict[str, Any]]:
        """智能填充可用时间段"""
        weekday = target_date.weekday()
        is_weekend = weekday >= 5
        profile = self.user_profile

        filled = []

        # 解析起床和睡觉时间
        wake_up = time(*map(int, profile["wake_up_time"].split(":")))
        bed_time = time(*map(int, profile["sleep_time"].split(":")))

        # 基础作息填充
        if not is_weekend:
            # 工作日
            filled = self._fill_weekday_routine(profile)
        else:
            # 周末
            filled = self._fill_weekend_routine(profile)

        # 添加运动时间
        if profile["include_exercise"]:
            exercise_slot = self._get_exercise_slot(profile)
            if exercise_slot:
                filled.append(exercise_slot)

        return filled

    def _fill_weekday_routine(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """填充工作日作息"""
        routine = []
        work_label = profile["work_label"]

        # 起床
        wake_up = time(*map(int, profile["wake_up_time"].split(":")))
        routine.append({
            "start_time": wake_up.strftime("%H:%M"),
            "end_time": (datetime.combine(date.today(), wake_up) + timedelta(minutes=15)).time().strftime("%H:%M"),
            "title": "起床洗漱",
            "description": "起床、拉伸、洗漱",
            "priority": "low",
            "category": "personal",
            "is_fixed": True,
        })

        # 早餐
        breakfast = time(*map(int, profile["breakfast_time"].split(":")))
        routine.append({
            "start_time": breakfast.strftime("%H:%M"),
            "end_time": (datetime.combine(date.today(), breakfast) + timedelta(minutes=30)).time().strftime("%H:%M"),
            "title": "早餐",
            "description": "营养早餐时间",
            "priority": "medium",
            "category": "meal",
            "is_fixed": True,
        })

        # 工作开始前准备
        work_start = time(*map(int, profile["work_start_time"].split(":")))
        prep_end = work_start
        prep_start = (datetime.combine(date.today(), prep_end) - timedelta(minutes=30)).time()
        if prep_start > breakfast:
            routine.append({
                "start_time": prep_start.strftime("%H:%M"),
                "end_time": prep_end.strftime("%H:%M"),
                "title": "通勤/准备",
                "description": f"前往{work_label}地点或准备开始",
                "priority": "medium",
                "category": "commute",
                "is_fixed": True,
            })

        # 午餐
        lunch = time(*map(int, profile["lunch_time"].split(":")))
        routine.append({
            "start_time": lunch.strftime("%H:%M"),
            "end_time": (datetime.combine(date.today(), lunch) + timedelta(minutes=40)).time().strftime("%H:%M"),
            "title": "午餐",
            "description": "享用午餐",
            "priority": "medium",
            "category": "meal",
            "is_fixed": True,
        })

        # 午休
        nap_start = (datetime.combine(date.today(), lunch) + timedelta(minutes=40)).time()
        routine.append({
            "start_time": nap_start.strftime("%H:%M"),
            "end_time": (datetime.combine(date.today(), nap_start) + timedelta(minutes=30)).time().strftime("%H:%M"),
            "title": "午休",
            "description": "小憩或冥想",
            "priority": "medium",
            "category": "rest",
            "is_fixed": True,
        })

        # 晚餐
        dinner = time(*map(int, profile["dinner_time"].split(":")))
        routine.append({
            "start_time": dinner.strftime("%H:%M"),
            "end_time": (datetime.combine(date.today(), dinner) + timedelta(minutes=40)).time().strftime("%H:%M"),
            "title": "晚餐",
            "description": "享用晚餐",
            "priority": "medium",
            "category": "meal",
            "is_fixed": True,
        })

        # 睡前准备
        bed = time(*map(int, profile["sleep_time"].split(":")))
        bedtime_prep = (datetime.combine(date.today(), bed) - timedelta(minutes=45)).time()
        routine.append({
            "start_time": bedtime_prep.strftime("%H:%M"),
            "end_time": bed.strftime("%H:%M"),
            "title": "睡前准备",
            "description": "洗漱、放松、准备睡觉",
            "priority": "low",
            "category": "personal",
            "is_fixed": True,
        })

        return routine

    def _fill_weekend_routine(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """填充周末作息（更宽松）"""
        routine = []

        # 周末起床晚一点
        wake_up = time(*map(int, profile["wake_up_time"].split(":")))
        weekend_wake = (datetime.combine(date.today(), wake_up) + timedelta(minutes=30)).time()

        routine.append({
            "start_time": weekend_wake.strftime("%H:%M"),
            "end_time": (datetime.combine(date.today(), weekend_wake) + timedelta(minutes=20)).time().strftime("%H:%M"),
            "title": "起床洗漱",
            "description": "轻松的早晨",
            "priority": "low",
            "category": "personal",
            "is_fixed": True,
        })

        # 早餐
        breakfast = time(*map(int, profile["breakfast_time"].split(":")))
        weekend_breakfast = (datetime.combine(date.today(), breakfast) + timedelta(minutes=30)).time()
        routine.append({
            "start_time": weekend_breakfast.strftime("%H:%M"),
            "end_time": (datetime.combine(date.today(), weekend_breakfast) + timedelta(minutes=40)).time().strftime("%H:%M"),
            "title": "早餐",
            "description": "悠闲的早餐时间",
            "priority": "medium",
            "category": "meal",
            "is_fixed": True,
        })

        # 午餐
        lunch = time(12, 30)
        routine.append({
            "start_time": lunch.strftime("%H:%M"),
            "end_time": (datetime.combine(date.today(), lunch) + timedelta(minutes=50)).time().strftime("%H:%M"),
            "title": "午餐",
            "description": "享用午餐",
            "priority": "medium",
            "category": "meal",
            "is_fixed": True,
        })

        # 晚餐
        dinner = time(18, 30)
        routine.append({
            "start_time": dinner.strftime("%H:%M"),
            "end_time": (datetime.combine(date.today(), dinner) + timedelta(minutes=50)).time().strftime("%H:%M"),
            "title": "晚餐",
            "description": "享用晚餐",
            "priority": "medium",
            "category": "meal",
            "is_fixed": True,
        })

        # 睡前准备
        bed = time(*map(int, profile["sleep_time"].split(":")))
        weekend_bed = (datetime.combine(date.today(), bed) + timedelta(minutes=30)).time()
        bedtime_prep = (datetime.combine(date.today(), weekend_bed) - timedelta(minutes=45)).time()
        routine.append({
            "start_time": bedtime_prep.strftime("%H:%M"),
            "end_time": weekend_bed.strftime("%H:%M"),
            "title": "睡前准备",
            "description": "洗漱、放松",
            "priority": "low",
            "category": "personal",
            "is_fixed": True,
        })

        return routine

    def _get_exercise_slot(self, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取运动时间段"""
        exercise_time = profile["exercise_time"]
        duration = profile["exercise_duration"]

        base_times = {
            "morning": time(7, 0),
            "noon": time(12, 30),
            "afternoon": time(16, 30),
            "evening": time(19, 0),
        }

        start = base_times.get(exercise_time, time(18, 0))
        end = (datetime.combine(date.today(), start) + timedelta(minutes=duration)).time()

        return {
            "start_time": start.strftime("%H:%M"),
            "end_time": end.strftime("%H:%M"),
            "title": "运动锻炼",
            "description": "保持身体健康",
            "priority": "high",
            "category": "exercise",
            "is_fixed": True,
        }

    def dynamic_replan(self, target_date: date, trigger: str, reason: str = "") -> Dict[str, Any]:
        """
        动态重新规划

        Args:
            target_date: 目标日期
            trigger: 触发原因 (new_event/completed_event/manual)
            reason: 详细原因

        Returns:
            重新规划结果
        """
        from sqlalchemy import func

        # 获取当天现有事件
        events = self.db.query(Event).filter(
            func.date(Event.start_time) == target_date
        ).order_by(Event.start_time).all()

        # 生成新规划
        new_plan = self.generate_day_plan(target_date, events)

        # 记录调整日志
        adjustment_log = {
            "date": target_date.isoformat(),
            "trigger": trigger,
            "reason": reason,
            "original_count": len(events),
            "new_count": len(new_plan),
            "timestamp": datetime.now().isoformat(),
        }

        return {
            "success": True,
            "plan": new_plan,
            "adjustment_log": adjustment_log,
        }

    def suggest_adjustments(self, target_date: date) -> List[Dict[str, Any]]:
        """
        智能建议调整

        Args:
            target_date: 目标日期

        Returns:
            调整建议列表
        """
        suggestions = []

        # 获取可用时段
        available = self.get_available_slots(target_date)

        # 检查是否有大块可用时间可以拆分
        for slot in available:
            if slot["duration"] > 120:  # 超过2小时
                suggestions.append({
                    "type": "split_large_slot",
                    "title": f"{slot['start']}-{slot['end']} 有大块时间",
                    "suggestion": "建议拆分为多个学习时段，中间安排休息",
                    "priority": "medium",
                })

        # 检查是否有时间过紧
        from sqlalchemy import func
        events = self.db.query(Event).filter(
            func.date(Event.start_time) == target_date
        ).order_by(Event.start_time).all()

        for i in range(len(events) - 1):
            gap = (events[i+1].start_time - events[i].end_time).total_seconds() // 60
            if gap < 10:
                suggestions.append({
                    "type": "tight_schedule",
                    "title": f"{events[i].title} 和 {events[i+1].title} 间隔过短",
                    "suggestion": f"当前只有 {gap} 分钟，建议增加缓冲时间",
                    "priority": "high",
                })

        return suggestions

    def set_user_profile(self, profile_data: Dict[str, Any]) -> bool:
        """设置用户详细资料"""
        try:
            self.user_profile.update(profile_data)
            return True
        except Exception as e:
            print(f"[高级规划器] 设置用户资料失败: {e}")
            return False

    def add_fixed_class(self, name: str, day_of_week: int,
                        start_time: str, end_time: str,
                        location: str = "", priority: str = "high") -> bool:
        """添加固定课程"""
        try:
            start = time(*map(int, start_time.split(":")))
            end = time(*map(int, end_time.split(":")))
            slot = TimeSlot(
                start=start,
                end=end,
                type=TimeSlotType.CLASS,
                name=name,
                location=location,
                priority=Priority(priority),
                is_fixed=True,
                is_repeated=True,
                day_of_week=day_of_week,
            )
            self.fixed_schedule.append(slot)
            return True
        except Exception as e:
            print(f"[高级规划器] 添加课程失败: {e}")
            return False

    def save_plan(self, target_date: date, plan: List[Dict[str, Any]], is_auto: bool = False) -> DayPlan:
        """保存规划到数据库"""
        date_str = target_date.isoformat()
        plan_data = {
            "schedule": plan,
            "summary": f"{date_str} 的精细化规划，共 {len(plan)} 个时段"
        }

        existing = self.db.query(DayPlan).filter(DayPlan.date == date_str).first()
        if existing:
            existing.ai_summary = plan_data["summary"]
            existing.detailed_plan = json.dumps(plan_data, ensure_ascii=False)
            existing.is_auto_generated = is_auto
        else:
            day_plan = DayPlan(
                date=date_str,
                ai_summary=plan_data["summary"],
                detailed_plan=json.dumps(plan_data, ensure_ascii=False),
                is_auto_generated=is_auto,
            )
            self.db.add(day_plan)

        self.db.commit()
        return existing or day_plan

    def get_plan(self, target_date: date) -> Optional[Dict[str, Any]]:
        """获取指定日期的规划"""
        date_str = target_date.isoformat()
        record = self.db.query(DayPlan).filter(DayPlan.date == date_str).first()
        if record and record.detailed_plan:
            try:
                return json.loads(record.detailed_plan)
            except json.JSONDecodeError:
                pass
        return None

    def apply_plan_to_events(self, target_date: date, plan: Dict[str, Any]) -> List[Event]:
        """将规划应用到事件表"""
        schedule = plan.get("schedule", []) if isinstance(plan, dict) else plan
        created_events = []

        for item in schedule:
            try:
                start_h, start_m = map(int, item["start_time"].split(":"))
                end_h, end_m = map(int, item["end_time"].split(":"))
                start = datetime.combine(target_date, time(start_h, start_m))
                end = datetime.combine(target_date, time(end_h, end_m))

                # 跳过过去的事件
                if end < datetime.now():
                    continue

                priority = Priority(item.get("priority", "medium"))
                event = Event(
                    title=item["title"],
                    description=item.get("description", ""),
                    start_time=start,
                    end_time=end,
                    priority=priority,
                    status=Status.pending,
                    is_ai_scheduled=True,
                )
                self.db.add(event)
                created_events.append(event)
            except Exception as e:
                print(f"[高级规划器] 跳过无效时段: {item}, 错误: {e}")

        self.db.commit()
        return created_events

    def get_today_events(self, target_date: date) -> List[Event]:
        """获取指定日期的事件"""
        from sqlalchemy import func
        return (
            self.db.query(Event)
            .filter(func.date(Event.start_time) == target_date)
            .order_by(Event.start_time)
            .all()
        )

    async def generate_and_save_plan(self, target_date: Optional[date] = None, auto_apply: bool = True) -> Dict[str, Any]:
        """生成并保存完整规划"""
        if target_date is None:
            target_date = date.today()

        # 获取当天事件
        events = self.get_today_events(target_date)

        # 生成规划
        plan = self.generate_day_plan(target_date, events)

        # 保存
        self.save_plan(target_date, plan, is_auto=True)

        # 应用到事件表
        created_events = []
        if auto_apply:
            created_events = self.apply_plan_to_events(target_date, plan)

        return {
            "date": target_date.isoformat(),
            "plan": plan,
            "events_created": len(created_events),
        }
