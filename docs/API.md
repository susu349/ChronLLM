# API 接口文档

## 概述

本文档描述 Aether 系统的所有 API 接口。

- **Base URL**: `http://localhost:8000`
- **Content-Type**: `application/json`
- **协议**: HTTP/1.1

---

## 通用响应格式

### 成功响应

```json
{
  "ok": true,
  "data": {}
}
```

### 错误响应

```json
{
  "ok": false,
  "message": "错误描述"
}
```

---

## 对话接口

### POST /api/chat

普通聊天接口

**请求体:**

```json
{
  "message": "用户消息内容"
}
```

**响应:**

```json
{
  "reply": "管家回复内容",
  "events": [],
  "saved_events": []
}
```

**字段说明:**

- `reply`: 管家的回复文本
- `events`: 提取出的事件数组
- `saved_events`: 已保存的事件数组

---

### POST /api/butler/start

开始主动管家对话

**响应:**

```json
{
  "reply": "第一个问题",
  "is_finished": false,
  "can_plan": false
}
```

---

### POST /api/butler/answer

回答管家问题

**请求体:**

```json
{
  "message": "用户回答内容"
}
```

**响应:**

```json
{
  "reply": "下一个问题或规划内容",
  "is_finished": false,
  "can_plan": false,
  "plan": {},
  "saved_events": []
}
```

**字段说明:**

- `is_finished`: 对话是否已完成
- `can_plan`: 是否可以生成规划
- `plan`: 生成的规划对象
- `saved_events`: 已保存的事件数组

---

### GET /api/butler/summary

获取当前对话摘要

**响应:**

```json
{
  "steps": [],
  "info": {},
  "is_finished": false
}
```

---

### POST /api/butler/reset

重置管家对话

**响应:**

```json
{
  "ok": true
}
```

---

## 事件管理接口

### GET /api/events/{event_id}

获取单个事件详情

**路径参数:**

- `event_id`: 事件 ID（整数）

**响应:**

```json
{
  "id": 1,
  "title": "事件标题",
  "description": "事件描述",
  "date": "2026-04-13",
  "start_time": "09:00",
  "end_time": "10:00",
  "priority": "medium",
  "status": "pending",
  "location": "事件地点",
  "participants": [],
  "task_steps": [],
  "notes": "备注信息",
  "category": "work",
  "is_ai_scheduled": false,
  "created_at": "2026-04-13T09:00:00"
}
```

**字段说明:**

- `priority`: 优先级，可选值: `urgent`, `high`, `medium`, `low`
- `status`: 状态，可选值: `pending`, `active`, `completed`, `skipped`
- `category`: 分类，可选值: `work`, `personal`, `meeting`, `exercise`, `meal`, `rest`

---

### POST /api/events

创建新事件

**请求体:**

```json
{
  "title": "事件标题",
  "date": "2026-04-13",
  "start_time": "09:00",
  "duration_minutes": 60,
  "priority": "medium",
  "description": "事件描述",
  "location": "事件地点",
  "participants": "张三, 李四",
  "task_steps": "1. 第一步\n2. 第二步",
  "notes": "备注信息",
  "category": "work"
}
```

**字段说明:**

- `title`: 必需，事件标题
- `start_time`: 必需，开始时间
- `date`: 可选，日期，默认为今天
- `duration_minutes`: 可选，持续分钟数，默认为 30
- `priority`: 可选，优先级，默认为 `medium`
- 其他字段均为可选

**响应:**

```json
{
  "id": 1,
  "title": "事件标题",
  "start": "2026-04-13T09:00:00"
}
```

---

### PUT /api/events/{event_id}

更新事件

**路径参数:**

- `event_id`: 事件 ID（整数）

**请求体:** 同 POST /api/events

**响应:**

```json
{
  "ok": true
}
```

---

### DELETE /api/events/{event_id}

删除事件

**路径参数:**

- `event_id`: 事件 ID（整数）

**响应:**

```json
{
  "ok": true
}
```

---

### POST /api/events/{event_id}/complete

标记事件完成

**路径参数:**

- `event_id`: 事件 ID（整数）

**请求体（可选）:**

```json
{
  "completion_rate": 80,
  "summary": "完成总结",
  "reflection": "反思内容",
  "obstacles": "遇到的困难"
}
```

**响应:**

```json
{
  "ok": true
}
```

---

## 时间线接口

### GET /api/timeline

获取时间线事件

**查询参数:**

- `year`: 可选，年份
- `month`: 可选，月份
- `day`: 可选，日期

**响应:**

```json
[
  {
    "id": 1,
    "title": "事件标题",
    "date": "2026-04-13",
    "time": "09:00",
    "end": "10:00",
    "priority": "medium",
    "status": "pending",
    "description": "事件描述",
    "is_ai_scheduled": false
  }
]
```

---

### GET /api/timeline/structure

获取树形结构时间线

**查询参数:**

- `year`: 可选，年份
- `month`: 可选，月份

**响应:**

```json
{
  "2026": {
    "4": {
      "13": [
        {
          "id": 1,
          "title": "事件标题",
          "time": "09:00",
          "priority": "medium",
          "status": "pending"
        }
      ]
    }
  }
}
```

---

## 规划接口

### POST /api/plan/generate

生成今日详细规划

**响应:**

```json
{
  "summary": "规划摘要",
  "schedule": [
    {
      "start_time": "07:00",
      "end_time": "07:30",
      "title": "起床",
      "description": "起床、拉伸",
      "priority": "medium",
      "category": "routine"
    }
  ]
}
```

---

### GET /api/plan

获取今日规划

**查询参数:**

- `date_str`: 可选，日期字符串，格式为 YYYY-MM-DD，默认为今天

**响应:**

```json
{
  "date": "2026-04-13",
  "summary": "规划摘要",
  "detailed_plan": {},
  "is_auto_generated": false,
  "created_at": "2026-04-13T00:30:00"
}
```

---

### POST /api/plan/apply

应用规划到日程

**响应:**

```json
{
  "ok": true,
  "events_created": 5
}
```

---

### POST /api/plan/trigger-now

立即触发自动规划（测试用）

**响应:**

```json
{
  "ok": true,
  "message": "规划任务已启动"
}
```

---

## 笔记接口

### GET /api/notes

获取笔记列表

**查询参数:**

- `date_str`: 可选，日期字符串
- `note_type`: 可选，笔记类型

**响应:**

```json
[
  {
    "id": 1,
    "title": "笔记标题",
    "content": "笔记内容",
    "note_type": "general",
    "tags": [],
    "date": "2026-04-13",
    "created_at": "2026-04-13T09:00:00",
    "updated_at": "2026-04-13T09:00:00"
  }
]
```

---

### POST /api/notes

创建笔记

**请求体:**

```json
{
  "title": "笔记标题",
  "content": "笔记内容",
  "note_type": "general",
  "tags": []
}
```

**响应:**

```json
{
  "id": 1,
  "title": "笔记标题",
  "content": "笔记内容",
  "note_type": "general",
  "tags": [],
  "date": "2026-04-13",
  "created_at": "2026-04-13T09:00:00",
  "updated_at": "2026-04-13T09:00:00"
}
```

---

### GET /api/notes/{note_id}

获取单个笔记

**路径参数:**

- `note_id`: 笔记 ID（整数）

**响应:** 同 POST /api/notes 的响应格式

---

### PUT /api/notes/{note_id}

更新笔记

**路径参数:**

- `note_id`: 笔记 ID（整数）

**请求体:** 同 POST /api/notes

**响应:** 同 POST /api/notes 的响应格式

---

### DELETE /api/notes/{note_id}

删除笔记

**路径参数:**

- `note_id`: 笔记 ID（整数）

**响应:**

```json
{
  "ok": true
}
```

---

### GET /api/notes/search/{keyword}

搜索笔记

**路径参数:**

- `keyword`: 搜索关键词

**响应:** 同 GET /api/notes 的响应格式

---

## 统计接口

### GET /api/today

获取今日概览

**响应:**

```json
{
  "total": 10,
  "pending": 5,
  "active": 2,
  "completed": 3
}
```

---

### GET /api/stats/weekly

获取周统计数据

**响应:**

```json
{
  "period_start": "2026-04-07",
  "period_end": "2026-04-13",
  "summary": {
    "total": 50,
    "completed": 35,
    "pending": 15,
    "completion_rate": 70.0
  },
  "daily": []
}
```

---

### GET /api/stats/monthly

获取月统计数据

**查询参数:**

- `year`: 可选，年份
- `month`: 可选，月份

**响应:**

```json
{
  "year": 2026,
  "month": 4,
  "summary": {
    "total": 200,
    "completed": 140,
    "pending": 60,
    "completion_rate": 70.0
  },
  "priority_distribution": {
    "urgent": 20,
    "high": 60,
    "medium": 100,
    "low": 20
  },
  "weekly": []
}
```

---

## 设置接口

### GET /api/settings

获取基础设置

**响应:**

```json
{
  "USER_NAME": "用户",
  "LLM_API_KEY": "",
  "LLM_BASE_URL": "",
  "LLM_MODEL": "",
  "DEFAULT_REMINDER_MINUTES": 10
}
```

---

### POST /api/settings

保存基础设置

**请求体:**

```json
{
  "USER_NAME": "用户",
  "LLM_API_KEY": "your_api_key",
  "LLM_BASE_URL": "https://api.example.com",
  "LLM_MODEL": "model-name",
  "DEFAULT_REMINDER_MINUTES": 10
}
```

**响应:** 同 GET /api/settings 的响应格式

---

### GET /api/preferences

获取偏好设置

**响应:**

```json
{
  "wake_up_time": "07:00",
  "breakfast_time": "07:30",
  "work_start_time": "09:00",
  "lunch_time": "12:00",
  "work_end_time": "18:00",
  "dinner_time": "18:30",
  "bed_time": "23:00",
  "buffer_minutes": 15,
  "include_exercise": true,
  "exercise_duration": 45,
  "exercise_time": "evening",
  "deep_work_first": true,
  "user_identity": "worker",
  "butler_style": "classic"
}
```

---

### POST /api/preferences

保存偏好设置

**请求体:** 同 GET /api/preferences 的响应格式

**响应:** 同 GET /api/preferences 的响应格式

---

## 身份与管家风格接口

### GET /api/identity/presets

获取所有身份预设

**响应:**

```json
{
  "student": {
    "name": "学生",
    "description": "早八晚十，学习为主"
  },
  "worker": {
    "name": "上班族",
    "description": "朝九晚五，工作为重"
  }
}
```

---

### POST /api/identity/apply

应用身份预设

**请求体:**

```json
{
  "identity": "worker"
}
```

**响应:**

```json
{
  "ok": true,
  "preferences": {}
}
```

---

### GET /api/butler/styles

获取所有管家风格预设

**响应:**

```json
{
  "classic": {
    "name": "经典管家",
    "description": "专业、稳重、优雅",
    "emoji": "🎩",
    "color": "#000000"
  }
}
```

---

### POST /api/butler/style/apply

应用管家风格预设

**请求体:**

```json
{
  "style": "classic"
}
```

**响应:**

```json
{
  "ok": true,
  "preferences": {}
}
```

---

### GET /api/butler/style/config

获取当前管家风格配置

**响应:**

```json
{
  "style": "classic",
  "name": "经典管家",
  "description": "专业、稳重、优雅",
  "greeting": "您好，{user_name}。",
  "call_user": "{user_name}",
  "self_call": "我",
  "tone": "professional",
  "emoji": "🎩",
  "color": "#000000"
}
```

---

## 天气接口

### GET /api/weather

获取天气信息

**查询参数:**

- `city`: 可选，城市名称

**响应:**

```json
{
  "ok": true,
  "weather": {
    "location": "北京",
    "temperature": "22°C",
    "condition": "晴",
    "humidity": "45%",
    "wind": "东北风 3级",
    "suggestions": [],
    "clothing": "薄外套 + 长裤",
    "travel": "适宜出行"
  },
  "suggestion": "天气晴好，适合户外活动",
  "is_configured": true
}
```

---

## 食谱接口

### GET /api/recipes

获取食谱列表

**查询参数:**

- `meal_type`: 可选，餐食类型
- `tag`: 可选，标签
- `cuisine`: 可选，菜系

**响应:**

```json
[
  {
    "id": 1,
    "name": "食谱名称",
    "description": "描述",
    "ingredients": [],
    "instructions": [],
    "prep_time": 30,
    "cook_time": 30,
    "servings": 2,
    "difficulty": "medium",
    "tags": [],
    "cuisine": "",
    "meal_type": "dinner",
    "calories": 0,
    "protein": 0,
    "carbs": 0,
    "fat": 0,
    "fiber": 0
  }
]
```

---

### GET /api/recipes/{recipe_id}

获取单个食谱详情

**路径参数:**

- `recipe_id`: 食谱 ID（整数）

**响应:** 同 GET /api/recipes 的单个元素格式

---

### GET /api/recipes/search/{keyword}

搜索食谱

**路径参数:**

- `keyword`: 搜索关键词

**响应:** 同 GET /api/recipes 的响应格式

---

### POST /api/recipes

添加自定义食谱

**请求体:**

```json
{
  "name": "食谱名称",
  "description": "描述",
  "ingredients": [],
  "instructions": [],
  "prep_time": 30,
  "cook_time": 30,
  "servings": 2,
  "difficulty": "medium",
  "tags": [],
  "cuisine": "",
  "meal_type": "dinner",
  "calories": 0,
  "protein": 0,
  "carbs": 0,
  "fat": 0,
  "fiber": 0
}
```

**响应:** 同 GET /api/recipes 的单个元素格式

---

### DELETE /api/recipes/{recipe_id}

删除食谱

**路径参数:**

- `recipe_id`: 食谱 ID（整数）

**响应:**

```json
{
  "ok": true
}
```

---

### GET /api/meal-plan/generate

生成每周饮食计划

**响应:**

```json
{
  "plan": {}
}
```

---

### GET /api/meal-plan

获取保存的周计划

**响应:**

```json
{
  "week_start": "2026-04-07",
  "plan_data": {}
}
```

---

### POST /api/meal-plan

保存周计划

**请求体:**

```json
{
  "week_start": "2026-04-07",
  "plan_data": {}
}
```

**响应:**

```json
{
  "ok": true
}
```

---

## 多智能体系统接口

### GET /api/agents/status

获取所有 Agent 状态

**响应:**

```json
{
  "timestamp": "2026-04-13T15:00:00",
  "total_agents": 11,
  "custom_agents": [],
  "agents": {
    "main": {
      "status": "idle",
      "enabled": true,
      "success_count": 100,
      "failure_count": 5,
      "avg_response_time": 1.2,
      "quality_score": 85
    }
  },
  "overall_health": "healthy"
}
```

---

### POST /api/agents/ceo/optimize

触发 CEO 优化

**查询参数:**

- `force`: 可选，布尔值，是否强制优化

**响应:**

```json
{
  "status": "success",
  "message": "优化完成",
  "analysis": {
    "overall_score": 78.5,
    "best_agents": ["chef", "weather", "audit"],
    "worst_agents": ["planning", "main"]
  },
  "self_optimization": {
    "old_learning_rate": 0.1,
    "new_learning_rate": 0.12,
    "old_exploration_rate": 0.2,
    "new_exploration_rate": 0.18,
    "reason": "整体评分: 78.5"
  },
  "timestamp": "2026-04-13T15:00:00"
}
```

---

### GET /api/agents/chef/menu

获取厨师 Agent 推荐菜单

**响应:**

```json
{
  "status": "success",
  "menu": {
    "breakfast": {},
    "lunch": {},
    "dinner": {},
    "snacks": [],
    "shopping_list": [],
    "tips": []
  }
}
```

---

### GET /api/agents/weather

获取天气 Agent 信息

**查询参数:**

- `location`: 可选，位置名称，默认为北京

**响应:**

```json
{
  "status": "success",
  "weather": {
    "location": "北京",
    "temperature": "22°C",
    "condition": "晴",
    "humidity": "45%",
    "wind": "东北风 3级",
    "suggestions": [],
    "clothing": "薄外套 + 长裤",
    "travel": "适宜出行"
  }
}
```

---

### GET /api/agents/audit

获取审计 Agent 结果

**响应:**

```json
{
  "status": "success",
  "audit": {
    "passed": true,
    "score": 85,
    "checks": [
      {
        "item": "时间冲突",
        "result": "通过"
      }
    ],
    "suggestions": [],
    "warnings": []
  }
}
```

---

## 实时推送接口

### GET /api/sse

SSE 实时推送连接

**响应格式:** Server-Sent Events 流

**事件类型:**

- `reminder`: 提醒事件
- `plan_generated`: 规划生成
- `nightly_summary`: 晚间总结

---

## 页面接口

### GET /

主页

**响应:** HTML 页面

---

### GET /recipes

食谱管理页面

**响应:** HTML 页面

---

## 错误码

| HTTP 状态码 | 说明 |
|-----------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
