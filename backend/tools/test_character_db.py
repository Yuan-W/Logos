"""
Character Database Test Script
==============================
验证角色数据库的隔离性和完整性。

测试场景：
1. 创建 D&D 5e 战役和角色
2. 创建 CoC 7th 战役和角色
3. 验证两个角色互不干扰
4. 测试 JSONB 路径更新
"""

from backend.database.db_init import init_database, get_session
from backend.tools.character_manager import (
    create_campaign,
    create_character,
    get_character_sheet,
    get_character_prompt_block,
    update_stat,
    update_stats_bulk,
    list_characters_in_campaign
)


def main():
    print("=" * 60)
    print("角色数据库隔离性测试")
    print("=" * 60)
    
    # 初始化数据库
    print("\n[1/6] 初始化数据库...")
    init_database()
    session = get_session()
    
    # =========================================================================
    # 创建 D&D 5e 战役和角色
    # =========================================================================
    print("\n[2/6] 创建 D&D 5e 战役...")
    dnd_campaign = create_campaign(
        name="龙与地下城周末团",
        system_type="dnd5e",
        description="费伦大陆冒险",
        settings={"starting_level": 1, "world": "Forgotten Realms"},
        session=session
    )
    print(f"  ✓ 战役创建成功: {dnd_campaign.name} (ID: {dnd_campaign.id})")
    
    print("\n[3/6] 创建 D&D 角色: 艾尔文 (精灵战士)...")
    dnd_character = create_character(
        campaign_id=dnd_campaign.id,
        name="艾尔文",
        system_type="dnd5e",
        initial_stats={
            "STR": 16,
            "DEX": 14,
            "CON": 15,
            "INT": 10,
            "WIS": 12,
            "CHA": 8,
            "level": 3,
            "proficiency_bonus": 2
        },
        inventory={
            "weapons": ["长剑", "短弓"],
            "armor": {"name": "链甲", "ac": 16},
            "gold": 50
        },
        current_status={
            "hp": 28,
            "max_hp": 28,
            "temp_hp": 0,
            "conditions": []
        },
        skills={"athletics": True, "perception": True},
        backstory="来自银月城的精灵战士，追寻失落的家族荣耀。",
        session=session
    )
    print(f"  ✓ 角色创建成功: {dnd_character.name} (ID: {dnd_character.id})")
    
    # =========================================================================
    # 创建 CoC 7th 战役和角色
    # =========================================================================
    print("\n[4/6] 创建克苏鲁的呼唤战役...")
    coc_campaign = create_campaign(
        name="阿卡姆噩梦",
        system_type="coc7",
        description="1920年代阿卡姆镇调查",
        settings={"era": "1920s", "location": "Arkham"},
        session=session
    )
    print(f"  ✓ 战役创建成功: {coc_campaign.name} (ID: {coc_campaign.id})")
    
    print("\n[5/6] 创建 CoC 角色: 霍华德·菲利普 (私家侦探)...")
    coc_character = create_character(
        campaign_id=coc_campaign.id,
        name="霍华德·菲利普",
        system_type="coc7",
        initial_stats={
            "STR": 55,
            "CON": 60,
            "SIZ": 65,
            "DEX": 50,
            "APP": 45,
            "INT": 70,
            "POW": 55,
            "EDU": 65,
            "SAN": 55,
            "HP": 12,
            "MP": 11,
            "Luck": 50
        },
        inventory={
            "weapons": [".38 左轮手枪"],
            "items": ["手电筒", "笔记本", "放大镜"]
        },
        current_status={
            "hp": 12,
            "max_hp": 12,
            "san": 55,
            "max_san": 99,
            "conditions": []
        },
        skills={
            "侦查": 60,
            "图书馆使用": 50,
            "心理学": 45,
            "说服": 40,
            "射击（手枪）": 35
        },
        backstory="前警探，因目睹不可名状之事而离开警队，如今以私家侦探为生。",
        session=session
    )
    print(f"  ✓ 角色创建成功: {coc_character.name} (ID: {coc_character.id})")
    
    # =========================================================================
    # 验证隔离性
    # =========================================================================
    print("\n[6/6] 验证角色隔离性...")
    
    # 获取 D&D 角色卡
    dnd_sheet = get_character_sheet(dnd_character.id, session)
    print(f"\n--- D&D 角色卡 ({dnd_sheet['【角色名】']}) ---")
    print(f"规则系统: {dnd_sheet['【规则系统】']}")
    print(f"核心属性: {dnd_sheet['【核心属性】']}")
    
    # 验证 D&D 属性
    assert "STR" in dnd_sheet["【核心属性】"], "D&D 角色应有 STR 属性"
    assert "SAN" not in dnd_sheet["【核心属性】"], "D&D 角色不应有 SAN 属性"
    
    # 获取 CoC 角色卡
    coc_sheet = get_character_sheet(coc_character.id, session)
    print(f"\n--- CoC 角色卡 ({coc_sheet['【角色名】']}) ---")
    print(f"规则系统: {coc_sheet['【规则系统】']}")
    print(f"核心属性: {coc_sheet['【核心属性】']}")
    
    # 验证 CoC 属性
    assert "SAN" in coc_sheet["【核心属性】"], "CoC 角色应有 SAN 属性"
    assert "proficiency_bonus" not in coc_sheet["【核心属性】"], "CoC 角色不应有熟练加值"
    
    print("\n✓ 隔离性验证通过！两个角色的属性结构完全独立。")
    
    # =========================================================================
    # 测试 JSONB 更新
    # =========================================================================
    print("\n--- 测试 JSONB 路径更新 ---")
    
    # 更新 D&D 角色 HP
    original_hp = dnd_sheet["【当前状态】"]["hp"]
    update_stat(dnd_character.id, "hp", original_hp - 5, session)
    
    updated_sheet = get_character_sheet(dnd_character.id, session)
    new_hp = updated_sheet["【当前状态】"]["hp"]
    
    print(f"D&D 角色 HP: {original_hp} -> {new_hp}")
    assert new_hp == original_hp - 5, "HP 更新失败"
    print("✓ JSONB 路径更新成功！")
    
    # 批量更新
    update_stats_bulk(
        coc_character.id,
        {"san": 50, "conditions": ["轻度恐惧"]},
        target_field="current_status",
        session=session
    )
    
    updated_coc = get_character_sheet(coc_character.id, session)
    print(f"CoC 角色 SAN: 55 -> {updated_coc['【当前状态】']['san']}")
    print(f"CoC 角色状态: {updated_coc['【当前状态】']['conditions']}")
    
    # =========================================================================
    # 列出战役角色
    # =========================================================================
    print("\n--- 战役角色列表 ---")
    
    dnd_chars = list_characters_in_campaign(dnd_campaign.id, session=session)
    print(f"\n{dnd_campaign.name}:")
    for c in dnd_chars:
        print(f"  - {c['name']} ({c['type']}): {c['stats_summary']}")
    
    coc_chars = list_characters_in_campaign(coc_campaign.id, session=session)
    print(f"\n{coc_campaign.name}:")
    for c in coc_chars:
        print(f"  - {c['name']} ({c['type']}): {c['stats_summary']}")
    
    # =========================================================================
    # 输出 Prompt Block
    # =========================================================================
    print("\n--- Prompt-ready 角色块 (D&D) ---")
    print(get_character_prompt_block(dnd_character.id, session))
    
    print("\n" + "=" * 60)
    print("✓ 所有测试通过！角色数据库隔离性验证成功。")
    print("=" * 60)


if __name__ == "__main__":
    main()
