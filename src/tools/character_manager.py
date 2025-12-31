"""
Character Manager - CRUD & Validation
======================================
角色管理工具，提供：
1. CRUD 操作（创建、读取、更新角色）
2. Pydantic 验证（确保 stats 符合规则系统）
3. Prompt-ready 格式化输出（防止 AI 幻觉）

使用 PostgreSQL JSONB 路径更新，避免全量写入。
"""

from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from src.database.models import Campaign, Character
from src.database.db_init import get_session


# =============================================================================
# Pydantic Validation Schemas
# =============================================================================

class DnD5eStats(BaseModel):
    """D&D 5e 属性验证"""
    STR: int = Field(ge=1, le=30, description="力量")
    DEX: int = Field(ge=1, le=30, description="敏捷")
    CON: int = Field(ge=1, le=30, description="体质")
    INT: int = Field(ge=1, le=30, description="智力")
    WIS: int = Field(ge=1, le=30, description="感知")
    CHA: int = Field(ge=1, le=30, description="魅力")
    
    # 可选衍生属性
    proficiency_bonus: int = Field(default=2, ge=2, le=6)
    level: int = Field(default=1, ge=1, le=20)
    

class CoC7Stats(BaseModel):
    """克苏鲁的呼唤 7th Edition 属性验证"""
    STR: int = Field(ge=0, le=99, description="力量")
    CON: int = Field(ge=0, le=99, description="体质")
    SIZ: int = Field(ge=0, le=99, description="体型")
    DEX: int = Field(ge=0, le=99, description="敏捷")
    APP: int = Field(ge=0, le=99, description="外貌")
    INT: int = Field(ge=0, le=99, description="智力")
    POW: int = Field(ge=0, le=99, description="意志")
    EDU: int = Field(ge=0, le=99, description="教育")
    
    # 衍生属性
    SAN: int = Field(ge=0, le=99, description="理智值")
    HP: int = Field(ge=0, le=99, description="生命值")
    MP: int = Field(ge=0, le=99, description="魔法值")
    Luck: int = Field(ge=0, le=99, description="幸运")


class BitDStats(BaseModel):
    """暗夜刀锋属性验证"""
    # 行动属性 (0-4 点)
    Hunt: int = Field(default=0, ge=0, le=4)
    Study: int = Field(default=0, ge=0, le=4)
    Survey: int = Field(default=0, ge=0, le=4)
    Tinker: int = Field(default=0, ge=0, le=4)
    
    Finesse: int = Field(default=0, ge=0, le=4)
    Prowl: int = Field(default=0, ge=0, le=4)
    Skirmish: int = Field(default=0, ge=0, le=4)
    Wreck: int = Field(default=0, ge=0, le=4)
    
    Attune: int = Field(default=0, ge=0, le=4)
    Command: int = Field(default=0, ge=0, le=4)
    Consort: int = Field(default=0, ge=0, le=4)
    Sway: int = Field(default=0, ge=0, le=4)
    
    # 资源
    stress: int = Field(default=0, ge=0, le=9)
    trauma: List[str] = Field(default_factory=list)


class CharacterSchema(BaseModel):
    """
    通用角色 Schema，根据 system_type 验证 stats。
    """
    name: str = Field(min_length=1, max_length=128)
    character_type: Literal["pc", "npc", "monster", "ally"] = "pc"
    system_type: str = Field(description="dnd5e, coc7, bitd, custom")
    stats: Dict[str, Any] = Field(default_factory=dict)
    inventory: Dict[str, Any] = Field(default_factory=dict)
    current_status: Dict[str, Any] = Field(default_factory=dict)
    skills: Dict[str, Any] = Field(default_factory=dict)
    backstory: str = ""
    
    @model_validator(mode='after')
    def validate_stats_by_system(self) -> 'CharacterSchema':
        """根据规则系统验证属性"""
        if self.system_type == "dnd5e":
            DnD5eStats(**self.stats)
        elif self.system_type == "coc7":
            CoC7Stats(**self.stats)
        elif self.system_type == "bitd":
            BitDStats(**self.stats)
        # custom 类型不做额外验证
        return self


# =============================================================================
# CRUD Functions
# =============================================================================

def create_campaign(
    name: str,
    system_type: str,
    owner_id: Optional[int] = None,
    description: str = "",
    settings: Optional[Dict[str, Any]] = None,
    session: Optional[Session] = None
) -> Campaign:
    """创建新战役"""
    _session = session or get_session()
    
    campaign = Campaign(
        name=name,
        system_type=system_type,
        owner_id=owner_id,
        description=description,
        settings=settings or {}
    )
    
    _session.add(campaign)
    _session.commit()
    _session.refresh(campaign)
    
    return campaign


def create_character(
    campaign_id: int,
    name: str,
    system_type: str,
    initial_stats: Dict[str, Any],
    character_type: str = "pc",
    inventory: Optional[Dict[str, Any]] = None,
    current_status: Optional[Dict[str, Any]] = None,
    skills: Optional[Dict[str, Any]] = None,
    backstory: str = "",
    session: Optional[Session] = None
) -> Character:
    """
    创建角色并验证属性。
    
    Args:
        campaign_id: 所属战役 ID
        name: 角色名
        system_type: 规则系统 (dnd5e, coc7, bitd, custom)
        initial_stats: 初始属性 JSON
        character_type: 角色类型 (pc, npc, monster, ally)
        inventory: 物品 JSON
        current_status: 当前状态 JSON
        skills: 技能 JSON
        backstory: 背景故事
        
    Returns:
        Character: 创建的角色对象
        
    Raises:
        ValueError: 属性验证失败
    """
    _session = session or get_session()
    
    # 验证
    schema = CharacterSchema(
        name=name,
        character_type=character_type,
        system_type=system_type,
        stats=initial_stats,
        inventory=inventory or {},
        current_status=current_status or {},
        skills=skills or {},
        backstory=backstory
    )
    
    character = Character(
        campaign_id=campaign_id,
        name=schema.name,
        character_type=schema.character_type,
        stats=schema.stats,
        inventory=schema.inventory,
        current_status=schema.current_status,
        skills=schema.skills,
        backstory=schema.backstory
    )
    
    _session.add(character)
    _session.commit()
    _session.refresh(character)
    
    return character


def get_character_sheet(
    character_id: int,
    session: Optional[Session] = None
) -> Dict[str, Any]:
    """
    获取角色卡，返回 Prompt-ready 格式。
    
    此格式专为注入 LLM Prompt 设计，强调数据的权威性。
    
    Returns:
        Dict containing formatted character data for prompt injection.
    """
    _session = session or get_session()
    
    stmt = select(Character).where(Character.id == character_id)
    character = _session.execute(stmt).scalar_one_or_none()
    
    if not character:
        raise ValueError(f"角色不存在: ID={character_id}")
    
    # 获取战役信息
    campaign = character.campaign
    
    # 格式化为 Prompt-ready 结构
    return {
        "【角色名】": character.name,
        "【角色类型】": character.character_type,
        "【所属战役】": campaign.name if campaign else "未知",
        "【规则系统】": campaign.system_type if campaign else "未知",
        "【存活状态】": "存活" if character.is_alive else "死亡",
        "【核心属性】": character.stats,
        "【当前状态】": character.current_status,
        "【物品栏】": character.inventory,
        "【技能】": character.skills,
        "【背景故事】": character.backstory[:200] + "..." if len(character.backstory) > 200 else character.backstory,
        "_meta": {
            "character_id": character.id,
            "campaign_id": character.campaign_id,
            "last_updated": character.updated_at.isoformat() if character.updated_at else None
        }
    }


def get_character_prompt_block(
    character_id: int,
    session: Optional[Session] = None
) -> str:
    """
    返回可直接注入 Prompt 的角色信息块。
    
    格式化为 Markdown，便于 LLM 解析。
    """
    sheet = get_character_sheet(character_id, session)
    
    lines = [
        f"## {sheet['【角色名】']} ({sheet['【角色类型】'].upper()})",
        f"**规则系统**: {sheet['【规则系统】']} | **状态**: {sheet['【存活状态】']}",
        "",
        "### 核心属性",
    ]
    
    for key, value in sheet["【核心属性】"].items():
        lines.append(f"- **{key}**: {value}")
    
    lines.extend([
        "",
        "### 当前状态",
    ])
    
    for key, value in sheet["【当前状态】"].items():
        lines.append(f"- **{key}**: {value}")
    
    if sheet["【物品栏】"]:
        lines.extend([
            "",
            "### 物品栏",
            f"```json\n{sheet['【物品栏】']}\n```"
        ])
    
    return "\n".join(lines)


def update_stat(
    character_id: int,
    key_path: str,
    new_value: Any,
    session: Optional[Session] = None
) -> bool:
    """
    使用 PostgreSQL JSONB 路径更新特定字段。
    
    Args:
        character_id: 角色 ID
        key_path: JSONB 路径，如 "hp" 或 "conditions"
        new_value: 新值
        
    Returns:
        bool: 是否更新成功
        
    Example:
        update_stat(1, "hp", 20)  # 更新 current_status.hp 为 20
    """
    _session = session or get_session()
    
    # 直接使用 ORM 更新，避免复杂的 raw SQL
    stmt = select(Character).where(Character.id == character_id)
    character = _session.execute(stmt).scalar_one_or_none()
    
    if not character:
        return False
    
    # 更新 JSONB 字段
    current_status = dict(character.current_status) if character.current_status else {}
    current_status[key_path] = new_value
    character.current_status = current_status
    
    _session.commit()
    
    return True


def update_stats_bulk(
    character_id: int,
    updates: Dict[str, Any],
    target_field: Literal["stats", "current_status", "inventory", "skills"] = "current_status",
    session: Optional[Session] = None
) -> bool:
    """
    批量更新 JSONB 字段。
    
    Args:
        character_id: 角色 ID
        updates: 要更新的键值对
        target_field: 目标 JSONB 字段
        
    Returns:
        bool: 是否更新成功
    """
    _session = session or get_session()
    
    stmt = select(Character).where(Character.id == character_id)
    character = _session.execute(stmt).scalar_one_or_none()
    
    if not character:
        return False
    
    # 获取目标字段的当前值
    field_map = {
        "stats": "stats",
        "current_status": "current_status",
        "inventory": "inventory",
        "skills": "skills"
    }
    
    if target_field not in field_map:
        raise ValueError(f"无效的目标字段: {target_field}")
    
    current_data = dict(getattr(character, target_field) or {})
    current_data.update(updates)
    setattr(character, target_field, current_data)
    
    _session.commit()
    
    return True


def list_characters_in_campaign(
    campaign_id: int,
    character_type: Optional[str] = None,
    alive_only: bool = True,
    session: Optional[Session] = None
) -> List[Dict[str, Any]]:
    """
    列出战役中的所有角色。
    
    Args:
        campaign_id: 战役 ID
        character_type: 过滤角色类型 (可选)
        alive_only: 仅显示存活角色
        
    Returns:
        List of character summaries
    """
    _session = session or get_session()
    
    stmt = select(Character).where(Character.campaign_id == campaign_id)
    
    if character_type:
        stmt = stmt.where(Character.character_type == character_type)
    
    if alive_only:
        stmt = stmt.where(Character.is_alive == True)
    
    characters = _session.execute(stmt).scalars().all()
    
    return [
        {
            "id": c.id,
            "name": c.name,
            "type": c.character_type,
            "alive": c.is_alive,
            "stats_summary": _summarize_stats(c.stats, c.campaign.system_type if c.campaign else "custom")
        }
        for c in characters
    ]


def _summarize_stats(stats: Dict[str, Any], system_type: str) -> str:
    """生成属性摘要"""
    if system_type == "dnd5e":
        return f"Lv{stats.get('level', 1)} | STR {stats.get('STR', '-')} DEX {stats.get('DEX', '-')} CON {stats.get('CON', '-')}"
    elif system_type == "coc7":
        return f"SAN {stats.get('SAN', '-')} | HP {stats.get('HP', '-')} | POW {stats.get('POW', '-')}"
    elif system_type == "bitd":
        return f"Stress {stats.get('stress', 0)}/9 | Trauma: {len(stats.get('trauma', []))}"
    else:
        return str(stats)[:50] + "..."
