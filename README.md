# Court Sandbox Child Sim Demo

这是一个首版 Python 文字版 demo：

- 纯文字+像素字符地图
- 3 个孩子（大皇子、二皇子、三公主）
- 每日自动行动（自主决策）
- 奏报/密报系统（含源可靠度和偏差）
- 记忆系统（延迟触发）
- 每日 1 次皇帝干预
- 运行 100 天默认模拟

## 运行

```bash
cd /Users/ymatrix/court_child_sim_demo
python demo.py
```

默认是自动模式（不需每回合手动输入）。

手动模式:

```bash
python demo.py --interactive
```

可调参数:

- `--days` 天数（默认 100）
- `--seed` 随机种子
- `--interactive` 手动干预输入
- `--log` 日志文件路径（JSONL），用于保存每日日志与角色详细变化
- `--interactive` 下，默认会按系统生成的“权责令”进行 1 次选择；非交互为自动策略选取高紧迫度选项

```bash
python demo.py --days 60 --seed 7 --interactive
```

## 干预权限（试验版）

本版已实现角色权限雏形：  

- 太傅：辅导 / 训诫（有冷却）
- 武师：加训 / 体能修整（有冷却）
- 母妃：安抚 / 夜谈（有冷却）
- 太监：密查 / 警示（有冷却）
- 皇帝：召见 / 夸奖 / 责罚 / 赐书 / 赐剑 / 宫规调整（有冷却）

每日系统会基于当前状态生成 1-4 条“今日权责令”；交互模式下可输入编号选择一条执行，自动模式会按紧迫度选取。

### 日志示例

```bash
python demo.py --days 5 --seed 1 --log /tmp/court_sim.log
```

日志文件每行一个 JSON，对自动模式可直接用 `cat` 或者按行读取查看：
- `run_start`：运行开始信息
- `day_start`：每天开始的全局快照
- `day_child`：每个角色每天的行为、来源/去向、属性变化、关系变化与新记忆
- `day_reports`：每个角色当天奏报摘要
- `day_action`：皇帝当天干预（自动或手动）
- `day_end_rollup`：每天结尾汇总
- `run_end`：终局结果快照

## 像素字符约定

- E 皇帝
- A 大皇子
- B 二皇子
- C 三公主
- T 太傅
- W 武师
- M 母妃
- S 太监
- G 侍卫
- Y/J/X/U/P/Q 对应 6 个位置（御书房/书院/校场/御花园/母妃宫/皇子居所）
