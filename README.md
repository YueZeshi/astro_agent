# astro_agent

GOSIM 2026 「巡天智能体 · Agentic Observer」参赛仓库。
深圳南山 · 2026-11-12 培训与比赛 · 11-13 12:00 报名截止 · 11-14 评审 · 11-15 颁奖。

**赛题**：给一座望远镜写一个观测调度智能体。它每 15 分钟（一个 900 s 时隙）决定下一个时隙
拍哪片天区、还是等。它看得见公开的天空状态（天区目录、可见窗口、几何、天况快照、7 天预报、
观测请求），**但看不见真实天气**，也看不见仪器效率和隐藏的科学标签。每个选择都是对未来的下注。

评分不看单场最高分，看**泛化**：公开场景 `dev-reference` + 未公开的隐藏场景 + 代码质量与文档。

## 30 秒上手

```bash
python scripts/ao.py run --scenario demo-week          # ~20 s，快速回归门
python scripts/ao.py run --scenario dev-reference      # ~10 min，P0 锚点场景
python scripts/ao.py results                           # 所有已记录运行，按分数排序
```

只改一个文件就能提分：`strategies/<你的策略>.py` 里的 `choose_action(candidates, snapshot, memory)`。

```bash
python scripts/ao.py new my-v1 --from-strategy greedy --promote   # 开一版新策略
python scripts/ao.py select my-v1 && python scripts/ao.py run --scenario dev-reference
```

## 当前状态（2026-09-25 建立）

| 项 | 值 |
|---|---|
| P0 锚点 `greedy` @ dev-reference（墙钟 7200 s） | **12,287.478365** — 与官方公布的 reference 分数逐位一致 |
| P0 锚点 `greedy` @ demo-week（墙钟 900 s） | **5,909.099093** |
| 基线画像 | 64/64 天区完成、17 请求完成 + 1 豁免、**0 罚分**、覆盖均匀度 1.00 |
| 已识别的最大余量 | `base_science`（占总分 58.4%）+ 档位上限 **+4.9%**，见 [strategy-design](docs/strategy-design.md#1-先定位余量在哪) |
| 官方 `reference` 示范 | demo-week 上与 P0 **逐位相同**（5,909.099093）—— 练习场景不是拉开差距的地方 |
| 平台提交 | 尚无（榜单目前只有 reference 基线，无人类提交） |

**最重要的一条实测**：`choose_action` 在 dev-reference 全场只被问 **91 次**（7,943 个时隙里其余
7,852 个由 `_finalize` 直接返回 wait，不问策略）。所以这不是「每 15 分钟做一个选择」的问题，
而是 **「把 ~90 个可行动名额分给谁」** 的问题 —— 而且等待**不产生任何费用**
（`wait_seconds.explicit == unavailable`，`avoidable_wait` 从未计费）。
据此已否证两个直觉方向（「优先补分区配额」= `quota-floor`，mine-s7 −1.77 / demo-week +24.64，
块数与罚分不变；「天况不好就等」= 官方实测 −1,700），详见
[strategy-design.md](docs/strategy-design.md) 与 [LEDGER.md](submissions/LEDGER.md)。

## 仓库结构

```
├── agent/          要提交的单元 —— 官方 agent 包的工作副本
│   └── my_strategy.py   ← 提升产物（strategies/ 的当前选中版本），唯一被反复覆盖的文件
├── strategies/     开发中的策略版本，每份自包含；第一行 __strategy__ = "<name>"
├── harness/        官方入门包的逐字节只读副本（评分器 + 工作流 + 3 个公开场景数据）
├── scripts/ao.py   run / score / select / new / sweep / results / pack
├── runs/           每次运行的产物（gitignore）；meta.json 记录场景、策略名与 SHA
├── submissions/    值得保留的 decisions.csv + LEDGER.md 台账
├── analysis/       离线分析（全知上界、预报校准）—— 唯一允许读场景真值的层
└── docs/           见下
```

三层严格分离：**官方评分器只读、策略代码自包含、离线分析与在线决策不同层**。
理由记在 [ADR 0003](docs/decisions/0003-vendor-the-starter-kit-unmodified-in-harness.md) 与
[ADR 0004](docs/decisions/0004-strategies-dir-is-source-my-strategy-is-a-promoted-artifact.md)。

## 文档地图

| 文件 | 回答什么 |
|---|---|
| [docs/competition.md](docs/competition.md) | 赛题、赛程、奖项、提交规则、红线、天文背景 |
| [docs/scoring.md](docs/scoring.md) | 评分公式与**全部常数**、什么算「完成曝光」、两代规则差异 |
| [docs/data-dictionary.md](docs/data-dictionary.md) | 场景目录、每个 CSV 的列与行数、运行时可见 vs 不可见 |
| [docs/agent-protocol.md](docs/agent-protocol.md) | JSON-Lines 合约、快照字段、候选字段、`choose_action` 契约 |
| [docs/strategy-design.md](docs/strategy-design.md) | 余量在哪、为什么「等天况」会掉分、待验证假设清单 |
| [docs/experiment-protocol.md](docs/experiment-protocol.md) | 怎么跑、怎么算「更好」、计时基准、复现要求 |
| [docs/decisions/](docs/decisions/) | ADR：结构与合约决定 |
| [submissions/LEDGER.md](submissions/LEDGER.md) | 提交台账 |

## 红线（先读这段再写代码）

1. 不读 `harness/scenarios/**` 来反推真值天气 —— 运行时沙箱里也拿不到，只在 `analysis/` 里离线用。
2. 不 import `agent/` 之外的东西。平台上 `challenge/` 包**不存在**。
3. 不直接调评分器探测分数。
4. stdout 只走协议行，日志写 stderr（进 `runs/<id>/agent.log`）。
5. 不构造当前候选集里不存在的 `(tile_id, program, request_id)`。
6. `agent/.env` 里的模型密钥**绝不入库**（已在 `.gitignore`）。
7. 评分常数从 `initialize.scoring_contract.score_config` 读，不硬编码 —— 隐藏场景会改。

## 官方入口

平台 https://create.gosim.org/survey26/platform/ ·
[规则](https://create.gosim.org/survey26/platform/rules) ·
[文档](https://create.gosim.org/survey26/platform/docs) ·
[资源](https://create.gosim.org/survey26/platform/resources) ·
[提交](https://create.gosim.org/survey26/platform/compete) ·
[赛题仓库](https://github.com/gosimfoundation/hackathon-survey26/tree/main/challenge/participant_agent) ·
入门包 `/downloads/agent-observer-starter-kit.zip` · hackathon@gosim.org
