from __future__ import annotations

from enum import StrEnum


class SpeciesBranch(StrEnum):
    """Canonical species branches accepted by Xingyuan student records."""

    STONE_CAT = "石虎"
    SNOW_HARE = "雪兔"
    SAMOYED = "萨摩耶"
    GOLDEN_RETRIEVER = "金毛"
    BORDER_COLLIE = "边境牧羊犬"
    BLACK_PANTHER = "黑豹"
    RED_FOX = "赤狐"
    SIBERIAN_TIGER = "东北虎"
    SIKA_DEER = "梅花鹿"
    GERMAN_SHEPHERD = "德国牧羊犬"
    GRAY_WOLF = "灰狼"
    DWARF_RABBIT = "侏儒兔"
    RED_DEER = "红鹿"
    LABRADOR_RETRIEVER = "拉布拉多猎犬"
    BENGAL_TIGER = "孟加拉虎"
    BROWN_BEAR = "棕熊"
    GIANT_PANDA = "大熊猫"
    WHITE_BIGHORN_SHEEP = "白大角羊"
    LEOPARD = "豹"
    SPOTTED_HYENA = "斑鬣狗"
    BALD_EAGLE = "白头海雕"
    COTTONTAIL_RABBIT = "棉尾兔"
    AFRICAN_BUFFALO = "非洲水牛"
    CHEETAH = "猎豹"
    SHEEP = "绵羊"
    LION = "狮"
    THREE_TOED_SLOTH = "三趾树懒"
    SHREW = "鼩鼱"
    GAZELLE = "瞪羚"
    FENNEC_FOX = "耳廓狐"
    STOAT = "白鼬"
    RED_PANDA = "小熊猫"
    SOUTH_CHINA_TIGER = "华南虎"
    SNOW_LEOPARD = "雪豹"
    GALAPAGOS_TORTOISE = "加拉帕戈斯象龟"
    GOLDEN_SNUB_NOSED_MONKEY = "川金丝猴"
    CHINESE_MANTIS = "中华大刀螳"
    RED_CROWNED_CRANE = "丹顶鹤"
    BAMBOO_VIPER = "赤尾青竹丝"
    GOOSE = "鹅"
    RACCOON_DOG = "日本狸"
    WOLF = "狼"
    MINK = "水貂"
    CHICKEN = "鸡"
    WOMBAT = "袋熊"
    DOLPHIN = "海豚"
    WANDERING_ALBATROSS = "漂泊信天翁"
    SECRETARY_BIRD = "蛇鹫"
    GORILLA = "大猩猩"
    DONKEY = "驴"
    NORTH_AMERICAN_RIVER_OTTER = "北美水獭"
    RED_WOLF = "红狼"
    KIT_FOX = "敏狐"
    CANADA_LYNX = "加拿大猞猁"
    BIGHORN_SHEEP = "大角羊"
    GILA_MONSTER = "希拉毒蜥"
    DOMESTIC_CAT = "家猫"
    WEASEL = "鼬"
    BEAR = "熊"
    CROCODILE = "鳄鱼"
    HEDGEHOG = "刺猬"
    TWO_TAILED_FOX = "双尾狐"
    ECHIDNA = "针鼹"
    BAT = "蝙蝠"
    CHAMELEON = "变色龙"
    JACKAL = "胡狼"
    RABBIT = "兔"
    FOX = "狐"


def parse_species_branch(value: SpeciesBranch | str) -> SpeciesBranch:
    """Normalize a branch value and reject values outside the domain enum."""

    if isinstance(value, SpeciesBranch):
        return value
    text = str(value).strip()
    try:
        return SpeciesBranch(text)
    except ValueError as error:
        raise ValueError(f"未知种族支系：{text or '（空）'}") from error


SPECIES_BRANCH_VALUES = tuple(branch.value for branch in SpeciesBranch)
