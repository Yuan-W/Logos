"""
Blades in the Dark Plugin
=========================
暗夜刀锋规则实现。

核心机制：
- Action Roll (1-6d6, 取最高)
- Position & Effect 系统
- Clocks (进度钟)
- Stress & Trauma
"""

from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from backend.plugins.trpg_base import (
    TRPGSystemPlugin, 
    MechanicsResult, 
    ActionResultType
)


@dataclass
class Clock:
    """进度钟数据结构"""
    name: str
    segments: int  # 总格数 (4, 6, 8)
    filled: int = 0  # 已填充格数
    clock_type: str = "progress"  # progress, danger, racing
    
    def tick(self, amount: int = 1) -> bool:
        """填充格子，返回是否完成"""
        self.filled = min(self.segments, self.filled + amount)
        return self.filled >= self.segments
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "segments": self.segments,
            "filled": self.filled,
            "type": self.clock_type
        }


class BladesInTheDarkPlugin(TRPGSystemPlugin):
    """暗夜刀锋规则插件"""
    
    @property
    def system_name(self) -> str:
        return "暗夜刀锋 (Blades in the Dark)"
    
    @property
    def default_dice_notation(self) -> str:
        return "2d6"  # 典型 Action Roll
    
    def handle_mechanics(
        self,
        action_type: str,
        player_stats: Dict[str, Any],
        difficulty: Optional[int] = None,
        modifiers: Optional[Dict[str, int]] = None
    ) -> MechanicsResult:
        """
        处理 BitD 的行动检定。
        
        Action Roll:
        - 6: 完全成功
        - 4-5: 部分成功（有代价）
        - 1-3: 失败
        - 双6: 暴击
        - 0骰: 掷2d6取低
        
        Position: Controlled / Risky / Desperate
        Effect: Limited / Standard / Great
        """
        modifiers = modifiers or {}
        
        if action_type == "clock_tick":
            return self._handle_clock_tick(player_stats, modifiers)
        
        # Action Roll
        action_name = modifiers.get("action", "Prowl")
        dice_pool = modifiers.get("dice", 2)
        position = modifiers.get("position", "risky")
        effect = modifiers.get("effect", "standard")
        
        # 投骰
        if dice_pool <= 0:
            # 0骰规则：掷2d6取最低
            roll = self.roll_dice("2d6")
            result_value = min(roll["rolls"])
            roll_desc = f"0骰规则，掷2d6取低 -> {roll['rolls']} -> 取 {result_value}"
        else:
            roll = self.roll_dice(f"{dice_pool}d6")
            result_value = max(roll["rolls"])
            
            # 检查暴击 (双6)
            if roll["rolls"].count(6) >= 2:
                return MechanicsResult(
                    result_type=ActionResultType.CRITICAL_SUCCESS,
                    narrative_hint=f"暴击！{action_name}行动掷出双6！除了完全成功外，获得额外好处。Position: {position}, Effect: {effect}+1。",
                    state_changes={"last_roll": roll["rolls"], "crit": True},
                    resource_costs={},
                    triggered_effects=["暴击加成"]
                )
            
            roll_desc = f"{dice_pool}d6 -> {roll['rolls']} -> 取 {result_value}"
        
        # 判定结果
        if result_value == 6:
            result_type = ActionResultType.SUCCESS
            narrative = f"完全成功！{action_name}行动骰出 6（{roll_desc}）。按 {effect} Effect 达成目标，无额外代价。"
            stress_cost = 0
        elif result_value >= 4:
            result_type = ActionResultType.PARTIAL_SUCCESS
            
            # 根据 Position 确定代价
            if position == "controlled":
                consequence = "轻微代价或减弱Effect"
            elif position == "desperate":
                consequence = "严重后果（大量伤害、困境升级）"
            else:
                consequence = "中等后果或复杂化"
            
            narrative = f"部分成功。{action_name}行动骰出 {result_value}（{roll_desc}）。达成目标但{consequence}。Position: {position}。"
            stress_cost = 0
        else:
            result_type = ActionResultType.FAILURE
            
            if position == "controlled":
                consequence = "情况恶化，你可以撤退"
            elif position == "desperate":
                consequence = "灾难性后果，可能受伤或陷入绝境"
            else:
                consequence = "事情出错，面临危险"
            
            narrative = f"失败。{action_name}行动骰出 {result_value}（{roll_desc}）。{consequence}。Position: {position}。"
            stress_cost = 0
        
        return MechanicsResult(
            result_type=result_type,
            narrative_hint=narrative,
            state_changes={"last_roll": roll["rolls"], "last_action": action_name},
            resource_costs={"stress": stress_cost},
            triggered_effects=[]
        )
    
    def _handle_clock_tick(
        self,
        player_stats: Dict[str, Any],
        modifiers: Dict[str, int]
    ) -> MechanicsResult:
        """处理进度钟推进"""
        clock_name = modifiers.get("clock_name", "Unknown Clock")
        tick_amount = modifiers.get("tick", 1)
        clocks = player_stats.get("clocks", {})
        
        if clock_name not in clocks:
            return MechanicsResult(
                result_type=ActionResultType.FAILURE,
                narrative_hint=f"进度钟 \"{clock_name}\" 不存在。",
                state_changes={},
                resource_costs={},
                triggered_effects=[]
            )
        
        clock_data = clocks[clock_name]
        clock = Clock(**clock_data)
        completed = clock.tick(tick_amount)
        
        if completed:
            narrative = f"进度钟 \"{clock_name}\" 完成！（{clock.filled}/{clock.segments}）事件触发。"
            effects = [f"{clock_name}_完成"]
        else:
            narrative = f"进度钟 \"{clock_name}\" 推进至 {clock.filled}/{clock.segments}。"
            effects = []
        
        return MechanicsResult(
            result_type=ActionResultType.SUCCESS,
            narrative_hint=narrative,
            state_changes={f"clock_{clock_name}": clock.to_dict()},
            resource_costs={},
            triggered_effects=effects
        )
    
    def get_system_prompt_additions(self, game_state: Dict[str, Any]) -> str:
        """返回 BitD 特定的 Prompt 增强内容"""
        stress = game_state.get("player_stats", {}).get("stress", 0)
        trauma = game_state.get("player_stats", {}).get("trauma", [])
        clocks = game_state.get("clocks", {})
        
        # 格式化进度钟状态
        clock_status = ""
        for name, data in clocks.items():
            filled = data.get("filled", 0)
            segments = data.get("segments", 4)
            clock_status += f"  - {name}: {'●' * filled}{'○' * (segments - filled)} ({filled}/{segments})\n"
        
        if not clock_status:
            clock_status = "  暂无活跃进度钟\n"
        
        stress_warning = ""
        if stress >= 7:
            stress_warning = "⚠ 压力值接近极限，下一次压力可能导致创伤！"
        
        return f"""
【暗夜刀锋规则提示】
- 当前压力值: {stress}/9 {stress_warning}
- 创伤: {', '.join(trauma) if trauma else '无'}
- 行动检定: 骰N个d6取最高，6=成功，4-5=部分成功，1-3=失败
- Position（立场）决定失败代价：Controlled < Risky < Desperate
- Effect（效果）决定成功程度：Limited < Standard < Great

【活跃进度钟】
{clock_status}
"""
    
    def process_state_update(
        self,
        current_state: Dict[str, Any],
        mechanics_result: MechanicsResult
    ) -> Dict[str, Any]:
        """更新 BitD 游戏状态"""
        new_state = current_state.copy()
        
        if "player_stats" not in new_state:
            new_state["player_stats"] = {}
        
        # 应用压力消耗
        if "stress" in mechanics_result.resource_costs:
            current_stress = new_state["player_stats"].get("stress", 0)
            new_stress = current_stress + mechanics_result.resource_costs["stress"]
            
            if new_stress >= 9:
                # 触发创伤
                new_state["player_stats"]["stress"] = 0
                if "trauma" not in new_state["player_stats"]:
                    new_state["player_stats"]["trauma"] = []
                new_state["player_stats"]["trauma"].append("待定创伤")
                mechanics_result.triggered_effects.append("获得创伤")
            else:
                new_state["player_stats"]["stress"] = new_stress
        
        # 更新进度钟
        for key, value in mechanics_result.state_changes.items():
            if key.startswith("clock_"):
                clock_name = key[6:]
                if "clocks" not in new_state:
                    new_state["clocks"] = {}
                new_state["clocks"][clock_name] = value
            else:
                new_state["player_stats"][key] = value
        
        return new_state
    
    # =================== 辅助方法 ===================
    
    def create_clock(
        self, 
        name: str, 
        segments: int = 4, 
        clock_type: str = "progress"
    ) -> Clock:
        """创建新的进度钟"""
        return Clock(name=name, segments=segments, clock_type=clock_type)
    
    def resistance_roll(self, attribute_rating: int) -> Dict[str, Any]:
        """
        抵抗投骰：用于减少后果。
        
        花费等于 6 减去最高骰的压力。
        暴击则恢复1点压力。
        """
        roll = self.roll_dice(f"{attribute_rating}d6")
        highest = max(roll["rolls"])
        
        if roll["rolls"].count(6) >= 2:
            stress_cost = -1  # 回复压力
            result = "暴击！回复1点压力，完全抵消后果。"
        elif highest == 6:
            stress_cost = 0
            result = "完美抵抗，无压力消耗。"
        else:
            stress_cost = 6 - highest
            result = f"抵抗成功，消耗 {stress_cost} 点压力。"
        
        return {
            "rolls": roll["rolls"],
            "highest": highest,
            "stress_cost": stress_cost,
            "result": result
        }
