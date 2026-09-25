# ADR 0003 · 原样 vendor 官方入门包到 `harness/`，只读

- 状态：已接受（2026-09-25）

## 背景

评分器、工作流、日历与几何求解、场景数据（含 SHA-256 manifest）都来自官方 zip。
分数只在「同一份评分器 + 同一份场景」下才与平台可比。一旦被就地修改，本地分数就会静默地
不再等于平台分数 —— 这是最难发现、代价最高的一类错误。

## 决定

`harness/` = 官方 zip 的**逐字节完整副本**（含它自带的 `harness/agent/` 模板），永不编辑。
我们的代码只在 `agent/`（可提交单元）与 `strategies/`（开发中的策略版本）。

已验证（2026-09-25）：`diff -rq .ref/agent-observer-starter-kit harness` **无输出**，两侧各 114 个文件。

> 复验时不要给 `diff` 加 `grep -v "Only in"` —— `diff -rq` 正是用「Only in A: file」报告
> B 里缺失的文件，过滤掉就等于把漏拷的文件藏起来。第一次建 `harness/` 时就是这样漏了
> `run_*.command` 等文件，实际是 100% 完整后才通过的比对。

## 后果

- 仓库里同一份官方文件存在两份（`harness/agent/` 模板 + 根 `agent/` 工作副本）。这是故意的：
  根 `agent/` 被反复覆盖，出问题时随时能 diff 回官方原样。
- `harness/` = 114 个文件、4.3 MB（含 3 个场景的参考数据）。换来离线可复现、评委可复算。
- 上游更新时：重新解压覆盖 `harness/`，再检查 `agent/` 是否需要同步合约变更。
  下载入口见 [competition.md](../competition.md#官方入口)。
- 例外：`make_scenario.py` 生成的自造场景也落在 `harness/scenarios/`（工具写死的相对布局），
  但它们不属于 zip，且能用 seed 一命令逐字节重建，所以 `.gitignore` 里用
  `harness/scenarios/mine-*/` 排除，不入库。
- **注意**：`harness/SKILL.md`、`fetch_scenario.py`、`sac_submit.py` 里含有主办方**公开发布**的
  Supabase anon key（`eyJhbGciOiJIUzI1NiIs…`，同一个值也出现在平台前端 bundle 里）。
  那不是密钥、不是我们的模型凭据，且逐字节只读要求我们不改它。安全扫描若报出来，
  出处是官方文件，不要「顺手删掉」—— 删了就破坏 ADR 0003 的可复算性。
  真正绝不能入库的是 `agent/.env`（我们自己的模型 key），已在 `.gitignore`。
