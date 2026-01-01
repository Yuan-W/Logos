"""
Call of Cthulhu Plugin
======================
克苏鲁的呼唤 7th Edition 规则实现。

核心机制：
- d100 技能检定 (Regular/Hard/Extreme)
- 理智值 (Sanity) 系统
- 运气点机制
"""

from typing import Any, Dict, Optional
from backend.plugins.trpg_base import (
    TRPGSystemPlugin, 
    MechanicsResult, 
    ActionResultType
)


class CallOfCthulhuPlugin(TRPGSystemPlugin):
    """克苏鲁的呼唤 7th Edition 规则插件"""
    
    @property
    def system_name(self) -> str:
        return "克苏鲁的呼唤 (Call of Cthulhu 7th Edition)"
    
    @property
    def default_dice_notation(self) -> str:
        return "d100"
    
    def handle_mechanics(
        self,
        action_type: str,
        player_stats: Dict[str, Any],
        difficulty: Optional[int] = None,
        modifiers: Optional[Dict[str, int]] = None
    ) -> MechanicsResult:
        """
        处理 CoC 的技能检定和理智检定。
        
        难度等级:
        - Regular: 技能值
        - Hard: 技能值 / 2
        - Extreme: 技能值 / 5
        
        特殊结果:
        - 01: 大成功
        - 96-100 (技能<50) 或 100: 大失败
        """
        modifiers = modifiers or {}
        
        if action_type == "sanity_check":
            return self._handle_sanity_check(player_stats, modifiers)
        
        # 技能检定
        skill_name = modifiers.get("skill", "侦查")
        skill_value = player_stats.get("skills", {}).get(skill_name, 50)
        
        # 难度调整
        difficulty_level = modifiers.get("difficulty", "regular")
        if difficulty_level == "hard":
            target = skill_value // 2
        elif difficulty_level == "extreme":
            target = skill_value // 5
        else:
            target = skill_value
        
        roll = self.roll_dice("d100")
        roll_value = roll["total"]
        
        # 判定结果
        if roll_value == 1:
            result_type = ActionResultType.CRITICAL_SUCCESS
            narrative = f"大成功！骰出 01，{skill_name}检定完美成功。描述一个超乎寻常的精彩表现。"
        elif roll_value <= target // 5:
            result_type = ActionResultType.CRITICAL_SUCCESS
            narrative = f"极限成功！骰出 {roll_value}（目标 {target}，极限 {target // 5}）。{skill_name}检定表现极佳。"
        elif roll_value <= target // 2:
            result_type = ActionResultType.SUCCESS
            narrative = f"困难成功！骰出 {roll_value}（目标 {target}，困难 {target // 2}）。{skill_name}检定干净利落。"
        elif roll_value <= target:
            result_type = ActionResultType.PARTIAL_SUCCESS
            narrative = f"普通成功。骰出 {roll_value}（目标 {target}）。{skill_name}检定勉强通过。"
        elif roll_value >= 96 and skill_value < 50:
            result_type = ActionResultType.CRITICAL_FAILURE
            narrative = f"大失败！骰出 {roll_value}。{skill_name}检定彻底失败，发生灾难性后果。"
        elif roll_value == 100:
            result_type = ActionResultType.CRITICAL_FAILURE
            narrative = f"大失败！骰出 100。{skill_name}检定出现最坏的情况。"
        else:
            result_type = ActionResultType.FAILURE
            narrative = f"失败。骰出 {roll_value}（目标 {target}）。{skill_name}检定未能成功。"
        
        return MechanicsResult(
            result_type=result_type,
            narrative_hint=narrative,
            state_changes={"last_roll": roll_value, "last_skill": skill_name},
            resource_costs={},
            triggered_effects=[]
        )
    
    def _handle_sanity_check(
        self, 
        player_stats: Dict[str, Any],
        modifiers: Dict[str, int]
    ) -> MechanicsResult:
        """
        处理理智检定。
        
        理智检定失败会导致理智值损失 (通常在 1d6 到 1d100 之间)。
        """
        current_sanity = player_stats.get("sanity", 50)
        
        roll = self.roll_dice("d100")
        roll_value = roll["total"]
        
        san_loss_success = modifiers.get("san_loss_success", 0)  # 成功时损失
        san_loss_fail = modifiers.get("san_loss_fail", "1d6")    # 失败时损失
        
        if roll_value <= current_sanity:
            # 成功
            actual_loss = san_loss_success
            new_sanity = max(0, current_sanity - actual_loss)
            
            if actual_loss > 0:
                narrative = f"理智检定成功（骰 {roll_value}，目标 {current_sanity}）。理智值 -{actual_loss}，当前 {new_sanity}。虽然成功抵抗了恐惧，但仍留下了阴影。"
            else:
                narrative = f"理智检定成功（骰 {roll_value}，目标 {current_sanity}）。保持冷静，理智不变。"
            
            return MechanicsResult(
                result_type=ActionResultType.SUCCESS,
                narrative_hint=narrative,
                state_changes={"sanity": new_sanity},
                resource_costs={"sanity": actual_loss},
                triggered_effects=[]
            )
        else:
            # 失败
            loss_roll = self.roll_dice(san_loss_fail)
            actual_loss = loss_roll["total"]
            new_sanity = max(0, current_sanity - actual_loss)
            
            effects = []
            if actual_loss >= 5:
                effects.append("临时性疯狂")
            if new_sanity <= 0:
                effects.append("永久性疯狂")
            
            narrative = f"理智检定失败（骰 {roll_value}，目标 {current_sanity}）！理智值 -{actual_loss}（{san_loss_fail}），当前 {new_sanity}。"
            if effects:
                narrative += f" 触发效果: {', '.join(effects)}。"
            
            return MechanicsResult(
                result_type=ActionResultType.FAILURE,
                narrative_hint=narrative,
                state_changes={"sanity": new_sanity},
                resource_costs={"sanity": actual_loss},
                triggered_effects=effects
            )
    
    def get_system_prompt_additions(self, game_state: Dict[str, Any]) -> str:
        """返回 CoC 特定的 Prompt 增强内容"""
        sanity = game_state.get("player_stats", {}).get("sanity", 50)
        max_sanity = game_state.get("player_stats", {}).get("max_sanity", 99)
        
        sanity_status = ""
        if sanity <= 10:
            sanity_status = "调查员濒临崩溃，行为可能变得不稳定。"
        elif sanity <= 30:
            sanity_status = "调查员精神状态堪忧，恐惧开始侵蚀理智。"
        elif sanity <= 50:
            sanity_status = "调查员已见识过不可名状之物，心灵留下创伤。"
        
        return f"""
【克苏鲁的呼唤规则提示】
- 当前理智值: {sanity}/{max_sanity}
- {sanity_status}
- 技能检定使用 d100，低于技能值为成功
- 遭遇不可名状之物或阅读禁忌知识需要进行理智检定
- 失败的理智检定可能导致临时性或永久性疯狂
"""
    
    def process_state_update(
        self,
        current_state: Dict[str, Any],
        mechanics_result: MechanicsResult
    ) -> Dict[str, Any]:
        """更新 CoC 游戏状态"""
        new_state = current_state.copy()
        
        if "player_stats" not in new_state:
            new_state["player_stats"] = {}
        
        # 应用状态变更
        for key, value in mechanics_result.state_changes.items():
            if key == "sanity":
                new_state["player_stats"]["sanity"] = value
            else:
                new_state["player_stats"][key] = value
        
        # 记录触发效果
        if mechanics_result.triggered_effects:
            if "active_effects" not in new_state:
                new_state["active_effects"] = []
            new_state["active_effects"].extend(mechanics_result.triggered_effects)
        
        return new_state
