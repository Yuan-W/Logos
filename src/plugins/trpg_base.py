"""
TRPG System Plugin - Abstract Base Class
=========================================
定义 TRPG 系统插件的抽象接口，用于扩展 GM Agent 支持不同规则系统。

设计目标：
1. 解耦游戏机制逻辑与核心 Agent 工作流
2. 支持热插拔不同 TRPG 规则 (CoC, BitD, D&D 等)
3. 提供统一的状态更新和 Prompt 注入接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum


class ActionResultType(Enum):
    """骰子检定结果类型"""
    CRITICAL_SUCCESS = "critical_success"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    CRITICAL_FAILURE = "critical_failure"


@dataclass
class MechanicsResult:
    """机制处理结果的标准化容器"""
    result_type: ActionResultType
    narrative_hint: str  # 给 Narrator 的叙事提示
    state_changes: Dict[str, Any] = field(default_factory=dict)  # 状态更新 (HP, Sanity, Clocks 等)
    resource_costs: Dict[str, int] = field(default_factory=dict)  # 资源消耗
    triggered_effects: list[str] = field(default_factory=list)  # 触发的特殊效果


class TRPGSystemPlugin(ABC):
    """
    TRPG 规则系统插件的抽象基类。
    
    每个插件负责：
    1. 处理特定系统的游戏机制 (骰子、技能检定)
    2. 提供系统特定的 Prompt 增强
    3. 管理状态更新逻辑
    """
    
    @property
    @abstractmethod
    def system_name(self) -> str:
        """返回系统名称，如 'Call of Cthulhu', 'Blades in the Dark'"""
        pass
    
    @property
    @abstractmethod
    def default_dice_notation(self) -> str:
        """返回默认骰子表达式，如 'd100', '1d6'"""
        pass
    
    @abstractmethod
    def handle_mechanics(
        self, 
        action_type: str,
        player_stats: Dict[str, Any],
        difficulty: Optional[int] = None,
        modifiers: Optional[Dict[str, int]] = None
    ) -> MechanicsResult:
        """
        处理游戏机制检定。
        
        Args:
            action_type: 动作类型 (e.g., "skill_check", "combat", "sanity_check")
            player_stats: 当前玩家状态 (技能值、属性等)
            difficulty: 难度等级 (可选)
            modifiers: 情境修正值 (可选)
            
        Returns:
            MechanicsResult: 包含结果类型、叙事提示和状态变更
        """
        pass
    
    @abstractmethod
    def get_system_prompt_additions(self, game_state: Dict[str, Any]) -> str:
        """
        返回系统特定的 Prompt 附加内容。
        
        这些内容会被注入到 GM Agent 的 System Prompt 中，
        帮助 LLM 理解当前游戏规则和状态。
        
        Args:
            game_state: 当前游戏状态
            
        Returns:
            str: 要附加到 System Prompt 的文本
        """
        pass
    
    @abstractmethod
    def process_state_update(
        self, 
        current_state: Dict[str, Any],
        mechanics_result: MechanicsResult
    ) -> Dict[str, Any]:
        """
        根据机制结果更新游戏状态。
        
        Args:
            current_state: 当前游戏状态
            mechanics_result: handle_mechanics 的返回值
            
        Returns:
            Dict[str, Any]: 更新后的游戏状态
        """
        pass
    
    def roll_dice(self, notation: str) -> Dict[str, Any]:
        """
        通用骰子投掷方法。
        
        Args:
            notation: 骰子表达式 (e.g., "2d6+3", "d100")
            
        Returns:
            Dict with rolls, total, and notation
        """
        import random
        import re
        
        notation = notation.lower().replace(" ", "")
        pattern = r"^(\d*)d(\d+)([+-]\d+)?$"
        match = re.match(pattern, notation)
        
        if not match:
            return {"error": f"无效骰子表达式: {notation}", "total": 0}
        
        num_dice = int(match.group(1)) if match.group(1) else 1
        die_size = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0
        
        rolls = [random.randint(1, die_size) for _ in range(num_dice)]
        total = sum(rolls) + modifier
        
        return {
            "notation": notation,
            "rolls": rolls,
            "modifier": modifier,
            "total": total
        }
