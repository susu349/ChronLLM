"""
基础Agent类 - 所有Agent的基类
包含：评估体系、容错机制、重试机制、熔断机制
"""
import abc
import json
import time
import hashlib
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from functools import wraps


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    FALLBACK = "fallback"
    CIRCUIT_BROKEN = "circuit_broken"


@dataclass
class AgentEvaluation:
    """Agent评估结果"""
    agent_name: str
    timestamp: str
    success_count: int = 0
    failure_count: int = 0
    average_response_time: float = 0.0
    quality_score: float = 0.0  # 0-100
    user_satisfaction: float = 0.0  # 0-100
    fallback_count: int = 0
    retry_count: int = 0
    circuit_break_count: int = 0
    risk_transfer_count: int = 0
    issues: List[str] = None
    suggestions: List[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.suggestions is None:
            self.suggestions = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentEvaluation':
        return cls(**data)


class CircuitBreaker:
    """熔断器"""
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func: Callable, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failure_count = 0
        self.state = "closed"

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class RetryMechanism:
    """重试机制"""
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay

    def call(self, func: Callable, *args, **kwargs):
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    time.sleep(delay)
        raise last_exception


class BaseAgent(abc.ABC):
    """基础Agent抽象类"""

    def __init__(self, name: str, description: str = "", config: Dict[str, Any] = None):
        self.name = name
        self.description = description
        self.config = config or {}
        self.status = AgentStatus.IDLE
        self.evaluation = AgentEvaluation(
            agent_name=name,
            timestamp=datetime.now().isoformat()
        )
        self.circuit_breaker = CircuitBreaker()
        self.retry_mechanism = RetryMechanism()
        self.response_times: List[float] = []
        self.last_execution_time = None
        self.fallback_strategy: Optional[Callable] = None
        self.risk_transfer_target: Optional[str] = None

        # 历史记录
        self.execution_history: List[Dict[str, Any]] = []
        self.max_history_size = 100

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行Agent任务（主入口）"""
        start_time = time.time()
        self.status = AgentStatus.RUNNING

        try:
            # 1. 检查熔断状态
            if self.circuit_breaker.state == "open":
                self.status = AgentStatus.CIRCUIT_BROKEN
                self.evaluation.circuit_break_count += 1
                return self._handle_circuit_break(input_data)

            # 2. 尝试执行（带重试）
            try:
                result = self.retry_mechanism.call(
                    self._execute_impl, input_data
                )
                self.status = AgentStatus.SUCCESS
                self.evaluation.success_count += 1
                self._record_success()
                return result

            except Exception as e:
                self.evaluation.failure_count += 1
                self.circuit_breaker._on_failure()

                # 3. 尝试兜底策略
                if self.fallback_strategy:
                    self.status = AgentStatus.FALLBACK
                    self.evaluation.fallback_count += 1
                    return self._handle_fallback(input_data, e)

                # 4. 尝试风险转移
                if self.risk_transfer_target:
                    self.evaluation.risk_transfer_count += 1
                    return self._handle_risk_transfer(input_data, e)

                self.status = AgentStatus.FAILED
                raise

        finally:
            end_time = time.time()
            response_time = end_time - start_time
            self.response_times.append(response_time)
            self.last_execution_time = datetime.now()
            self._update_evaluation(response_time)
            self._record_execution(input_data, self.status, response_time)

    @abc.abstractmethod
    def _execute_impl(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Agent具体实现（子类必须实现）"""
        pass

    def _handle_circuit_break(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理熔断"""
        return {
            "status": "circuit_broken",
            "agent": self.name,
            "message": f"Agent {self.name} has been circuit broken",
            "fallback": True,
            "data": input_data,
            "timestamp": datetime.now().isoformat()
        }

    def _handle_fallback(self, input_data: Dict[str, Any], error: Exception) -> Dict[str, Any]:
        """处理兜底"""
        try:
            return self.fallback_strategy(input_data, error)
        except Exception as e:
            return {
                "status": "fallback_failed",
                "agent": self.name,
                "error": str(e),
                "original_error": str(error),
                "data": input_data,
                "timestamp": datetime.now().isoformat()
            }

    def _handle_risk_transfer(self, input_data: Dict[str, Any], error: Exception) -> Dict[str, Any]:
        """处理风险转移"""
        return {
            "status": "risk_transferred",
            "from_agent": self.name,
            "to_agent": self.risk_transfer_target,
            "error": str(error),
            "data": input_data,
            "timestamp": datetime.now().isoformat()
        }

    def _record_success(self):
        """记录成功"""
        pass

    def _update_evaluation(self, response_time: float):
        """更新评估数据"""
        if len(self.response_times) > 0:
            self.evaluation.average_response_time = sum(self.response_times) / len(self.response_times)
        self.evaluation.timestamp = datetime.now().isoformat()

    def _record_execution(self, input_data: Dict[str, Any], status: AgentStatus, response_time: float):
        """记录执行历史"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "input_hash": self._hash_input(input_data),
            "status": status.value,
            "response_time": response_time
        }
        self.execution_history.append(record)
        if len(self.execution_history) > self.max_history_size:
            self.execution_history = self.execution_history[-self.max_history_size:]

    def _hash_input(self, input_data: Dict[str, Any]) -> str:
        """输入哈希（用于去重）"""
        try:
            data_str = json.dumps(input_data, sort_keys=True)
            return hashlib.md5(data_str.encode()).hexdigest()
        except:
            return hashlib.md5(str(time.time()).encode()).hexdigest()

    def set_fallback(self, fallback_strategy: Callable):
        """设置兜底策略"""
        self.fallback_strategy = fallback_strategy

    def set_risk_transfer(self, target_agent: str):
        """设置风险转移目标"""
        self.risk_transfer_target = target_agent

    def get_evaluation(self) -> AgentEvaluation:
        """获取评估结果"""
        return self.evaluation

    def reset_evaluation(self):
        """重置评估"""
        self.evaluation = AgentEvaluation(
            agent_name=self.name,
            timestamp=datetime.now().isoformat()
        )
        self.response_times = []
        self.execution_history = []

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "config": self.config,
            "evaluation": self.evaluation.to_dict(),
            "last_execution_time": self.last_execution_time.isoformat() if self.last_execution_time else None,
            "circuit_breaker_state": self.circuit_breaker.state,
        }

    def get_capabilities(self) -> List[str]:
        """获取Agent能力列表"""
        return []

    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置Schema（用于前端配置）"""
        return {}
