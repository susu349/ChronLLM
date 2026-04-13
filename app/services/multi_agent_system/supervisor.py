"""
主管Agent (Supervisor Agent)
负责协调各Agent之间的交互，是系统的中枢调度器
"""
import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent, AgentStatus, AgentEvaluation


class SupervisorAgent(BaseAgent):
    """主管Agent - 协调各Agent交互"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(
            name="supervisor",
            description="负责协调各Agent之间的交互",
            config=config
        )
        self.agents: Dict[str, BaseAgent] = {}
        self.task_queue: List[Dict[str, Any]] = []
        self.execution_graph: Dict[str, List[str]] = {}
        self.agent_dependencies: Dict[str, List[str]] = {}
        self.custom_agents: List[str] = []

    def register_agent(self, agent: BaseAgent):
        """注册Agent"""
        self.agents[agent.name] = agent
        print(f"[Supervisor] Agent已注册: {agent.name}")

    def register_custom_agent(self, agent_name: str, agent_config: Dict[str, Any]):
        """注册自定义Agent"""
        if agent_name not in self.agents:
            self.custom_agents.append(agent_name)
            print(f"[Supervisor] 自定义Agent已注册: {agent_name}")

    def set_dependencies(self, agent_name: str, depends_on: List[str]):
        """设置Agent依赖关系"""
        self.agent_dependencies[agent_name] = depends_on

    def _execute_impl(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行调度"""
        task_type = input_data.get("task_type", "general")
        user_input = input_data.get("input", "")
        context = input_data.get("context", {})

        print(f"[Supervisor] 收到任务: {task_type}")

        # 1. 任务路由
        execution_plan = self._create_execution_plan(task_type, user_input, context)

        # 2. 执行计划
        results = self._execute_plan(execution_plan, user_input, context)

        # 3. 结果聚合
        final_result = self._aggregate_results(results, task_type)

        return {
            "status": "success",
            "supervisor_decision": execution_plan,
            "results": results,
            "final_output": final_result,
            "timestamp": datetime.now().isoformat()
        }

    def _create_execution_plan(self, task_type: str, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """创建执行计划"""
        plan = {
            "task_type": task_type,
            "steps": [],
            "parallel_agents": [],
            "sequential_agents": [],
            "requires_audit": True,
        }

        if task_type == "daily_plan":
            # 每日规划流程
            plan["sequential_agents"] = [
                "context_compression",  # 先加载上下文
                "planning",             # 规划
                "audit",                # 审计
            ]
            plan["parallel_agents"] = ["weather", "chef"]  # 并行获取天气和菜单

        elif task_type == "task_decomposition":
            # 任务拆解流程
            plan["sequential_agents"] = [
                "task_decomposition",
                "event_handler",
                "audit",
            ]

        elif task_type == "chat":
            # 普通对话流程
            plan["sequential_agents"] = [
                "context_compression",
                "main",
            ]
            plan["parallel_agents"] = ["weather"]  # 可选并行
            plan["requires_audit"] = False

        elif task_type == "custom":
            # 自定义流程
            custom_agents = context.get("agents", [])
            plan["sequential_agents"] = custom_agents

        else:
            # 默认流程
            plan["sequential_agents"] = [
                "context_compression",
                "main",
            ]

        return plan

    def _execute_plan(self, plan: Dict[str, Any], user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行计划"""
        results = {}
        step_context = {**context, "user_input": user_input}

        # 1. 并行执行
        for agent_name in plan.get("parallel_agents", []):
            if agent_name in self.agents:
                try:
                    agent = self.agents[agent_name]
                    if agent.config.get("enabled", True):
                        print(f"[Supervisor] 并行执行: {agent_name}")
                        result = agent.execute({
                            "input": user_input,
                            "context": step_context,
                        })
                        results[agent_name] = result
                        step_context[agent_name] = result.get("data", {})
                except Exception as e:
                    print(f"[Supervisor] Agent {agent_name} 执行失败: {e}")
                    results[agent_name] = {"status": "failed", "error": str(e)}

        # 2. 顺序执行
        for agent_name in plan.get("sequential_agents", []):
            if agent_name in self.agents:
                try:
                    agent = self.agents[agent_name]
                    if agent.config.get("enabled", True):
                        # 检查依赖
                        if not self._check_dependencies(agent_name, results):
                            print(f"[Supervisor] Agent {agent_name} 依赖未满足，跳过")
                            continue

                        print(f"[Supervisor] 顺序执行: {agent_name}")
                        result = agent.execute({
                            "input": user_input,
                            "context": step_context,
                            "previous_results": results,
                        })
                        results[agent_name] = result
                        step_context[agent_name] = result.get("data", {})
                except Exception as e:
                    print(f"[Supervisor] Agent {agent_name} 执行失败: {e}")
                    results[agent_name] = {"status": "failed", "error": str(e)}

        return results

    def _check_dependencies(self, agent_name: str, results: Dict[str, Any]) -> bool:
        """检查依赖是否满足"""
        dependencies = self.agent_dependencies.get(agent_name, [])
        for dep in dependencies:
            if dep in results:
                dep_result = results[dep]
                if dep_result.get("status") != "success":
                    return False
        return True

    def _aggregate_results(self, results: Dict[str, Any], task_type: str) -> Dict[str, Any]:
        """聚合结果"""
        # 优先获取主Agent的结果
        if "main" in results:
            return results["main"]

        # 规划任务结果
        if task_type == "daily_plan" and "planning" in results:
            return results["planning"]

        # 默认返回所有结果
        return {
            "aggregated": True,
            "task_type": task_type,
            "results": results,
        }

    def get_status_report(self) -> Dict[str, Any]:
        """获取系统状态报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_agents": len(self.agents),
            "custom_agents": self.custom_agents,
            "agents": {},
            "overall_health": "healthy",
        }

        for name, agent in self.agents.items():
            eval_data = agent.get_evaluation()
            report["agents"][name] = {
                "status": agent.status.value,
                "enabled": agent.config.get("enabled", True),
                "success_count": eval_data.success_count,
                "failure_count": eval_data.failure_count,
                "avg_response_time": eval_data.average_response_time,
                "quality_score": eval_data.quality_score,
            }

        return report

    def get_capabilities(self) -> List[str]:
        return [
            "任务编排",
            "Agent协调",
            "依赖管理",
            "并行执行",
            "顺序执行",
            "自定义Agent注册",
            "状态监控",
        ]
