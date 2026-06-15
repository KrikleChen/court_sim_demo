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

```bash
python demo.py --days 60 --seed 7 --interactive
```

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
