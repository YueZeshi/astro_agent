# 实验协议 · Experiment protocol

怎么跑、怎么算分、怎么判断「这次改动真的更好」。

## 环境

Python ≥ 3.9（本机 3.11.1 已验证）。官方工具链只用标准库；只有走 LLM 才需要
`agent/requirements.txt`。**不要改 `harness/`**（它应当与官方 zip 逐字节一致，
`diff -rq` 可自证）。

```
python scripts/ao.py run --scenario dev-reference      # 跑 + 打分 + 记 meta.json
python scripts/ao.py results                           # 所有已记录运行，按总分排序
```

## 命令面

`scripts/ao.py` 是对 `harness/` 的薄封装，只加了：路径解析、按场景读
`scenario_manifest.json` 决定墙钟、`runs/` 命名、`meta.json` 记录、策略提升。

| 命令 | 作用 |
|---|---|
| `run [--scenario S] [--strategy NAME] [--wallclock N] [--tag T] [--out DIR] [--quiet]` | 跑一次并打分；`--strategy` 会先提升为活动策略 |
| `select NAME` | 把 `strategies/NAME.py` 复制进 `agent/my_strategy.py` |
| `new NAME [--from-strategy S] [--promote]` | 从模板或已有策略开新策略 |
| `score --run DIR` / `--decisions F --scenario S [--out J]` | 用官方评分器**独立复算** |
| `sweep --strategies a,b --scenarios S1,S2 [--repeats N]` | 批量对比，打表 + 写 `runs/sweep-latest.json` |
| `results` | 汇总表 |
| `pack [--out F] [--no-env]` | 打包 `agent/` 为提交用 zip |

等价的官方命令（绕过封装，排查环境问题用）：

```
python harness/local_runner.py  --scenario harness/scenarios/dev-reference \
        --agent agent/minimal_agent.py --wallclock 600 --out runs/manual
python harness/score_decisions.py --scenario harness/scenarios/dev-reference \
        --decisions runs/manual/decisions.csv
```

`local_runner.py` 退出码：`survey_complete` / `global_wallclock_expired` → 0；
`agent_error` / `agent_initialization_error` → **2**。其他旗标：`--python`（换解释器，跑非 Python
实现）、`--init-timeout`、`--inherit-env`、`--show-agent-stderr`、`--no-replay`、`--quiet`。

## 产物

```
runs/<UTC时间戳>-<场景>-<策略>[-tag]/
├── decisions.csv          # 提交物：decision_id,slot_id,action,tile_id,program,request_id,reason
├── score_report.json      # 分项得分 + 逐文件 input_sha256
├── workflow_result.json   # 仿真终态
├── agent.log              # 智能体 stderr —— 出先看这里
├── decision_replay.html   # 回放（体积大，不进 git）
├── meta.json              # 本次运行的场景/策略/SHA/摘要（本项目加的）
└── scratch/
```

`runs/` 整体 gitignore。**值得留的结果**复制进 `submissions/` 并在
[LEDGER.md](../submissions/LEDGER.md) 记一行。

## 计时基准（本机实测）

| 场景 | 时隙 | 真实耗时 | total | 说明 |
|---|---|---|---|---|
| demo-week | 294 | `runner_seconds` **20.05**（仿真 `wall_seconds` 16.73） | **5,909.10** | 52 块完成、1 请求、`survey_complete`；penalties 仅 flexible_shortfall 500 |
| dev-reference | 7928 | **≈ 9 min 47 s**（由产物时间戳 13:01:34→13:11:21 得出） | **12,287.48** | 64/64 块、17 完成 + 1 豁免请求、0 罚分、`survey_complete` |

dev-reference 一次跑用掉 **536.86 s** 的仿真墙钟预算（`accounted_wallclock_seconds`，上限 7200）、
提交 7943 个动作。注意区分：`accounted_wallclock_seconds` 是**策略预算**（规则里的硬约束），
`runner_seconds` 是**本机 CPU 时间**（无关规则，只影响你迭代节奏）。

**一次改动一次全量 dev-reference ≈ 10 分钟 —— 这是真实预算。** 因此：

1. 迭代在 **demo-week**（20 s）上做，行为对了再上 dev-reference。
2. `--wallclock` 限制的是**仿真可用时间**，不是真实 CPU；不要盲目放大。
3. 平台每天 10 次提交额度 ≠ 本地跑的次数；本地随便跑，提交要挑。

greedy 在 7200 s 预算下复算出的 **12,287.478365** 与官方 `/brief` 公布的 reference 分数
12,287.48 逐位一致 —— 说明本机的 `harness/`、场景数据与评分链路都是干净的。
**这个数就是 P0 锚点**，之后每一次改动都跟它比。


## 提交到平台

```bash
export SAC_EMAIL='you@example.org' SAC_PASSWORD='...'     # 只放环境，别放文件
python scripts/ao.py submit --kind results --file runs/<id>/decisions.csv --wait
# --scenario 省略时从该 run 的 meta.json 推断；平台要求与本地运行选同一个场景
```

底层是 `harness/sac_submit.py`。`SAC_URL` / `SAC_KEY` **不用设** —— 官方脚本里已经写死了
默认值（`sac_submit.py:74-77`，就是 SKILL.md 那段 env 的内容）。只有 `SAC_EMAIL` /
`SAC_PASSWORD` 是必须的，且只有这两个是凭据。

> **凭据绝不能写进 `agent/.env`。** `pack_agent.py:80` 默认**把 `agent/.env` 打进提交 zip**
> （那是给模型 key 用的，平台只让你的 agent 进程读到）。账号密码放那里等于直接寄给主办方。
> 放 shell 环境变量，或 `agent/.env.sac` —— 后者被 `pack_agent.py:82` 排除在包外。

限制：`decisions.csv` ≤ 20 MB；`dev-reference` 上限 10 次/天；`--kind agent` 走
`python scripts/ao.py pack` 产出的 zip（≤ 20 MB，模型 ≤ 128K 上下文，每轮决策 ≤ 3 次调用）。

**本机已验证到的位置**（2026-09-25）：封装层正确把请求交到 `sac_submit.py`，停在
`--email (or SAC_EMAIL) is required` —— 没有提交任何东西。但同一时间
`vdiemcofukuxglqsmlyz.supabase.co` 从本机**不可达**（`curl` 返回 000，Python 报
`WinError 10054` 连接被强制重置），而 `create.gosim.org` 正常 200。
所以 `fetch_scenario.py` 与 `sac_submit.py` 都需要一条能到 Supabase 主机的网络出口；
命令行不通就退回网页上传 https://create.gosim.org/survey26/platform/compete ，
上传同一个 `runs/<id>/decisions.csv`（先 `ao.py score --run runs/<id>` 复算过再传）。


官方保证：同场景 + 同 `decisions.csv` ⇒ 本地与平台 `score_report.json` **完全一致**，
`make_scenario.py` 生成的场景跨 OS 字节一致。所以我们任何「更好」的结论都必须可复算：

- `meta.json` 里存了策略文件的 SHA-256 和完整 runner 命令行 —— 复现一条记录只需要这两样。
- 复算：`python scripts/ao.py score --run runs/<id>`。它应当给出与 `score_report.json` 一致的分数；
  不一致说明你动了 `harness/`（不该）或 runner 报了 replay 与 live 不符的警告。

## 判断「更好」的规则

单次 dev-reference 分数变化 **不构成证据**。它是单一固定 seed（20260909）的单一实现。
门槛：

1. demo-week 不 regress；
2. dev-reference 提升，且**分项方向可解释**（`base_science` 涨是因为质量挑得好，不是运气）；
3. 至少 2 个 `make_scenario.py` 自造场景（不同 seed、≥ 90 夜）同向；
4. `--wallclock` 扫 900 → 7200 不崩（隐藏场景可能只有 900 s）；
5. `agent.log` 里零 fallback（`could not be imported` / `raised` / `not legal now`）。

第 3、4 条是评测口径（隐藏场景泛化）直接要求的，见
[ADR 0002](decisions/0002-target-the-v3-rules-not-just-dev-reference.md)。

## 离线分析（合法的那半边）

练习场景的 `weather.csv` 真值是公开的（`participant_visible`），**可以在策略之外**用它做：

- **全知上界**：对每块天区枚举其合法时隙的真值 `A_used`，算 `Σ V_tile × max(A) × (1+bonus)`，
  与基线比 → 直接回答 [strategy-design.md](strategy-design.md) 的 A1「余量到底有多大」。
- **预报校准**：`weekly` 各 `revision` vs 事后真值 → 12% 漏检、6 假阳性到底是怎样分布的，
  给 A2 提供判据阈值。

写进 `analysis/`，读 `harness/scenarios/**` 只发生在这一层。**策略（`agent/`）永远不许读。**

## 榜单现状（2026-09-25）

`/brief` 上 `dev-reference` 与 `finals-preview` 两行榜单：reference agent 分数分别为
**12,287.48** 和 **8,214.26**，「暂无参与队伍」，最高人类分数**为空**（还没有人提交过）。
`/leaderboard` 页面本身显示「尚未配置任何阶段」。

也就是说：**目前唯一的对手就是 reference 基线本身，而且练习榜上没有任何可参照的人类成绩。**
不要试图去追一个不存在的榜 —— 真正的对手是隐藏场景。官方文档给出的唯一量化提升是
1600 天区规模下覆盖打法 **+2.00%**。**小场景打不开差距，规模才打开**，
这进一步支持「不要对着 dev-reference 调参」。
