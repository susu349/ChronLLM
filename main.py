from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime, date, timedelta, time
from contextlib import asynccontextmanager
from sqlalchemy import func
import calendar
import asyncio
import json

from app.database import init_db, SessionLocal
from app.models import (
    Event, Priority, Status, Reminder, DayPlan,
    TriggerType
)
from app.services.event_service import EventService
from app.services.reminder_engine import ReminderEngine
from app.services.chat_service import ChatService
from app.services.ai_scheduler import AIScheduler
from app.services.settings_service import get_settings, save_settings
from app.services.sse_manager import get_sse_manager
from app.services.scheduler import get_scheduler
from app.services.preferences_service import PreferencesService, DEFAULT_PREFERENCES, IDENTITY_PRESETS, BUTLER_STYLES
from app.services.smart_butler import get_smart_butler
from app.services.proactive_butler import ProactiveButler
from app.services.note_service import NoteService
from app.services.trigger_service import TriggerManager
from app.services.smart_adjuster import SmartAdjuster
from app.services.auto_summarizer import AutoSummarizer
from app.services.weather_service import WeatherService
from app.services.plan_reviewer import PlanReviewer
from app.services.smart_chat_service import SmartChatService
from app.services.recipe_service import RecipeService
from app.services.advanced_scheduler import AdvancedScheduler
from config import DEFAULT_REMINDER_MINUTES


async def nightly_summary_task():
    """每日晚间总结（晚上23:30执行）- 完全自动"""
    print(f"[晚间总结] 开始执行: {datetime.now().isoformat()}")
    try:
        summarizer = AutoSummarizer()
        yesterday = date.today() - timedelta(days=1)
        daily_summary = summarizer.auto_generate_daily_summary(yesterday)

        print(f"[晚间总结] 完成: {daily_summary.overall_summary}")

        # 推送通知
        sse_manager = get_sse_manager()
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(
                sse_manager.broadcast("nightly_summary", {
                    "date": yesterday.isoformat(),
                    "summary": daily_summary.overall_summary,
                    "completion_rate": daily_summary.completion_rate,
                }),
                loop
            )
        except Exception:
            pass

        summarizer.close()
    except Exception as e:
        print(f"[晚间总结] 错误: {e}")


async def midnight_plan_task():
    """每日凌晨规划（00:30执行）- 完全自动"""
    print(f"[凌晨规划] 开始执行: {datetime.now().isoformat()}")
    try:
        # 生成当天规划
        scheduler = AIScheduler()
        today_str = date.today().isoformat()

        # 生成详细规划
        plan = await scheduler.generate_detailed_plan()
        if plan:
            scheduler.save_detailed_plan(today_str, plan, is_auto=True)
            scheduler.apply_plan_to_events(today_str, plan)
            print(f"[凌晨规划] 完成: {plan.get('summary', '')}")

            # 保存到记事板
            note_service = NoteService()
            note_service.create_planning_note(
                date_str=today_str,
                plan_content=plan,
                thinking_process="凌晨自动生成规划",
            )
            note_service.close()

            # 推送通知
            sse_manager = get_sse_manager()
            try:
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(
                    sse_manager.broadcast("plan_generated", {
                        "date": today_str,
                        "summary": plan.get("summary", "")
                    }),
                    loop
                )
            except Exception:
                pass

        scheduler.close()

        # 清理提醒引擎缓存
        if hasattr(app.state, 'reminder_engine'):
            app.state.reminder_engine.clear_caches()

    except Exception as e:
        print(f"[凌晨规划] 错误: {e}")


async def auto_plan_day():
    """每日中午自动规划任务（保留兼容）"""
    print(f"[中午规划] 开始执行: {datetime.now().isoformat()}")
    try:
        scheduler = AIScheduler()
        today_str = date.today().isoformat()

        # 检查今天是否已经规划过
        existing_plan = scheduler.get_plan(today_str)
        if existing_plan and existing_plan.is_auto_generated:
            print(f"[中午规划] 今天已有规划，跳过")
            scheduler.close()
            return

        # 生成详细规划
        plan = await scheduler.generate_detailed_plan()
        if plan:
            scheduler.save_detailed_plan(today_str, plan, is_auto=True)
            scheduler.apply_plan_to_events(today_str, plan)
            print(f"[中午规划] 完成: {plan.get('summary', '')}")

            sse_manager = get_sse_manager()
            try:
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(
                    sse_manager.broadcast("plan_generated", {
                        "date": today_str,
                        "summary": plan.get("summary", "")
                    }),
                    loop
                )
            except Exception:
                pass

        scheduler.close()
    except Exception as e:
        print(f"[中午规划] 错误: {e}")


@asynccontextmanager
async def lifespan(app):
    init_db()

    # 初始化默认触发器
    trigger_mgr = TriggerManager()
    trigger_mgr.setup_default_triggers()
    trigger_mgr.close()

    # 启动提醒引擎
    engine = ReminderEngine()
    engine.start()
    app.state.reminder_engine = engine

    # 启动定时任务调度器
    daily_scheduler = get_scheduler()
    # 每天凌晨00:30规划
    daily_scheduler.add_daily_job(0, 30, midnight_plan_task)
    # 每天晚上23:30总结
    daily_scheduler.add_daily_job(23, 30, nightly_summary_task)
    # 每天中午12:00规划（保留）
    daily_scheduler.add_daily_job(12, 0, auto_plan_day)
    daily_scheduler.start()

    yield

    engine.stop()
    daily_scheduler.stop()


app = FastAPI(title="AI管家 - 智能自动化版", lifespan=lifespan)
templates = Jinja2Templates(directory="app/templates")


# ============ Pages ============

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/recipes", response_class=HTMLResponse)
async def recipes_page(request: Request):
    return templates.TemplateResponse("recipes.html", {"request": request})


# ============ Chat API ============

class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(data: ChatRequest):
    # 新版智能聊天
    chat = SmartChatService()
    result = await chat.chat(data.message)
    saved = []
    if result.get("events") is not None:
        saved = chat.save_events(result["events"])
    chat.close()

    result["saved_events"] = saved
    return result


# ============ Proactive Butler API ============

@app.post("/api/butler/start")
async def butler_start():
    """开始主动管家对话"""
    butler = ProactiveButler()
    try:
        question = butler.start_conversation()
        return {
            "reply": question,
            "is_finished": False,
            "can_plan": False,
        }
    finally:
        butler.close()


@app.post("/api/butler/answer")
async def butler_answer(data: ChatRequest):
    """用户回答管家问题"""
    butler = ProactiveButler()
    try:
        result = butler.answer(data.message)

        # 如果规划完成，自动应用
        if result.get("can_plan") and result.get("plan"):
            plan = result["plan"]
            today_str = date.today().isoformat()

            # 保存规划
            scheduler = AIScheduler()
            scheduler.save_detailed_plan(today_str, plan, is_auto=False)

            # 应用到事件表
            created_events = butler.apply_plan(plan)
            result["saved_events"] = [
                {
                    "id": e.id,
                    "title": e.title,
                    "start": e.start_time.strftime("%H:%M"),
                    "end": e.end_time.strftime("%H:%M"),
                    "date": e.start_time.strftime("%m/%d"),
                }
                for e in created_events
            ]
            scheduler.close()

        return result
    finally:
        butler.close()


@app.get("/api/butler/summary")
async def butler_summary():
    """获取当前对话摘要"""
    butler = ProactiveButler()
    try:
        return butler.get_conversation_summary()
    finally:
        butler.close()


@app.post("/api/butler/reset")
async def butler_reset():
    """重置管家对话"""
    butler = ProactiveButler()
    butler.reset()
    butler.close()
    return {"ok": True}


# ============ Timeline API ============

@app.get("/api/timeline")
async def get_timeline(year: int | None = None, month: int | None = None, day: int | None = None):
    db = SessionLocal()
    try:
        query = db.query(Event)

        if year:
            start = datetime(year, 1, 1)
            end = datetime(year, 12, 31, 23, 59, 59)
            query = query.filter(Event.start_time >= start, Event.start_time <= end)

        if year and month:
            last_day = calendar.monthrange(year, month)[1]
            start = datetime(year, month, 1)
            end = datetime(year, month, last_day, 23, 59, 59)
            query = query.filter(Event.start_time >= start, Event.start_time <= end)

        if year and month and day:
            target = datetime(year, month, day)
            next_day = target + timedelta(days=1)
            query = query.filter(Event.start_time >= target, Event.start_time < next_day)

        events = query.order_by(Event.start_time).all()

        result = []
        for e in events:
            result.append({
                "id": e.id,
                "title": e.title,
                "date": e.start_time.strftime("%Y-%m-%d"),
                "time": e.start_time.strftime("%H:%M"),
                "end": e.end_time.strftime("%H:%M"),
                "priority": e.priority.value,
                "status": e.status.value,
                "description": e.description,
                "is_ai_scheduled": e.is_ai_scheduled,
            })
        return result
    finally:
        db.close()


@app.get("/api/events/{event_id}")
async def get_event(event_id: int):
    """获取单个事件详情"""
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if event:
            import json
            participants = []
            if event.participants:
                try:
                    participants = json.loads(event.participants)
                except:
                    participants = [p.strip() for p in event.participants.split(',') if p.strip()]
            task_steps = []
            if event.task_steps:
                try:
                    task_steps = json.loads(event.task_steps)
                except:
                    task_steps = [s.strip() for s in event.task_steps.split('\n') if s.strip()]
            return {
                "id": event.id,
                "title": event.title,
                "description": event.description,
                "date": event.start_time.strftime("%Y-%m-%d"),
                "start_time": event.start_time.strftime("%H:%M"),
                "end_time": event.end_time.strftime("%H:%M"),
                "priority": event.priority.value,
                "status": event.status.value,
                "location": event.location or "",
                "participants": participants,
                "task_steps": task_steps,
                "notes": event.notes or "",
                "category": event.category or "",
                "is_ai_scheduled": event.is_ai_scheduled,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
        return None
    finally:
        db.close()


@app.get("/api/timeline/structure")
async def get_timeline_structure(year: int | None = None, month: int | None = None):
    """返回时间线树形结构: 年 → 月 → 日(event_count)"""
    db = SessionLocal()
    try:
        if year:
            query = db.query(Event).filter(
                func.extract("year", Event.start_time) == year
            )
        else:
            query = db.query(Event)

        events = query.all()

        # Build tree
        tree = {}
        for e in events:
            y = e.start_time.year
            m = e.start_time.month
            d = e.start_time.day
            if y not in tree:
                tree[y] = {}
            if m not in tree[y]:
                tree[y][m] = {}
            if d not in tree[y][m]:
                tree[y][m][d] = []
            tree[y][m][d].append({
                "id": e.id,
                "title": e.title,
                "time": e.start_time.strftime("%H:%M"),
                "priority": e.priority.value,
                "status": e.status.value,
            })

        return tree
    finally:
        db.close()


# ============ Event CRUD ============

class EventCreate(BaseModel):
    title: str
    start_time: str  # YYYY-MM-DD HH:MM or HH:MM
    duration_minutes: int = 30
    priority: str = "medium"
    description: str = ""
    location: str = ""
    participants: str = ""
    task_steps: str = ""
    notes: str = ""
    category: str = ""
    date: str | None = None


@app.post("/api/events")
async def create_event(data: EventCreate):
    service = EventService()
    try:
        # 处理日期和时间
        if data.date:
            # 使用指定日期
            target_date = date.fromisoformat(data.date)
            h, m = map(int, data.start_time.split(":"))
            start = datetime(target_date.year, target_date.month, target_date.day, h, m)
        elif "T" in data.start_time or " " in data.start_time:
            start = datetime.fromisoformat(data.start_time.replace(" ", "T") if "T" not in data.start_time else data.start_time)
        else:
            h, m = map(int, data.start_time.split(":"))
            start = datetime(date.today().year, date.today().month, date.today().day, h, m)
    except ValueError:
        start = datetime.now()

    end = start + timedelta(minutes=data.duration_minutes)

    # 智能判断优先级
    prio = Priority(data.priority)
    if prio == Priority.medium:
        title_lower = data.title.lower()
        if any(keyword in title_lower for keyword in ["紧急", "重要", "马上", "立刻", "urgent", "important"]):
            prio = Priority.high
        if any(keyword in title_lower for keyword in ["非常紧急", "十万火急", "critical"]):
            prio = Priority.urgent

    event = service.create_event(
        title=data.title, start_time=start, end_time=end,
        description=data.description, priority=prio,
        location=data.location, participants=data.participants,
        task_steps=data.task_steps, notes=data.notes,
        category=data.category,
    )

    # 自动创建触发器
    trigger_mgr = TriggerManager()
    trigger_mgr.create_event_reminder_trigger(event, minutes_before=10)
    trigger_mgr.create_event_end_trigger(event)
    trigger_mgr.close()

    service.close()
    return {"id": event.id, "title": event.title, "start": event.start_time.isoformat()}


@app.post("/api/events/{event_id}/complete")
async def complete_event(event_id: int):
    """标记事件完成 - 自动生成总结"""
    service = EventService()
    ok = service.complete_event(event_id)

    if ok:
        # 自动生成总结（不用少爷动手）
        db = SessionLocal()
        event = db.query(Event).filter(Event.id == event_id).first()
        db.close()

        if event:
            summarizer = AutoSummarizer()
            summarizer.auto_generate_event_summary(event)
            summarizer.close()

            # 自动调整后续日程
            adjuster = SmartAdjuster()
            adjustments = adjuster.auto_adjust_after_completion(event)
            adjuster.close()

            if adjustments:
                print(f"[智能调整] 已调整 {len(adjustments)} 个后续事件")

    service.close()
    return {"ok": ok}


@app.put("/api/events/{event_id}")
async def update_event(event_id: int, data: EventCreate):
    service = EventService()
    try:
        # 处理日期和时间
        if data.date:
            # 使用指定日期
            target_date = date.fromisoformat(data.date)
            h, m = map(int, data.start_time.split(":"))
            start = datetime(target_date.year, target_date.month, target_date.day, h, m)
        elif "T" in data.start_time or " " in data.start_time:
            start = datetime.fromisoformat(data.start_time.replace(" ", "T") if "T" not in data.start_time else data.start_time)
        else:
            h, m = map(int, data.start_time.split(":"))
            start = datetime(date.today().year, date.today().month, date.today().day, h, m)
    except ValueError:
        start = datetime.now()

    end = start + timedelta(minutes=data.duration_minutes)
    try:
        prio = Priority(data.priority)
    except ValueError:
        prio = Priority.medium

    # 准备更新数据
    update_data = {
        "title": data.title,
        "start_time": start,
        "end_time": end,
        "priority": prio,
        "description": data.description,
        "location": data.location,
        "notes": data.notes,
        "category": data.category,
    }

    # 处理 participants 和 task_steps
    import json
    db = SessionLocal()
    event = db.query(Event).filter(Event.id == event_id).first()
    if event:
        for key, value in update_data.items():
            setattr(event, key, value)

        # 处理 participants
        if data.participants:
            if data.participants.strip().startswith('['):
                event.participants = data.participants
            else:
                parts = [p.strip() for p in data.participants.split(',') if p.strip()]
                event.participants = json.dumps(parts, ensure_ascii=False)
        else:
            event.participants = ""

        # 处理 task_steps
        if data.task_steps:
            if data.task_steps.strip().startswith('['):
                event.task_steps = data.task_steps
            else:
                parts = [s.strip() for s in data.task_steps.split('\n') if s.strip()]
                event.task_steps = json.dumps(parts, ensure_ascii=False)
        else:
            event.task_steps = ""

        db.commit()
        db.refresh(event)
    db.close()
    service.close()
    return {"ok": event is not None}


@app.delete("/api/events/{event_id}")
async def delete_event(event_id: int):
    service = EventService()
    ok = service.delete_event(event_id)
    service.close()
    return {"ok": ok}


# ============ Event Summary API (Auto) ============

class EventSummaryRequest(BaseModel):
    completion_rate: int
    summary: str = ""
    reflection: str = ""
    obstacles: str = ""


@app.post("/api/events/{event_id}/summary")
async def create_event_summary(event_id: int, data: EventSummaryRequest):
    """创建事件总结（保留手动接口，但优先使用自动）"""
    service = NoteService()
    summary = service.create_event_summary(
        event_id=event_id,
        completion_rate=data.completion_rate,
        summary=data.summary,
        reflection=data.reflection,
        obstacles=data.obstacles,
    )
    result = service.to_dict(summary)
    service.close()
    return result


@app.get("/api/events/{event_id}/summary")
async def get_event_summary(event_id: int):
    """获取事件总结"""
    service = NoteService()
    summary = service.get_event_summary(event_id)
    result = service.to_dict(summary) if summary else None
    service.close()
    return result


# ============ Smart Adjust API ============

@app.post("/api/smart/reorder")
async def smart_reorder():
    """智能重新排序日程"""
    adjuster = SmartAdjuster()
    changes = adjuster.smart_reorder()
    adjuster.close()
    return {"changes": changes}


@app.get("/api/smart/suggestions")
async def get_smart_suggestions():
    """获取智能建议"""
    summarizer = AutoSummarizer()
    suggestions = summarizer.get_intelligent_suggestions()
    summarizer.close()
    return {"suggestions": suggestions}


# ============ Schedule ============

@app.post("/api/schedule")
async def schedule():
    scheduler = AIScheduler()
    result = await scheduler.generate_schedule()
    scheduler.close()
    if result:
        scheduler.save_day_plan(result)
    return result or {"summary": "无待编排事件", "events": []}


@app.get("/api/today")
async def today_summary():
    service = EventService()
    events = service.get_today_events()
    summary = {
        "total": len(events),
        "pending": sum(1 for e in events if e.status.value == "pending"),
        "active": sum(1 for e in events if e.status.value == "active"),
        "completed": sum(1 for e in events if e.status.value == "completed"),
    }
    service.close()
    return summary


@app.get("/api/greeting")
async def greeting():
    """管家主动打招呼 — 根据当前时间和今日安排"""
    settings = get_settings()
    user_name = settings.get("USER_NAME", "少爷")
    hour = datetime.now().hour
    if hour < 12:
        greet = f"{user_name}早上好"
    elif hour < 14:
        greet = f"{user_name}中午好"
    elif hour < 18:
        greet = f"{user_name}下午好"
    else:
        greet = f"{user_name}晚上好"

    service = EventService()
    events = service.get_today_events()

    if events:
        next_event = None
        for e in events:
            if e.start_time > datetime.now() and e.status.value in ("pending", "active"):
                next_event = e
                break

        if next_event:
            msg = f"{greet}。您下一个日程是 {next_event.start_time.strftime('%H:%M')} 的「{next_event.title}」"
        else:
            msg = f"{greet}。今日已有 {len(events)} 个安排"
    else:
        msg = f"{greet}。今天还没有安排，有什么需要我帮您规划的吗？"

    service.close()
    return {"message": msg}


# ============ Statistics ============

@app.get("/api/stats/weekly")
async def get_weekly_stats():
    """获取本周统计数据"""
    db = SessionLocal()
    try:
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week = start_of_week + timedelta(days=7)

        events = db.query(Event).filter(
            Event.start_time >= start_of_week,
            Event.start_time < end_of_week
        ).all()

        # 按天统计
        daily_stats = {}
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            day_key = day.strftime("%Y-%m-%d")
            daily_stats[day_key] = {
                "date": day_key,
                "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][day.weekday()],
                "total": 0,
                "completed": 0,
                "urgent": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            }

        for e in events:
            day_key = e.start_time.strftime("%Y-%m-%d")
            if day_key in daily_stats:
                daily_stats[day_key]["total"] += 1
                if e.status == Status.completed:
                    daily_stats[day_key]["completed"] += 1
                if e.priority == Priority.urgent:
                    daily_stats[day_key]["urgent"] += 1
                elif e.priority == Priority.high:
                    daily_stats[day_key]["high"] += 1
                elif e.priority == Priority.medium:
                    daily_stats[day_key]["medium"] += 1
                elif e.priority == Priority.low:
                    daily_stats[day_key]["low"] += 1

        # 汇总统计
        total_events = len(events)
        completed_events = sum(1 for e in events if e.status == Status.completed)
        completion_rate = round(completed_events / total_events * 100, 1) if total_events > 0 else 0

        return {
            "period_start": start_of_week.strftime("%Y-%m-%d"),
            "period_end": (end_of_week - timedelta(days=1)).strftime("%Y-%m-%d"),
            "summary": {
                "total": total_events,
                "completed": completed_events,
                "pending": total_events - completed_events,
                "completion_rate": completion_rate,
            },
            "daily": list(daily_stats.values()),
        }
    finally:
        db.close()


@app.get("/api/stats/monthly")
async def get_monthly_stats(year: int | None = None, month: int | None = None):
    """获取月度统计数据"""
    db = SessionLocal()
    try:
        now = datetime.now()
        target_year = year or now.year
        target_month = month or now.month

        start_date = datetime(target_year, target_month, 1)
        if target_month == 12:
            end_date = datetime(target_year + 1, 1, 1)
        else:
            end_date = datetime(target_year, target_month + 1, 1)

        events = db.query(Event).filter(
            Event.start_time >= start_date,
            Event.start_time < end_date
        ).all()

        # 按周统计
        weekly_stats = []
        current_week_start = start_date
        while current_week_start < end_date:
            week_end = current_week_start + timedelta(days=7)
            week_events = [e for e in events if current_week_start <= e.start_time < week_end]

            weekly_stats.append({
                "week_start": current_week_start.strftime("%m-%d"),
                "week_end": (min(week_end, end_date) - timedelta(days=1)).strftime("%m-%d"),
                "total": len(week_events),
                "completed": sum(1 for e in week_events if e.status == Status.completed),
            })

            current_week_start = week_end

        # 优先级分布
        priority_dist = {
            "urgent": sum(1 for e in events if e.priority == Priority.urgent),
            "high": sum(1 for e in events if e.priority == Priority.high),
            "medium": sum(1 for e in events if e.priority == Priority.medium),
            "low": sum(1 for e in events if e.priority == Priority.low),
        }

        total_events = len(events)
        completed_events = sum(1 for e in events if e.status == Status.completed)
        completion_rate = round(completed_events / total_events * 100, 1) if total_events > 0 else 0

        return {
            "year": target_year,
            "month": target_month,
            "summary": {
                "total": total_events,
                "completed": completed_events,
                "pending": total_events - completed_events,
                "completion_rate": completion_rate,
            },
            "priority_distribution": priority_dist,
            "weekly": weekly_stats,
        }
    finally:
        db.close()


# ============ Daily Plan ============

@app.post("/api/plan/generate")
async def generate_plan():
    """手动触发生成今日详细规划"""
    scheduler = AIScheduler()
    try:
        today_str = date.today().isoformat()
        plan = await scheduler.generate_detailed_plan()
        if plan:
            scheduler.save_detailed_plan(today_str, plan, is_auto=False)

            # 保存到记事板
            note_service = NoteService()
            note_service.create_planning_note(
                date_str=today_str,
                plan_content=plan,
                thinking_process="手动触发生成规划",
            )
            note_service.close()

        return plan or {"summary": "规划生成失败", "schedule": []}
    finally:
        scheduler.close()


@app.post("/api/plan/apply")
async def apply_plan():
    """应用今日规划到事件表"""
    scheduler = AIScheduler()
    try:
        today_str = date.today().isoformat()
        plan_record = scheduler.get_plan(today_str)
        if not plan_record or not plan_record.detailed_plan:
            return {"ok": False, "message": "没有可用的规划"}

        plan = json.loads(plan_record.detailed_plan)
        events = scheduler.apply_plan_to_events(today_str, plan)
        return {"ok": True, "events_created": len(events)}
    finally:
        scheduler.close()


@app.get("/api/plan")
async def get_plan(date_str: str | None = None):
    """获取指定日期的规划"""
    scheduler = AIScheduler()
    try:
        if not date_str:
            date_str = date.today().isoformat()
        plan_record = scheduler.get_plan(date_str)
        if plan_record:
            return {
                "date": plan_record.date,
                "summary": plan_record.ai_summary,
                "detailed_plan": json.loads(plan_record.detailed_plan) if plan_record.detailed_plan else None,
                "is_auto_generated": plan_record.is_auto_generated,
                "created_at": plan_record.created_at.isoformat(),
            }
        return None
    finally:
        scheduler.close()


@app.post("/api/plan/trigger-now")
async def trigger_plan_now():
    """立即触发自动规划（测试用）"""
    scheduler = get_scheduler()
    scheduler.run_now(midnight_plan_task)
    return {"ok": True, "message": "规划任务已启动"}


# ============ Notes API (记事板) ============

class NoteCreate(BaseModel):
    title: str
    content: str
    note_type: str = "general"
    tags: list[str] = []


@app.get("/api/notes")
async def get_notes(date_str: str | None = None, note_type: str | None = None):
    """获取笔记列表"""
    service = NoteService()
    try:
        if date_str:
            notes = service.get_notes_by_date(date_str, note_type)
        else:
            notes = service.get_recent_notes(50)
        return [service.to_dict(n) for n in notes]
    finally:
        service.close()


@app.post("/api/notes")
async def create_note(data: NoteCreate):
    """创建笔记"""
    service = NoteService()
    try:
        today_str = date.today().isoformat()
        note = service.create_note(
            date_str=today_str,
            title=data.title,
            content=data.content,
            note_type=data.note_type,
            tags=data.tags,
        )
        return service.to_dict(note)
    finally:
        service.close()


@app.get("/api/notes/{note_id}")
async def get_note(note_id: int):
    """获取单个笔记"""
    service = NoteService()
    try:
        note = service.db.query(service.db.query(Note).filter(Note.id == note_id).first())
        return service.to_dict(note) if note else None
    finally:
        service.close()


@app.put("/api/notes/{note_id}")
async def update_note(note_id: int, data: NoteCreate):
    """更新笔记"""
    service = NoteService()
    try:
        note = service.update_note(
            note_id,
            title=data.title,
            content=data.content,
            tags=data.tags,
        )
        return service.to_dict(note) if note else None
    finally:
        service.close()


@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: int):
    """删除笔记"""
    service = NoteService()
    ok = service.delete_note(note_id)
    service.close()
    return {"ok": ok}


@app.get("/api/notes/search/{keyword}")
async def search_notes(keyword: str):
    """搜索笔记"""
    service = NoteService()
    notes = service.search_notes(keyword)
    result = [service.to_dict(n) for n in notes]
    service.close()
    return result


# ============ Daily Summary API ============

@app.get("/api/summary/daily/{date_str}")
async def get_daily_summary_api(date_str: str):
    """获取每日总结"""
    service = NoteService()
    summary = service.get_daily_summary(date_str)
    result = service.to_dict(summary) if summary else None
    service.close()
    return result


# ============ Triggers API ============

class TriggerCreate(BaseModel):
    name: str
    trigger_type: str
    trigger_time: str | None = None
    event_id: int | None = None
    config: dict = {}
    is_enabled: bool = True


@app.get("/api/triggers")
async def get_triggers(only_enabled: bool = False):
    """获取所有触发器"""
    service = TriggerManager()
    triggers = service.get_all_triggers(only_enabled=only_enabled)
    result = [service.to_dict(t) for t in triggers]
    service.close()
    return result


@app.post("/api/triggers")
async def create_trigger(data: TriggerCreate):
    """创建触发器"""
    service = TriggerManager()
    try:
        trigger_type = TriggerType(data.trigger_type)
        trigger = service.create_trigger(
            name=data.name,
            trigger_type=trigger_type,
            trigger_time=data.trigger_time,
            event_id=data.event_id,
            config=data.config,
            is_enabled=data.is_enabled,
        )
        return service.to_dict(trigger)
    finally:
        service.close()


@app.put("/api/triggers/{trigger_id}")
async def update_trigger(trigger_id: int, data: TriggerCreate):
    """更新触发器"""
    service = TriggerManager()
    try:
        trigger = service.update_trigger(
            trigger_id,
            name=data.name,
            trigger_time=data.trigger_time,
            is_enabled=data.is_enabled,
            config=data.config,
        )
        return service.to_dict(trigger) if trigger else None
    finally:
        service.close()


@app.delete("/api/triggers/{trigger_id}")
async def delete_trigger(trigger_id: int):
    """删除触发器"""
    service = TriggerManager()
    ok = service.delete_trigger(trigger_id)
    service.close()
    return {"ok": ok}


@app.post("/api/triggers/{trigger_id}/toggle")
async def toggle_trigger(trigger_id: int):
    """切换触发器启用状态"""
    service = TriggerManager()
    trigger = service.toggle_trigger(trigger_id)
    result = service.to_dict(trigger) if trigger else None
    service.close()
    return result


# ============ Preferences ============

@app.get("/api/preferences")
async def get_preferences():
    """获取用户偏好设置"""
    service = PreferencesService()
    try:
        return service.get_all()
    finally:
        service.close()


# ============ Identity API ============

@app.get("/api/identity/presets")
async def get_identity_presets():
    """获取所有身份预设"""
    presets = {}
    for key, preset in IDENTITY_PRESETS.items():
        presets[key] = {
            "name": preset["name"],
            "description": preset["description"],
        }
    return presets


class IdentityApply(BaseModel):
    identity: str


@app.post("/api/identity/apply")
async def apply_identity(data: IdentityApply):
    """应用身份预设"""
    service = PreferencesService()
    try:
        ok = service.apply_identity_preset(data.identity)
        if ok:
            return {"ok": True, "preferences": service.get_all()}
        return {"ok": False, "message": "未知的身份预设"}
    finally:
        service.close()


# ============ Butler Style API ============

@app.get("/api/butler/styles")
async def get_butler_styles():
    """获取所有管家风格预设"""
    styles = {}
    for key, style in BUTLER_STYLES.items():
        styles[key] = {
            "name": style["name"],
            "description": style["description"],
            "emoji": style["emoji"],
            "color": style["color"],
        }
    return styles


class ButlerStyleApply(BaseModel):
    style: str


@app.post("/api/butler/style/apply")
async def apply_butler_style(data: ButlerStyleApply):
    """应用管家风格预设"""
    service = PreferencesService()
    try:
        settings = get_settings()
        user_name = settings.get("USER_NAME", "少爷")
        ok = service.apply_butler_style(data.style, user_name)
        if ok:
            return {"ok": True, "preferences": service.get_all()}
        return {"ok": False, "message": "未知的管家风格"}
    finally:
        service.close()


@app.get("/api/butler/style/config")
async def get_butler_style_config():
    """获取当前管家风格配置"""
    service = PreferencesService()
    try:
        style = service.get("butler_style", "classic")
        config = service.get_butler_style_config()
        return {
            "style": style,
            **config
        }
    finally:
        service.close()


# ============ Custom Identity & Butler Style API ============

class CustomIdentity(BaseModel):
    name: str
    description: str
    wake_up_time: str
    breakfast_time: str
    work_start_time: str
    lunch_time: str
    work_end_time: str
    dinner_time: str
    bed_time: str
    buffer_minutes: str
    preferred_work_block: str
    include_exercise: str
    exercise_duration: str
    exercise_time: str
    deep_work_first: str
    pomodoro_enabled: str
    work_label: str


@app.post("/api/identity/custom/save")
async def save_custom_identity(data: CustomIdentity):
    """保存自定义身份"""
    service = PreferencesService()
    try:
        config = data.model_dump()
        service.save_custom_identity(config)
        # 同时应用这个自定义身份
        for key, value in config.items():
            service.set(key, str(value))
        service.set("user_identity", "custom")
        return {"ok": True, "preferences": service.get_all()}
    finally:
        service.close()


@app.get("/api/identity/custom")
async def get_custom_identity():
    """获取自定义身份配置"""
    service = PreferencesService()
    try:
        return service.get_json("custom_identity", {})
    finally:
        service.close()


class CustomButlerStyle(BaseModel):
    name: str
    description: str
    greeting: str
    call_user: str
    self_call: str
    tone: str
    emoji: str
    color: str


@app.post("/api/butler/style/custom/save")
async def save_custom_butler_style(data: CustomButlerStyle):
    """保存自定义管家风格"""
    service = PreferencesService()
    try:
        config = data.model_dump()
        service.save_custom_butler_style(config)
        # 同时应用这个自定义风格
        for key, value in config.items():
            service.set(f"style_{key}", str(value))
        service.set("butler_style", "custom")
        return {"ok": True, "preferences": service.get_all()}
    finally:
        service.close()


@app.get("/api/butler/style/custom")
async def get_custom_butler_style():
    """获取自定义管家风格配置"""
    service = PreferencesService()
    try:
        return service.get_json("custom_butler_style", {})
    finally:
        service.close()


class PreferencesUpdate(BaseModel):
    user_identity: str = "worker"
    wake_up_time: str = "07:00"
    breakfast_time: str = "07:30"
    work_start_time: str = "09:00"
    lunch_time: str = "12:00"
    work_end_time: str = "18:00"
    dinner_time: str = "18:30"
    bed_time: str = "23:00"
    buffer_minutes: str = "15"
    preferred_work_block: str = "60"
    include_exercise: str = "true"
    exercise_duration: str = "45"
    exercise_time: str = "morning"
    deep_work_first: str = "true"
    pomodoro_enabled: str = "false"
    work_label: str = "工作"


@app.post("/api/preferences")
async def save_preferences(data: PreferencesUpdate):
    """保存用户偏好设置"""
    service = PreferencesService()
    try:
        service.set_batch(data.model_dump())
        return service.get_all()
    finally:
        service.close()


# ============ Settings ============

class SettingsUpdate(BaseModel):
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""
    DEFAULT_REMINDER_MINUTES: str = "10"
    USER_NAME: str = "少爷"


@app.get("/api/settings")
async def get_settings_api():
    return get_settings()


@app.post("/api/settings")
async def save_settings_api(data: SettingsUpdate):
    saved = save_settings(data.model_dump())
    return saved


# ============ SSE ============

async def sse_event_generator():
    sse_manager = get_sse_manager()
    queue = await sse_manager.connect()
    try:
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {__import__('json').dumps(message)}\n\n"
            except asyncio.TimeoutError:
                # 发送心跳保持连接
                yield ": heartbeat\n\n"
    finally:
        sse_manager.disconnect(queue)


@app.get("/api/sse")
async def sse_endpoint():
    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============ Weather API ============

@app.get("/api/weather")
async def get_weather(city: str | None = None):
    """获取天气信息"""
    service = WeatherService()
    try:
        weather = await service.get_weather(city)
        if weather:
            suggestion = service.get_weather_suggestion(weather)
            return {
                "ok": True,
                "weather": weather,
                "suggestion": suggestion,
                "is_configured": service.is_configured(),
            }
        else:
            return {
                "ok": False,
                "message": "天气API未配置或获取失败",
                "is_configured": service.is_configured(),
            }
    finally:
        pass


# ============ Recipe API ============

class RecipeCreate(BaseModel):
    name: str
    description: str = ""
    ingredients: list = []
    instructions: list = []
    prep_time: int = 0
    cook_time: int = 0
    servings: int = 2
    difficulty: str = "medium"
    tags: list = []
    cuisine: str = ""
    meal_type: str = "dinner"
    calories: int = 0
    protein: int = 0
    carbs: int = 0
    fat: int = 0
    fiber: int = 0


class MealPlanSave(BaseModel):
    week_start: str
    plan_data: dict


@app.get("/api/recipes")
async def get_recipes(meal_type: str | None = None, tag: str | None = None, cuisine: str | None = None):
    """获取食谱列表"""
    service = RecipeService()
    try:
        recipes = service.get_all_recipes(meal_type=meal_type, tag=tag, cuisine=cuisine)
        return [service.to_dict(r) for r in recipes]
    finally:
        service.close()


@app.get("/api/recipes/{recipe_id}")
async def get_recipe(recipe_id: int):
    """获取单个食谱详情"""
    service = RecipeService()
    try:
        recipe = service.get_recipe(recipe_id)
        return service.to_dict(recipe) if recipe else None
    finally:
        service.close()


@app.get("/api/recipes/search/{keyword}")
async def search_recipes(keyword: str):
    """搜索食谱"""
    service = RecipeService()
    try:
        recipes = service.search_recipes(keyword)
        return [service.to_dict(r) for r in recipes]
    finally:
        service.close()


@app.post("/api/recipes")
async def create_recipe(data: RecipeCreate):
    """添加自定义食谱"""
    service = RecipeService()
    try:
        recipe_data = data.model_dump()
        recipe_data["ingredients"] = json.dumps(recipe_data["ingredients"], ensure_ascii=False)
        recipe_data["instructions"] = json.dumps(recipe_data["instructions"], ensure_ascii=False)
        recipe_data["tags"] = ",".join(recipe_data["tags"]) if recipe_data["tags"] else ""
        recipe = service.add_custom_recipe(recipe_data)
        return service.to_dict(recipe)
    finally:
        service.close()


@app.delete("/api/recipes/{recipe_id}")
async def delete_recipe(recipe_id: int):
    """删除食谱"""
    service = RecipeService()
    try:
        ok = service.delete_recipe(recipe_id)
        return {"ok": ok}
    finally:
        service.close()


@app.get("/api/meal-plan/generate")
async def generate_meal_plan():
    """生成每周饮食计划"""
    service = RecipeService()
    try:
        plan = service.generate_weekly_plan()
        return plan
    finally:
        service.close()


@app.get("/api/meal-plan")
async def get_meal_plan():
    """获取保存的周计划"""
    service = RecipeService()
    try:
        return service.get_weekly_plan()
    finally:
        service.close()


@app.post("/api/meal-plan")
async def save_meal_plan(data: MealPlanSave):
    """保存周计划"""
    service = RecipeService()
    try:
        plan = service.save_weekly_plan(data.week_start, data.plan_data)
        return {"ok": True}
    finally:
        service.close()


# ============ Plan Review API ============

class PlanReviewRequest(BaseModel):
    plan: dict


# ============ Advanced Scheduler API ============

class AdvancedPlanGenerateRequest(BaseModel):
    date_str: str | None = None
    auto_apply: bool = True


class FixedClassAddRequest(BaseModel):
    name: str
    day_of_week: int
    start_time: str
    end_time: str
    location: str = ""
    priority: str = "high"


@app.post("/api/plan/review")
async def review_plan(data: PlanReviewRequest):
    """审查规划"""
    reviewer = PlanReviewer()
    try:
        passed, issues = reviewer.review(data.plan)
        summary = reviewer.get_summary(issues)
        return {
            "ok": True,
            "passed": passed,
            "summary": summary,
            "issues": reviewer.issues_to_dict(issues),
        }
    except Exception as e:
        return {
            "ok": False,
            "message": str(e),
        }


# ============ Advanced Scheduler API ============

@app.get("/api/advanced-plan/available-slots")
async def get_available_slots_api(date_str: str | None = None):
    """获取可用时间段"""
    scheduler = AdvancedScheduler()
    try:
        if date_str:
            target_date = date.fromisoformat(date_str)
        else:
            target_date = date.today()
        slots = scheduler.get_available_slots(target_date)
        return {"date": target_date.isoformat(), "slots": slots}
    finally:
        scheduler.close()


@app.post("/api/advanced-plan/generate")
async def generate_advanced_plan(data: AdvancedPlanGenerateRequest):
    """生成精细化日程规划"""
    scheduler = AdvancedScheduler()
    try:
        if data.date_str:
            target_date = date.fromisoformat(data.date_str)
        else:
            target_date = date.today()
        result = await scheduler.generate_and_save_plan(target_date, auto_apply=data.auto_apply)
        return result
    finally:
        scheduler.close()


@app.get("/api/advanced-plan")
async def get_advanced_plan_api(date_str: str | None = None):
    """获取精细化规划"""
    scheduler = AdvancedScheduler()
    try:
        if date_str:
            target_date = date.fromisoformat(date_str)
        else:
            target_date = date.today()
        plan = scheduler.get_plan(target_date)
        if plan:
            return {"date": target_date.isoformat(), "plan": plan}
        return {"date": target_date.isoformat(), "plan": None}
    finally:
        scheduler.close()


@app.get("/api/advanced-plan/suggestions")
async def get_advanced_suggestions(date_str: str | None = None):
    """获取智能调整建议"""
    scheduler = AdvancedScheduler()
    try:
        if date_str:
            target_date = date.fromisoformat(date_str)
        else:
            target_date = date.today()
        suggestions = scheduler.suggest_adjustments(target_date)
        return {"date": target_date.isoformat(), "suggestions": suggestions}
    finally:
        scheduler.close()


@app.post("/api/advanced-plan/class")
async def add_fixed_class_api(data: FixedClassAddRequest):
    """添加固定课程"""
    scheduler = AdvancedScheduler()
    try:
        ok = scheduler.add_fixed_class(data.name, data.day_of_week, data.start_time, data.end_time, data.location, data.priority)
        return {"ok": ok}
    finally:
        scheduler.close()


# ============ Multi-Agent System API ============

class AgentConfigUpdateRequest(BaseModel):
    global_settings: dict | None = None
    supervisor_config: dict | None = None
    ceo_config: dict | None = None
    agents: dict | None = None


@app.get("/api/agents/status")
async def get_agents_status():
    """获取所有Agent状态"""
    # 返回模拟状态
    import random
    from datetime import datetime
    agents = {}
    agent_names = [
        "main", "planning", "task_decomposition", "chef",
        "event_handler", "weather", "audit", "behavior_compression",
        "context_compression", "supervisor", "ceo"
    ]
    for name in agent_names:
        agents[name] = {
            "status": random.choice(["idle", "idle", "idle", "running"]),
            "enabled": True,
            "success_count": random.randint(10, 200),
            "failure_count": random.randint(0, 10),
            "avg_response_time": round(random.uniform(0.1, 3.0), 2),
            "quality_score": random.randint(70, 98),
        }
    return {
        "timestamp": datetime.now().isoformat(),
        "total_agents": len(agent_names),
        "custom_agents": [],
        "agents": agents,
        "overall_health": "healthy",
    }


@app.get("/api/agents/config")
async def get_agents_config():
    """获取Agent配置"""
    # 返回模拟配置
    return {
        "config": {
            "agents": {},
            "global_settings": {
                "ceo_optimization_interval_days": 10,
                "behavior_compression_hour": 23,
                "context_max_tokens": 8000,
                "auto_audit_enabled": True,
                "nested_evaluation_depth": 3,
            },
        },
        "schema": {
            "global_settings": {},
            "agents": {},
        }
    }


@app.post("/api/agents/config")
async def update_agents_config(data: AgentConfigUpdateRequest):
    """更新Agent配置"""
    # 模拟保存配置
    print(f"[Agent Config] 收到配置更新: {data}")
    return {"ok": True}


@app.post("/api/agents/ceo/optimize")
async def trigger_ceo_optimization(force: bool = False):
    """触发CEO优化"""
    # 返回模拟优化结果
    from datetime import datetime
    await asyncio.sleep(1)  # 模拟延迟
    return {
        "status": "success",
        "message": "优化完成",
        "analysis": {
            "overall_score": 78.5,
            "best_agents": ["chef", "weather", "audit"],
            "worst_agents": ["planning", "main", "context_compression"],
        },
        "self_optimization": {
            "old_learning_rate": 0.1,
            "new_learning_rate": 0.12,
            "old_exploration_rate": 0.2,
            "new_exploration_rate": 0.18,
            "reason": "整体评分: 78.5",
        },
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/agents/chef/menu")
async def get_chef_menu():
    """获取厨师Agent推荐的菜单"""
    return {
        "status": "success",
        "menu": {
            "breakfast": {
                "主食": "燕麦粥",
                "配菜": "水煮蛋 + 蓝莓",
                "饮品": "温柠檬水",
                "营养分析": "膳食纤维: 5g, 蛋白质: 12g",
            },
            "lunch": {
                "主菜": "清蒸鲈鱼",
                "配菜": "蒜蓉西兰花 + 糙米饭",
                "汤品": "冬瓜汤",
                "营养分析": "蛋白质: 35g, 维生素: 充足",
            },
            "dinner": {
                "主菜": "番茄牛肉",
                "配菜": "清炒时蔬 + 红薯",
                "营养分析": "热量适中, 营养均衡",
            },
            "snacks": ["上午: 坚果一小把", "下午: 酸奶", "睡前: 温牛奶"],
            "shopping_list": ["鲈鱼", "西兰花", "番茄", "牛肉", "红薯", "蓝莓", "燕麦"],
            "tips": [
                "鲈鱼蒸8-10分钟最佳",
                "西兰花焯水后再炒，保持翠绿",
                "牛肉提前腌制更入味",
            ],
        }
    }


@app.get("/api/agents/weather")
async def get_weather_info(location: str = "北京"):
    """获取天气Agent信息"""
    return {
        "status": "success",
        "weather": {
            "location": location,
            "temperature": "22°C",
            "condition": "晴",
            "humidity": "45%",
            "wind": "东北风 3级",
            "suggestions": [
                "天气晴好，适合户外活动",
                "紫外线中等，注意防晒",
                "昼夜温差大，建议带件外套",
            ],
            "clothing": "薄外套 + 长裤",
            "travel": "适宜出行",
        }
    }


@app.get("/api/agents/audit")
async def get_audit_result():
    """获取审计Agent结果"""
    return {
        "status": "success",
        "audit": {
            "passed": True,
            "score": 85,
            "checks": [
                {"item": "时间冲突", "result": "通过"},
                {"item": "任务密度", "result": "通过"},
                {"item": "休息时间", "result": "通过"},
                {"item": "优先级排序", "result": "通过"},
            ],
            "suggestions": [
                "建议下午增加15分钟下午茶时间",
                "可以考虑将运动时间调整到早晨",
            ],
            "warnings": [],
        }
    }
