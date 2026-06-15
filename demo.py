from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ===== 像素字符合集 =====
PIXEL = {
    "wall": "#",
    "door": "+",
    "floor": ".",
    "emperor": "E",
    "prince1": "A",
    "prince2": "B",
    "princess": "C",
    "taifu": "T",
    "wushi": "W",
    "mother_a": "M",
    "mother_b": "N",
    "eunuch": "S",
    "guard": "G",
}

LOCATION_SYMBOL = {
    "御书房": "Y",
    "书院": "J",
    "校场": "X",
    "御花园": "U",
    "母妃宫": "P",
    "皇子居所": "Q",
}

LOCATION_ROWS = [
    ["御书房", "书院", "校场"],
    ["御花园", "母妃宫", "皇子居所"],
]

LOCATION_GRAPH = {
    "御书房": ["书院"],
    "书院": ["御书房", "校场", "御花园"],
    "校场": ["书院"],
    "御花园": ["书院", "母妃宫", "皇子居所"],
    "母妃宫": ["御花园"],
    "皇子居所": ["御花园"],
}

SOURCE_RULES = {
    "太傅": {
        "symbol": "t",
        "reliability": 0.82,
        "focus": {"read": 1.2, "discipline": 0.7, "politics": 0.3},
    },
    "武师": {
        "symbol": "w",
        "reliability": 0.8,
        "focus": {"martial": 1.25, "discipline": 1.0},
    },
    "母妃": {
        "symbol": "m",
        "reliability": 0.88,
        "focus": {"mood": 1.1, "lonely": 1.2},
    },
    "太监": {
        "symbol": "s",
        "reliability": 0.67,
        "focus": {"relation": 1.1, "rivals": 0.95},
    },
    "皇帝": {
        "symbol": "E",
        "reliability": 1.0,
        "focus": {"state": 1.0},
    },
}

EVENT_POOL: Dict[str, List[str]] = {
    "读书": [
        "你送来的太傅今天有意在公开场合称赞了{name}的文章。",
        "{name}在书院听课时迟迟未答，只得重复三次经文。",
    ],
    "练武": [
        "侍卫统领发现{name}站姿稳，给他讲了几招骑射。",
        "{name}在校场冲动行事，被督军提醒要先练内功。",
    ],
    "偷听朝政": [
        "{name}在御书房外偷听朝政，听到边关粮草消息后若有所思。",
        "{name}被守卫发现靠近御书房，面色有些慌乱。",
    ],
    "看花园": [
        "{name}在御花园里避开人群，发泄了一整天的紧张。",
        "{name}见到同侪后心情转好，但晚间仍独自呆着。",
    ],
    "找母妃": [
        "{name}向母妃倾诉了宫中的孤单与不安。",
        "{name}在母妃宫里很安静，回去后情绪明显平稳。",
    ],
    "写日记": [
        "{name}把今日所见写进日记，没对他人提起。",
        "{name}在居所里自言自语，像在构思什么。",
    ],
}


@dataclass
class Memory:
    day: int
    category: str
    text: str
    impact: Dict[str, int]
    importance: int = 50
    delay: int = 0
    delayed: bool = False
    triggered: bool = False


@dataclass
class Report:
    day: int
    source: str
    target: str
    text: str
    truth: int
    source_symbol: str


@dataclass
class Child:
    cid: str
    name: str
    icon: str
    age: int
    visible: Dict[str, int]
    hidden: Dict[str, int]
    needs: Dict[str, int]
    interests: Dict[str, int]
    tags: List[str]
    state: str
    mood: str
    location: str
    relationships: Dict[str, Dict[str, int]] = field(default_factory=dict)
    memories: List[Memory] = field(default_factory=list)
    history: List[str] = field(default_factory=list)

    def _clamp(self, d: Dict[str, int]) -> None:
        for k, v in list(d.items()):
            if k in ("stress", "lonely", "energy", "health", "age"):
                self.needs[k] = max(0, min(100, self.needs[k]))
            if k in ("wisdom", "martial", "politics", "courage", "kindness", "charm", "prestige"):
                self.visible[k] = max(0, min(100, self.visible[k]))

    def apply_deltas(self, dct: Dict[str, int]) -> None:
        for k, v in dct.items():
            if k in self.visible:
                self.visible[k] = max(0, min(100, self.visible[k] + v))
            elif k in self.hidden:
                self.hidden[k] = max(0, min(100, self.hidden[k] + v))
            elif k in self.needs:
                self.needs[k] = max(0, min(100, self.needs[k] + v))

    def relation(self, other: str) -> Dict[str, int]:
        r = self.relationships.setdefault(other, {"亲近": 50, "嫉妒": 40, "信任": 50, "依赖": 40, "敌意": 20})
        return r

    def adjust_relation(self, other: str, delta: Dict[str, int]) -> None:
        rel = self.relation(other)
        for k, v in delta.items():
            rel[k] = max(-100, min(100, rel[k] + v))

    def is_stressed(self) -> bool:
        return self.needs["stress"] > 70

    def choose_destination(self, rng: random.Random, day: int, open_locations: Dict[str, bool], policy: Dict[str, bool]) -> str:
        # 强压力和低精力会偏向舒缓/避险
        scores: Dict[str, float] = {}
        for nxt in LOCATION_GRAPH[self.location] + [self.location]:
            if nxt == "皇子居所" and not open_locations.get("皇子居所", True):
                continue
            if not policy["allow_outside"] and nxt == "母妃宫":
                # 简化：母妃宫仍可去，只是信息受限
                pass

            score = 0.0
            if nxt == "书院":
                score += self.interests["study"] * 0.55
                score += self.hidden["obedience"] * 0.25
                score += 5
            if nxt == "校场":
                score += self.interests["martial"] * 0.6
                score += self.visible["courage"] * 0.2
            if nxt == "御花园":
                score += self.needs["stress"] * 0.45
                score += self.interests["play"] * 0.4
            if nxt == "母妃宫":
                score += (100 - self.hidden["security"]) * 0.2
                score += self.hidden["family_need"] * 0.3
            if nxt == "皇子居所":
                score += self.needs["lonely"] * 0.25
            if nxt == "御书房":
                score += self.interests["politics"] * 0.25
                score += self.visible["charisma"] * 0.1

            # 关系记忆：孩子被召见后更愿意见帝后留在御书房
            score += 0.4 * self.relation("皇帝").get("依赖", 40)

            # 低精力时减少移动成本
            if self.needs["energy"] < 35:
                if nxt != self.location:
                    score -= 12
            score += rng.randint(-5, 8)
            scores[nxt] = score

        # 让概率化不是死锁
        m = max(scores.values())
        top = [k for k, v in scores.items() if v == m]
        if rng.random() < 0.25:
            return rng.choice(top)
        return max(scores, key=scores.get)

    def choose_action(self, rng: random.Random, target_location: str) -> str:
        actions = {
            "御书房": {
                "偷听朝政": self.hidden["curiosity"] * 0.7 + self.interests["politics"] * 0.6 + 6,
                "待机": self.needs["energy"] * 0.1 + 10,
            },
            "书院": {
                "读书": self.interests["study"] * 0.7 + self.hidden["obedience"] * 0.3 + 10,
                "旁听": self.interests["politics"] * 0.3 + self.hidden["curiosity"] * 0.3 + 8,
            },
            "校场": {
                "练武": self.interests["martial"] * 0.8 + self.visible["courage"] * 0.2 + 10,
                "结交武将": self.hidden["ambition"] * 0.3 + self.visible["courage"] * 0.4 + 6,
            },
            "御花园": {
                "看花园": 80 - self.needs["stress"] * 0.4 + 30,
                "待机": 18 + self.needs["lonely"] * 0.2,
            },
            "母妃宫": {
                "找母妃": 80 - self.hidden["security"] * 0.2 + self.hidden["family_need"] * 0.6,
                "待机": 12,
            },
            "皇子居所": {
                "写日记": self.hidden["independence"] * 0.4 + 8,
                "发呆": 30,
            },
        }

        base = actions[target_location]
        if self.is_stressed() and "看花园" in base:
            base["看花园"] += 25

        if self.needs["lonely"] > 75 and "找母妃" in base:
            base["找母妃"] += 25

        if self.needs["stress"] > 80 and "发呆" in base:
            base["发呆"] += 20

        # 取最高动作，偶尔试验性选择
        m = max(base.values())
        picks = [k for k, v in base.items() if v == m]
        if rng.random() < 0.3:
            return rng.choice(picks)
        return max(base, key=base.get)


@dataclass
class GameState:
    day: int = 1
    days: int = 100
    rng: random.Random = field(default_factory=random.Random)
    children: List[Child] = field(default_factory=list)
    emperor_perception: Dict[str, Dict[str, int]] = field(default_factory=dict)
    policy: Dict[str, bool] = field(default_factory=lambda: {
        "strict_gate": False,
        "allow_outside": False,
    })
    reports: List[Report] = field(default_factory=list)
    open_locations: Dict[str, bool] = field(default_factory=lambda: {name: True for name in LOCATION_SYMBOL})

    def today_stamp(self) -> str:
        return f"第{self.day:03d}日"

    def all_positions(self) -> Dict[str, List[str]]:
        pos: Dict[str, List[str]] = {loc: [] for loc in LOCATION_SYMBOL}
        pos["御书房"].append(PIXEL["emperor"])
        pos["书院"].append(PIXEL["taifu"])
        pos["校场"].append(PIXEL["wushi"])
        pos["母妃宫"].append(PIXEL["mother_a"])
        pos["御花园"].append(PIXEL["eunuch"])
        pos["皇子居所"].append(PIXEL["guard"])

        for c in self.children:
            pos[c.location].append(c.icon)
        return pos

    def character_panel(self, c: Child) -> str:
        rel_emperor = c.relation("皇帝")
        return (
            f"{c.name}({c.cid}) loc={c.location} mood={c.mood} "
            f"stress={c.needs['stress']:>3d} lonely={c.needs['lonely']:>3d} "
            f"energy={c.needs['energy']:>3d} 威={c.visible['prestige']:>3d} "
            f"智={c.visible['wisdom']:>3d} 武={c.visible['martial']:>3d} 政={c.visible['politics']:>3d} "
            f"信任={rel_emperor['信任']:>3d} 亲近={rel_emperor['亲近']:>3d}"
        )


def render_map(game: GameState) -> str:
    pos = game.all_positions()

    def cell(loc: str) -> str:
        actors = pos.get(loc, [])
        base = LOCATION_SYMBOL[loc]
        if not actors:
            return f" {base}"
        if len(actors) == 1:
            return f"{actors[0]}{base}"
        if len(actors) == 2:
            return f"{actors[0]}{actors[1]}"
        return f"{actors[0]}+"

    def row_text(row: List[str]) -> str:
        return "+" + "+".join(f" {cell(c):^7} " for c in row) + "+"

    lines = [
        "像素宫殿地图（字符仅示意）",
        row_text(LOCATION_ROWS[0]),
        row_text(LOCATION_ROWS[0]),
        "+" + "+".join(["=" * 9 for _ in LOCATION_ROWS[0]]) + "+",
        row_text(LOCATION_ROWS[1]),
        row_text(LOCATION_ROWS[1]),
        "".ljust(0),
    ]
    return "\n".join(lines).rstrip()


def build_children(rng: random.Random) -> List[Child]:
    c1 = Child(
        cid="大皇子",
        name="大皇子",
        icon=PIXEL["prince1"],
        age=10,
        visible={
            "wisdom": 40, "martial": 32, "politics": 28,
            "courage": 45, "kindness": 58, "charisma": 52,
            "health": 85, "prestige": 35,
        },
        hidden={
            "ambition": 45, "security": 55, "jealousy": 30,
            "independence": 42, "obedience": 62, "curiosity": 35,
            "cruelty": 12, "self_esteem": 64, "power_desire": 38,
            "family_need": 52,
        },
        needs={"stress": 22, "lonely": 18, "energy": 90, "health_state": 100},
        interests={"study": 48, "martial": 32, "politics": 24, "play": 34},
        tags=["聪慧", "谨慎"],
        state="normal",
        mood="平稳",
        location="御书房",
    )

    c2 = Child(
        cid="二皇子",
        name="二皇子",
        icon=PIXEL["prince2"],
        age=9,
        visible={
            "wisdom": 32, "martial": 44, "politics": 20,
            "courage": 58, "kindness": 36, "charisma": 48,
            "health": 84, "prestige": 28,
        },
        hidden={
            "ambition": 66, "security": 40, "jealousy": 42,
            "independence": 58, "obedience": 28, "curiosity": 64,
            "cruelty": 28, "self_esteem": 52, "power_desire": 61,
            "family_need": 46,
        },
        needs={"stress": 25, "lonely": 24, "energy": 92, "health_state": 97},
        interests={"study": 36, "martial": 52, "politics": 22, "play": 44},
        tags=["好武", "争强"],
        state="normal",
        mood="平稳",
        location="书院",
    )

    c3 = Child(
        cid="三公主",
        name="三公主",
        icon=PIXEL["princess"],
        age=9,
        visible={
            "wisdom": 36, "martial": 24, "politics": 26,
            "courage": 32, "kindness": 72, "charisma": 62,
            "health": 90, "prestige": 42,
        },
        hidden={
            "ambition": 34, "security": 68, "jealousy": 46,
            "independence": 50, "obedience": 56, "curiosity": 58,
            "cruelty": 8, "self_esteem": 60, "power_desire": 26,
            "family_need": 72,
        },
        needs={"stress": 18, "lonely": 15, "energy": 88, "health_state": 98},
        interests={"study": 42, "martial": 24, "politics": 30, "play": 60},
        tags=["仁厚", "敏感"],
        state="normal",
        mood="平稳",
        location="母妃宫",
    )

    return [c1, c2, c3]


def _clamp_child(child: Child) -> None:
    for k in ["stress", "lonely", "energy", "health_state"]:
        child.needs[k] = max(0, min(100, child.needs[k]))
    for k in list(child.visible.keys()) + list(child.hidden.keys()):
        if k in child.visible:
            child.visible[k] = max(0, min(100, child.visible[k]))
        else:
            child.hidden[k] = max(0, min(100, child.hidden[k]))


def apply_action_effects(game: GameState, child: Child, location: str, action: str) -> Tuple[List[str], List[Memory]]:
    logs: List[str] = []
    mems: List[Memory] = []

    # 基础消耗
    child.needs["energy"] -= 14
    child.needs["stress"] = max(0, child.needs["stress"] - 2)

    if location == "书院":
        if action == "读书":
            child.apply_deltas({"wisdom": 3, "prestige": 1})
            child.apply_deltas({"study": 1})
            child.needs["stress"] -= 5
            child.adjust_relation("太傅", {"亲近": 3, "信任": 2})
            logs.append(f"{child.name}在书院读书，今日收获稳定。")
            if game.rng.random() < 0.5:
                delta = {"wisdom": 1, "self_esteem": 4, "courage": 1}
                mems.append(Memory(
                    day=game.day,
                    category="被夸奖",
                    text=f"太傅对{child.name}发表公开好评，{child.name}当晚记下了老师的鼓励。",
                    impact=delta,
                    importance=55,
                    delay=0,
                ))
        else:
            child.apply_deltas({"politics": 1, "politics": 2})
            child.needs["stress"] -= 2
            logs.append(f"{child.name}在书院旁听，开始关注朝廷话题。")

    elif location == "校场":
        if action == "练武":
            child.apply_deltas({"martial": 4, "courage": 3, "prestige": 1})
            child.adjust_relation("武师", {"亲近": 6, "信任": 3})
            child.needs["stress"] += 6
            child.apply_deltas({"energy": -8})
            logs.append(f"{child.name}在校场勤练骑射，体力消耗不小。")
            if game.rng.random() < 0.45:
                mems.append(Memory(
                    day=game.day,
                    category="被崇拜",
                    text=f"侍卫统领对{child.name}有了持续关注，开始看重其胆识。",
                    impact={"martial": 3, "ambition": 4, "power_desire": 2},
                    importance=58,
                    delay=0,
                ))
        else:
            child.apply_deltas({"martial": 1, "courage": 2})
            logs.append(f"{child.name}在校场与武士切磋，建立了新的交往线。")
            child.adjust_relation("武师", {"依赖": 2})

    elif location == "御花园":
        if action == "看花园":
            child.needs["stress"] = max(0, child.needs["stress"] - 12)
            child.needs["lonely"] = max(0, child.needs["lonely"] - 8)
            child.apply_deltas({"charisma": 1})
            child.needs["energy"] += 2
            logs.append(f"{child.name}在御花园舒缓心情，短期压力下降。")
            if game.rng.random() < 0.2:
                mems.append(Memory(
                    day=game.day,
                    category="偶遇",
                    text=f"{child.name}在花园遇到同龄兄长，关系有微妙变化。",
                    impact={"kindness": 2, "jealousy": 2},
                    importance=35,
                    delay=0,
                ))

    elif location == "母妃宫":
        if action == "找母妃":
            child.needs["lonely"] = max(0, child.needs["lonely"] - 15)
            child.apply_deltas({"family_need": -1})
            child.adjust_relation("母妃", {"亲近": 8, "依赖": 4, "信任": 4})
            child.hidden["security"] += 3
            logs.append(f"{child.name}向母妃表露心迹，安全感上升。")
        else:
            child.needs["lonely"] += 2
            logs.append(f"{child.name}在母妃宫待了很久，情绪较平静。")

    elif location == "御书房":
        if action == "偷听朝政":
            if child.hidden["curiosity"] > 50 and child.interests["politics"] > 20:
                child.apply_deltas({"politics": 4, "ambition": 4})
                child.needs["stress"] += 6
                child.adjust_relation("皇帝", {"信任": -2, "亲近": -1, "敌意": 3})
                mems.append(Memory(
                    day=game.day,
                    category="信息",
                    text=f"{child.name}偷听朝政后，开始关注大臣取向与军务细节。",
                    impact={"politics": 2, "ambition": 2, "power_desire": 3},
                    importance=65,
                    delay=3,
                ))
                logs.append(f"{child.name}偷听朝政，学到了不少。")
            else:
                child.needs["stress"] += 2
                logs.append(f"{child.name}尝试靠近御书房，但大多听不懂。")

    elif location == "皇子居所":
        if action == "写日记":
            child.needs["stress"] += 2
            child.adjust_relation("皇帝", {"敌意": 2, "信任": -1})
            mems.append(Memory(
                day=game.day,
                category="自省",
                text=f"{child.name}在居所记录当日见闻，记下了数条对人心的观察。",
                impact={"self_esteem": 2, "independence": 2},
                importance=45,
                delay=14,
            ))
            logs.append(f"{child.name}在居所写下了私密日记。")
        else:
            child.needs["stress"] += 1
            logs.append(f"{child.name}在居所发呆，精神有些漂移。")

    _clamp_child(child)
    return logs, mems


def trigger_event_text(game: GameState, child: Child, location: str, action: str) -> List[str]:
    pool = EVENT_POOL.get(action, [])
    if not pool:
        return []

    events = []
    if game.rng.random() < 0.55:
        events.append(game.rng.choice(pool).format(name=child.name))

    # 附加关系事件：兄弟姐妹同处同位，嫉妒/亲近变化
    siblings = [c for c in game.children if c.cid != child.cid and c.location == child.location]
    if siblings and game.rng.random() < 0.35:
        other = game.rng.choice(siblings)
        if child.hidden["jealousy"] > 38 and child.tags.count("争强"):
            child.apply_deltas({"jealousy": 2})
            child.adjust_relation(other.cid, {"嫉妒": 4, "敌意": 2})
            events.append(f"{child.name}注意到{other.name}在同处一地时显得更受关注，内心起了波澜。")
        else:
            child.adjust_relation(other.cid, {"亲近": 3})
            events.append(f"{child.name}与{other.name}有了短暂交流，关系更稳。")

    # 偶发风险
    if child.is_stressed() and game.rng.random() < 0.1:
        child.apply_deltas({"stress": 4, "lonely": 3})
        child.adjust_relation("皇帝", {"信任": -2})
        events.append(f"{child.name}因压力过高，今日多次回避老师的要求。")

    return events


def generate_reports(game: GameState, child: Child, action_logs: List[str]) -> List[Report]:
    out: List[Report] = []
    candidates = []
    for source, cfg in SOURCE_RULES.items():
        base_score = cfg["reliability"]
        if source == "太傅" and child.location == "书院":
            base_score += 0.12
        if source == "武师" and child.location == "校场":
            base_score += 0.1
        if source == "母妃" and child.location == "母妃宫":
            base_score += 0.15
        if source == "太监" and child.location == "御花园":
            base_score += 0.09
        candidates.append((source, base_score))

    candidates.sort(key=lambda x: x[1], reverse=True)
    selected_sources = [s for s, _ in candidates[:game.rng.randint(2, 4)]]

    for source in selected_sources:
        cfg = SOURCE_RULES[source]
        reliability = int(cfg["reliability"] * 100)

        if game.rng.random() < cfg["reliability"]:
            tone = "中性"
            if source in ("太傅", "武师") and child.is_stressed():
                tone = "温和"
            if source == "太监" and game.rng.random() < 0.35:
                tone = "怀疑"
            text = build_report_text(source, child, action_logs, tone)
        else:
            # 偏差/误报
            text = build_noisy_text(source, child, action_logs)

        out.append(Report(
            day=game.day,
            source=source,
            target=child.cid,
            text=text,
            truth=reliability,
            source_symbol=cfg["symbol"],
        ))

    return out


def build_report_text(source: str, child: Child, action_logs: List[str], tone: str) -> str:
    if source == "太傅":
        if "读书" in "".join(action_logs):
            return f"太傅报：{child.name}近来在书院勤学，状态可观（{tone}）。"
        return f"太傅报：{child.name}今日在书院表现一般，仍需约束自持。"
    if source == "武师":
        if child.visible["martial"] > 45:
            return f"武师报：{child.name}在校场练习仍可，再加重心可见进展（{tone}）。"
        return f"武师报：{child.name}在校场动作生硬，耐心与纪律仍不足。"
    if source == "母妃":
        if child.mood in ("平稳", "愉快") and child.needs["lonely"] < 40:
            return f"母妃来信：{child.name}今天情绪稳定，似有安全感。"
        return f"母妃来信：{child.name}近来有些孤单，时有叹息。"
    if source == "太监":
        if child.needs["stress"] > 55:
            return f"太监密报：{child.name}走动频繁，似有逃避情绪，行迹值得留意。"
        return f"太监密报：{child.name}最近少有冲突，朝政旁听迹象不强。"
    if source == "皇帝":
        return f"皇帝自阅：{child.name}今日于{child.location}，压力{child.needs['stress']}，疲劳{child.needs['energy']}。"
    return f"{child.name}近日尚安。"


def build_noisy_text(source: str, child: Child, action_logs: List[str]) -> str:
    if source == "母妃":
        return f"母妃传闻：{child.name}今日似乎情绪非常稳定。"
    if source == "太监":
        return f"太监闲语：{child.name}到底在说什么没人完全听懂。"
    if source == "武师":
        return f"武场谣言：{child.name}在场外逗留比实战更多。"
    if source == "太傅":
        return f"师门说法：{child.name}或许有意回避课程，待查。"
    return f"{child.name}信息互相矛盾，难以确认。"


def process_delayed_memories(game: GameState, child: Child) -> List[str]:
    events = []
    for mem in child.memories:
        if mem.triggered:
            continue
        if mem.delay <= 0:
            continue
        if game.day - mem.day < mem.delay:
            continue
        if mem.delay <= game.day - mem.day:
            mem.triggered = True
            child.apply_deltas(mem.impact)
            events.append(f"旧记忆回响：{mem.text}")
    return events


def apply_intervention_interactive(game: GameState, child_lookup: Dict[str, Child]) -> str:
    print("\n皇帝可干预（1次）")
    print("0=不干预, 1=召见, 2=夸奖, 3=责罚, 4=赐书, 5=赐剑, 6=放宽宫规, 7=加严宫规")
    try:
        choice = input("输入编号: ").strip()
    except EOFError:
        return "不干预"

    if choice == "0" or choice == "":
        return "不干预"

    if choice in {"6", "7"}:
        if choice == "6":
            game.policy["strict_gate"] = False
            return "放宽宫规"
        game.policy["strict_gate"] = True
        return "加严宫规"

    if choice not in {"1", "2", "3", "4", "5"}:
        return "不干预"

    name = input("选择对象（大皇子/二皇子/三公主）: ").strip()
    target = child_lookup.get(name)
    if not target:
        return "不干预"

    if choice == "1":
        target.adjust_relation("皇帝", {"亲近": 8, "信任": 6, "敌意": -2})
        target.hidden["security"] += 6
        target.needs["lonely"] = max(0, target.needs["lonely"] - 10)
        target.needs["stress"] = max(0, target.needs["stress"] - 5)
        target.mood = "平稳"
        target.history.append(f"被皇帝召见，气氛融洽。")
        return f"召见{target.name}"

    if choice == "2":
        target.hidden["self_esteem"] += 8
        target.visible["wisdom"] += 2
        target.adjust_relation("皇帝", {"亲近": 6, "信任": 4})
        target.history.append("受到皇帝夸奖。")
        return f"夸奖{target.name}"

    if choice == "3":
        target.needs["stress"] += 10
        target.hidden["self_esteem"] -= 6
        target.adjust_relation("皇帝", {"信任": -6, "敌意": 4})
        target.history.append("遭到皇帝责罚。")
        return f"责罚{target.name}"

    if choice == "4":
        target.interests["study"] += 5
        target.visible["wisdom"] += 2
        target.hidden["obedience"] += 3
        target.history.append("获得皇帝赐书。")
        return f"赐书给{target.name}"

    if choice == "5":
        target.interests["martial"] += 7
        target.visible["martial"] += 2
        target.visible["courage"] += 2
        target.history.append("获得皇帝赐剑。")
        return f"赐剑给{target.name}"

    return "不干预"


def apply_intervention_auto(game: GameState, child_lookup: Dict[str, Child]) -> str:
    # 简化自动策略：优先处理压力高的孩子，防止系统崩坏
    target = sorted(game.children, key=lambda c: c.needs["stress"], reverse=True)[0]

    # 严重应激：优先召见
    if target.needs["stress"] > 75:
        target.adjust_relation("皇帝", {"亲近": 6, "信任": 4, "敌意": -2})
        target.needs["stress"] = max(0, target.needs["stress"] - 8)
        target.needs["lonely"] = max(0, target.needs["lonely"] - 4)
        target.hidden["security"] += 4
        return f"自动: 召见{target.name}缓解压力"

    # 争强且高目标：少量鼓励以免激进
    if target.hidden["ambition"] > 65 and target.visible["martial"] < 55 and target.needs["stress"] > 50:
        target.interests["martial"] += 2
        target.visible["courage"] += 1
        target.history.append("皇帝赐剑，化解野性。")
        return f"自动: 赐剑{target.name}"

    # 常态：大皇子偶尔夸奖以维持稳定感
    if game.rng.random() < 0.2:
        target = child_lookup["大皇子"]
        target.hidden["self_esteem"] += 3
        target.adjust_relation("皇帝", {"亲近": 2, "信任": 2})
        return f"自动: 夸奖{target.name}"

    # 随机微观策略
    if game.rng.random() < 0.15:
        target = game.rng.choice(game.children)
        target.needs["stress"] += 6
        target.adjust_relation("皇帝", {"信任": -2, "敌意": 2})
        return f"自动: 责罚{target.name}（高压）"

    return "不干预"


def resolve_route(child: Child) -> str:
    if child.visible["health"] < 45 and child.needs["stress"] > 55:
        return "病弱皇子（偏向体弱）"
    if child.hidden["ambition"] > 65 and child.visible["politics"] > 58 and child.visible["martial"] > 52:
        return "权谋武皇（军政路线）"
    if child.visible["wisdom"] > 60 and child.visible["politics"] > 35 and child.hidden["security"] > 55 and child.relationships.get("皇帝", {}).get("信任", 50) > 60:
        return "明君型太子（文治）"
    if child.visible["martial"] > 58 and child.hidden["power_desire"] > 60:
        return "武皇型继承人"
    if child.hidden["ambition"] > 60 and child.visible["politics"] > 55 and child.relationships.get("皇帝", {}).get("信任", 50) < 35:
        return "权谋型继承人"
    if child.hidden["security"] < 35 and child.relationships.get("皇帝", {}).get("信任", 50) < 35:
        return "叛逆成长线（需警惕）"
    if child.state == "normal" and child.visible["charisma"] > 62 and child.visible["kindness"] > 65:
        return "仁厚路线（亲和）"
    return "平稳成长线（普通皇子/公主）"


def print_reports(game: GameState, reports: List[Report], child: Child) -> None:
    print("  奏报")
    for rp in reports:
        print(f"   [{rp.source_symbol}] {rp.source} -> 真实度{rp.truth:>2d}: {rp.text}")
    # 给玩家做简版聚合
    if game.rng.random() < 0.25:
        print(f"   提示: 今日最值得关注的是{child.name}的安全感与压力波动。")


def day_step(game: GameState, interactive: bool) -> None:
    # 每日开始：轻微自然恢复
    for c in game.children:
        c.state = "平稳"
        c.needs["energy"] = min(100, c.needs["energy"] + 20)
        c.needs["stress"] = min(100, c.needs["stress"] + game.rng.randint(0, 3))
        c.needs["lonely"] = min(100, c.needs["lonely"] + 1)

    # 1) 孩子行动
    day_events = []
    for c in game.children:
        # 决策
        dest = c.choose_destination(game.rng, game.day, game.open_locations, game.policy)
        c.location = dest
        action = c.choose_action(game.rng, dest)

        logs, new_memories = apply_action_effects(game, c, dest, action)

        # 延迟记忆触发
        delayed = process_delayed_memories(game, c)

        events = trigger_event_text(game, c, dest, action)

        if delayed:
            logs.extend(delayed)

        c.history.extend(logs)
        c.needs["energy"] = max(0, c.needs["energy"])

        c.needs["lonely"] += game.rng.randint(0, 3)
        c.needs["stress"] = max(0, min(100, c.needs["stress" ]))

        c.memories.extend(new_memories)

        day_events.append((c, action, logs, events))

    # 2) 生成今日奏报
    print(f"\n{'=' * 40}")
    print(f"{game.today_stamp()} 宫廷更新")
    print(render_map(game))
    for c in game.children:
        # 与其本人的关系映射
        print(game.character_panel(c))

    # 只做核心的简化展示：挑一个有更多事件的孩子展示完整
    for c, action, logs, events in day_events:
        c.history.extend(events)

    for c in game.children:
        print(f"\n{c.name}今日行动：{c.location} / {c.history[-1] if c.history else '无显著事件'}")
        rpt = generate_reports(game, c, c.history[-3:])
        game.reports.extend(rpt)
        print_reports(game, rpt, c)

    # 3) 今日玩家干预
    lookup = {"大皇子": game.children[0], "二皇子": game.children[1], "三公主": game.children[2]}
    if interactive:
        note = apply_intervention_interactive(game, lookup)
    else:
        note = apply_intervention_auto(game, lookup)
    print(f"皇帝行动: {note}")

    # 行动点副作用：加严宫规会加大孩子压力/降低出宫事件
    if game.policy["strict_gate"]:
        for c in game.children:
            c.needs["stress"] += 3
            c.hidden["obedience"] += 1

    # 4) 日终收尾
    for c in game.children:
        if c.needs["stress"] > 85:
            c.mood = "焦躁"
            c.adjust_relation("皇帝", {"信任": -3, "敌意": 3})
        elif c.needs["stress"] < 35 and c.needs["lonely"] < 35:
            c.mood = "平稳"
        else:
            c.mood = "平常"

        # 关系边界衰减，避免一条线永久极端
        for rel_name in c.relationships:
            for k in ["嫉妒", "敌意"]:
                if c.relationships[rel_name].get(k, 0) > 0:
                    c.relationships[rel_name][k] -= 1

        _clamp_child(c)

    game.day += 1


def run(days: int, interactive: bool, seed: int) -> None:
    rng = random.Random(seed)
    game = GameState(day=1, days=days, rng=rng)
    game.children = build_children(rng)
    game.policy["strict_gate"] = False

    for c in game.children:
        game.emperor_perception[c.cid] = {"favor": 0, "suspicion": 0}

    print("像素宫廷沙盒（文字版）Demo")
    print("像素符号：")
    print("  E皇帝 A大皇子 B二皇子 C三公主 T太傅 W武师 M母妃 S太监 G侍卫")
    print("  Y御书房 J书院 X校场 U御花园 P母妃宫 Q皇子居所")

    for _ in range(days):
        if game.day > game.days:
            break
        day_step(game, interactive)

    print("\n" + "=" * 40)
    print("百天后（或终盘）总结")
    for c in game.children:
        r = resolve_route(c)
        print(f"{c.name}: {r}")
        print(f"  可见数据: 智{c.visible['wisdom']} 武{c.visible['martial']} 政{c.visible['politics']} 魅{c.visible['charisma']} 威{c.visible['prestige']}")
        print(f"  隐含偏向: 野心{c.hidden['ambition']} 安全{c.hidden['security']} 服从{c.hidden['obedience']} 好奇{c.hidden['curiosity']} 家需求{c.hidden['family_need']}")
        print(f"  状态: 压力{c.needs['stress']} 孤独{c.needs['lonely']} 情绪{c.mood}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=100)
    p.add_argument("--seed", type=int, default=20260616)
    p.add_argument("--interactive", action="store_true", help="每回合手动输入决策")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(args.days, args.interactive, args.seed)


if __name__ == "__main__":
    main()
