"""
Grand Unified Schema - Database Models
=====================================
SQLAlchemy models for multi-agent system with 3 domains:
1. Core & Identity
2. Creative Engine (TRPG & Novelist)
3. Knowledge Base (Researcher & Coder)
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# =============================================================================
# Domain 1: Core & Identity
# =============================================================================

class User(Base):
    """User authentication and identity."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False)
    conversations: Mapped[list["ConversationLog"]] = relationship(back_populates="user")


class UserProfile(Base):
    """Living document for Coach/Psychologist - stores psychological profile and memories."""
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    
    # Psychological profile: MBTI, Big 5, communication preferences
    psych_profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB, 
        default=dict,
        comment="MBTI, Big 5 traits, communication preferences"
    )
    
    # Long-term memories extracted from past sessions
    long_term_memories: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment="Extracted facts from past sessions"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="profile")


class ConversationLog(Base):
    """Log of all agent interactions."""
    __tablename__ = "conversation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    agent_role: Mapped[str] = mapped_column(String(32), nullable=False)  # coach, trpg, novelist, etc.
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="conversations")


# =============================================================================
# Domain 2: Creative Engine (TRPG & Novelist)
# =============================================================================

class Rulebook(Base):
    """Vector store for game rules (D&D 5e, Call of Cthulhu, etc.)."""
    __tablename__ = "rulebooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(3072))  # Gemini 001 embedding size
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, 
        default=dict,
        comment='{"system": "dnd5e" | "coc", "chapter": "...", "page": 123}'
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GameState(Base):
    """Active TRPG session state."""
    __tablename__ = "game_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    current_scene: Mapped[str] = mapped_column(Text, default="")
    
    # Player stats: HP, Inventory, Skills, etc.
    player_stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment='{"hp": 25, "max_hp": 30, "inventory": [...], "skills": {...}}'
    )
    
    # NPC status tracking
    npc_status: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment='{"goblin_chief": {"hp": 50, "hostile": true}, ...}'
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StoryBible(Base):
    """Entity knowledge graph for Novelist."""
    __tablename__ = "story_bible"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    entity_name: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)  # character, location, item, event
    description: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(3072))
    
    # Relations to other entities
    relations: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment='{"allies": ["entity_id"], "enemies": [...], "locations": [...]}'
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Campaign(Base):
    """
    战役/项目容器，用于隔离不同规则系统的角色。
    
    一个用户可以有多个战役（如：D&D 周末团、CoC 长期团）。
    """
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    system_type: Mapped[str] = mapped_column(
        String(32), 
        nullable=False,
        comment="dnd5e, coc7, bitd, pathfinder2e, custom"
    )
    description: Mapped[str] = mapped_column(Text, default="")
    
    # 战役级别的设定（世界观、房规等）
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment='{"house_rules": {...}, "world_name": "...", "starting_level": 1}'
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    characters: Mapped[list["Character"]] = relationship(
        back_populates="campaign", 
        cascade="all, delete-orphan"
    )


class Character(Base):
    """
    角色卡 - 支持多规则系统的通用角色存储。
    
    使用 JSONB 存储系统特定的属性，避免 AI 混淆不同规则的数值。
    所有字段都是 Ground Truth，优先级高于 AI 生成的内容。
    """
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    # 基础信息
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    character_type: Mapped[str] = mapped_column(
        String(32), 
        default="pc",
        comment="pc (玩家角色), npc, monster, ally"
    )
    portrait_url: Mapped[str] = mapped_column(String(512), nullable=True)
    
    # 核心属性 - JSONB 存储系统特定的数值
    # D&D: {"STR": 16, "DEX": 14, "CON": 15, "INT": 10, "WIS": 12, "CHA": 8}
    # CoC: {"STR": 55, "CON": 60, "SIZ": 65, "DEX": 50, "APP": 45, "INT": 70, "POW": 55, "EDU": 65}
    stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="系统特定属性值 (D&D: STR/DEX, CoC: SAN/EDU)"
    )
    
    # 装备和物品
    inventory: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment='{"weapons": [...], "armor": {...}, "items": [...], "gold": 100}'
    )
    
    # 当前状态 (HP, 临时效果等)
    current_status: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment='{"hp": 25, "max_hp": 30, "conditions": ["poisoned"], "temp_hp": 0}'
    )
    
    # 技能/职业/背景
    skills: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment="系统特定技能 (D&D: proficiencies, CoC: skill percentages)"
    )
    
    # 背景故事和笔记
    backstory: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    
    # 元数据
    is_alive: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    campaign: Mapped["Campaign"] = relationship(back_populates="characters")


# =============================================================================
# Domain 3: Knowledge Base (Researcher & Coder)
# =============================================================================

class Document(Base):
    """Vector store for PDFs, papers, articles."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(3072))
    source_page: Mapped[int] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CodeSnippet(Base):
    """Vector store for code blocks."""
    __tablename__ = "code_snippets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False)  # python, typescript, rust, etc.
    code_block: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(3072))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    source_file: Mapped[str] = mapped_column(String(512), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
