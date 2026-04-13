import typer
from datetime import datetime, timedelta

from app.database import init_db
from app.models import Priority
from app.services.event_service import EventService
from app.services.ai_scheduler import AIScheduler
from app.services.reminder_engine import ReminderEngine

app = typer.Typer(help="AI 每日管家 — 日程管理与提醒")


@app.callback()
def callback():
    init_db()


@app.command("add")
def add_event(
    title: str = typer.Argument(..., help="事件标题"),
    start: str = typer.Option(..., "--start", "-s", help="开始时间，格式 HH:MM 或完整日期时间 YYYY-MM-DDTHH:MM"),
    duration: int = typer.Option(30, "--duration", "-d", help="时长（分钟）"),
    priority: str = typer.Option("medium", "--priority", "-p", help="优先级: urgent/high/medium/low"),
    description: str = typer.Option("", "--desc", help="事件描述"),
):
    """添加新事件"""
    try:
        start_time = parse_time(start)
    except ValueError:
        typer.echo(f"[错误] 时间格式不正确: {start}，请使用 HH:MM 或 YYYY-MM-DDTHH:MM")
        raise typer.Exit(1)

    end_time = start_time + timedelta(minutes=duration)

    try:
        prio = Priority(priority)
    except ValueError:
        typer.echo(f"[错误] 优先级无效: {priority}，可选: urgent/high/medium/low")
        raise typer.Exit(1)

    service = EventService()
    event = service.create_event(
        title=title,
        start_time=start_time,
        end_time=end_time,
        description=description,
        priority=prio,
    )
    service.close()
    typer.echo(f"[OK] 已添加: {event.title} [{event.priority.value}] {event.start_time.strftime('%H:%M')}")


@app.command("list")
def list_events(today_only: bool = typer.Option(True, "--today", "-t", help="只看今天的事件")):
    """列出所有事件"""
    service = EventService()
    if today_only:
        events = service.get_today_events()
    else:
        events = service.get_all_events()
    service.close()

    if not events:
        typer.echo("暂无事件")
        return

    typer.echo(f"\n{'时间':<12} {'优先级':<8} {'状态':<10} {'标题'}")
    typer.echo("-" * 60)
    for e in events:
        typer.echo(
            f"{e.start_time.strftime('%H:%M')}-{e.end_time.strftime('%H:%M')}  "
            f"[{e.priority.value:<7}] [{e.status.value:<8}] {e.title}"
        )
    typer.echo()


@app.command("done")
def complete_event(event_id: int = typer.Argument(..., help="事件ID")):
    """标记事件为已完成"""
    service = EventService()
    ok = service.complete_event(event_id)
    service.close()
    if ok:
        typer.echo(f"[OK] 事件 #{event_id} 已完成")
    else:
        typer.echo(f"[错误] 未找到事件 #{event_id}")


@app.command("delete")
def delete_event(event_id: int = typer.Argument(..., help="事件ID")):
    """删除事件"""
    service = EventService()
    ok = service.delete_event(event_id)
    service.close()
    if ok:
        typer.echo(f"[OK] 事件 #{event_id} 已删除")
    else:
        typer.echo(f"[错误] 未找到事件 #{event_id}")


@app.command("schedule")
def ai_schedule():
    """AI 智能编排 — 重新安排今日事件"""
    import asyncio

    async def _run():
        scheduler = AIScheduler()
        result = await scheduler.generate_schedule()
        scheduler.close()
        return result

    result = asyncio.run(_run())
    if not result:
        typer.echo("今日无待编排事件")
        return

    typer.echo(f"\n{'=' * 50}")
    typer.echo(f"AI 编排建议: {result.get('summary', '')}")
    typer.echo(f"{'=' * 50}")
    for item in result.get("events", []):
        typer.echo(f"  ID:{item['event_id']:>3}  {item['suggested_start']}  — {item['reason']}")
    typer.echo()


@app.command("watch")
def watch(
    interval: int = typer.Option(30, "--interval", "-i", help="检查间隔（秒）"),
):
    """启动提醒守护进程 — 持续运行并按时提醒"""
    typer.echo("[管家] 提醒引擎启动中... 按 Ctrl+C 停止")
    engine = ReminderEngine()
    engine.start(interval_seconds=interval)
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        engine.stop()
        typer.echo("[管家] 已停止")


def parse_time(s: str) -> datetime:
    """解析时间字符串"""
    from datetime import date

    # 尝试完整 ISO 格式
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    # 仅 HH:MM，使用今天
    try:
        h, m = map(int, s.split(":"))
        return datetime(date.today().year, date.today().month, date.today().day, h, m)
    except (ValueError, AttributeError):
        raise ValueError(f"无法解析时间: {s}")


if __name__ == "__main__":
    app()
