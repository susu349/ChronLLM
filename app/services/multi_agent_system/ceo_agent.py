"""
CEO Agent
负责优化各个Agent以及自我优化，约10天一次
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
from pathlib import Path
from .base_agent import BaseAgent, AgentEvaluation


class CEOAgent(BaseAgent):
    """CEO Agent - 优化各Agent及自我优化"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(
            name="ceo",
            description="优化各Agent及自我优化（约10天一次）",
            config=config
        )
        self.optimization_interval_days = config.get("optimization_interval_days", 10) if config else 10
        self.last_optimization_date: datetime = None
        self.optimization_history: List[Dict[str, Any]] = []
        self.learning_rate = config.get("learning_rate", 0.1) if config else 0.1
        self.exploration_rate = config.get("exploration_rate", 0.2) if config else 0.2

        self._load_state()

    def _get_state_file(self) -> Path:
        """获取状态文件路径"""
        data_dir = Path(__file__).parent.parent.parent.parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "ceo_agent_state.json"

    def _load_state(self):
        """加载状态"""
        state_file = self._get_state_file()
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    if state.get("last_optimization_date"):
                        self.last_optimization_date = datetime.fromisoformat(state["last_optimization_date"])
                    self.optimization_history = state.get("optimization_history", [])
                    self.learning_rate = state.get("learning_rate", 0.1)
                    self.exploration_rate = state.get("exploration_rate", 0.2)
            except Exception as e:
                print(f"[CEO Agent] 加载状态失败: {e}")

    def _save_state(self):
        """保存状态"""
        state_file = self._get_state_file()
        state = {
            "last_optimization_date": self.last_optimization_date.isoformat() if self.last_optimization_date else None,
            "optimization_history": self.optimization_history[-100:],
            "learning_rate": self.learning_rate,
            "exploration_rate": self.exploration_rate,
        }
        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CEO Agent] 保存状态失败: {e}")

    def should_optimize(self) -> bool:
        """是否应该进行优化"""
        if self.last_optimization_date is None:
            return True
        days_since = (datetime.now() - self.last_optimization_date).days
        return days_since >= self.optimization_interval_days

    def _execute_impl(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行优化"""
        force = input_data.get("force", False)

        if not force and not self.should_optimize():
            return {
                "status": "skipped",
                "message": f"优化间隔未到（{self.optimization_interval_days}天）",
                "last_optimization": self.last_optimization_date.isoformat() if self.last_optimization_date else None,
                "days_until_next": self.optimization_interval_days - (datetime.now() - self.last_optimization_date).days if self.last_optimization_date else 0,
                "timestamp": datetime.now().isoformat()
            }

        print(f"[CEO Agent] 开始优化流程...")

        # 1. 收集各Agent的评估数据
        agents_evaluation = input_data.get("agents_evaluation", {})

        # 2. 分析问题
        analysis = self._analyze_agents(agents_evaluation)

        # 3. 生成优化建议
        optimizations = self._generate_optimizations(analysis, agents_evaluation)

        # 4. 自我优化
        self_optimization = self._self_optimize(analysis)

        # 5. 记录优化
        optimization_record = {
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
            "optimizations": optimizations,
            "self_optimization": self_optimization,
        }
        self.optimization_history.append(optimization_record)
        self.last_optimization_date = datetime.now()
        self._save_state()

        # 更新评估
        self.evaluation.success_count += 1

        return {
            "status": "success",
            "message": "优化完成",
            "analysis": analysis,
            "optimizations": optimizations,
            "self_optimization": self_optimization,
            "timestamp": datetime.now().isoformat()
        }

    def _analyze_agents(self, agents_evaluation: Dict[str, AgentEvaluation]) -> Dict[str, Any]:
        """分析各Agent的表现"""
        analysis = {
            "overall_score": 0.0,
            "best_agents": [],
            "worst_agents": [],
            "common_issues": [],
            "recommendations": [],
        }

        scores = []
        for name, eval_data in agents_evaluation.items():
            if isinstance(eval_data, dict):
                quality = eval_data.get("quality_score", 0)
                scores.append((name, quality))
            elif hasattr(eval_data, "quality_score"):
                scores.append((name, eval_data.quality_score))

        if scores:
            scores.sort(key=lambda x: x[1], reverse=True)
            analysis["best_agents"] = [name for name, score in scores[:3]]
            analysis["worst_agents"] = [name for name, score in scores[-3:]]
            analysis["overall_score"] = sum(score for _, score in scores) / len(scores)

        return analysis

    def _generate_optimizations(self, analysis: Dict[str, Any], agents_evaluation: Dict[str, AgentEvaluation]) -> List[Dict[str, Any]]:
        """生成优化建议"""
        optimizations = []

        # 为表现差的Agent提供优化建议
        for agent_name in analysis.get("worst_agents", []):
            eval_data = agents_evaluation.get(agent_name)
            if eval_data:
                optimization = {
                    "target_agent": agent_name,
                    "priority": "high",
                    "suggestions": [],
                    "estimated_improvement": 0.0,
                }

                if isinstance(eval_data, dict):
                    if eval_data.get("failure_count", 0) > 5:
                        optimization["suggestions"].append("增加重试次数")
                        optimization["suggestions"].append("检查熔断阈值")
                    if eval_data.get("average_response_time", 0) > 10:
                        optimization["suggestions"].append("优化响应速度")
                        optimization["suggestions"].append("考虑添加缓存")
                elif hasattr(eval_data, "failure_count"):
                    if eval_data.failure_count > 5:
                        optimization["suggestions"].append("增加重试次数")
                    if eval_data.average_response_time > 10:
                        optimization["suggestions"].append("优化响应速度")

                optimization["estimated_improvement"] = 15.0
                optimizations.append(optimization)

        return optimizations

    def _self_optimize(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """自我优化"""
        old_learning_rate = self.learning_rate
        old_exploration_rate = self.exploration_rate

        overall_score = analysis.get("overall_score", 50)

        # 根据整体表现调整参数
        if overall_score < 50:
            self.learning_rate = min(0.3, self.learning_rate * 1.2)
            self.exploration_rate = min(0.4, self.exploration_rate * 1.1)
        elif overall_score > 80:
            self.learning_rate = max(0.05, self.learning_rate * 0.9)
            self.exploration_rate = max(0.1, self.exploration_rate * 0.9)

        return {
            "old_learning_rate": old_learning_rate,
            "new_learning_rate": self.learning_rate,
            "old_exploration_rate": old_exploration_rate,
            "new_exploration_rate": self.exploration_rate,
            "reason": f"整体评分: {overall_score:.1f}",
        }

    def get_capabilities(self) -> List[str]:
        return [
            "Agent性能分析",
            "优化建议生成",
            "自我参数调优",
            "优化历史记录",
        ]
