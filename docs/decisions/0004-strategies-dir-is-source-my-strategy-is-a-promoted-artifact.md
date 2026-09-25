# ADR 0004 · `strategies/` 是开发源，`agent/my_strategy.py` 是提升产物

- 状态：已接受（2026-09-25）

## 背景

平台的可提交单元是**单个自包含文件** `agent/my_strategy.py`（`decision_graph.py` 里
`import my_strategy`，失败就静默退回默认排序）。但一次实验需要同时存在多份候选策略，
而 `agent/` 只有一个 `my_strategy.py` 的位置。

两个直觉方案都有问题：

- 让 `my_strategy.py` 按环境变量去 import `../strategies/xxx.py` —— 平台上 `strategies/` 不存在，
  `pack_agent.py` 只打包 `agent/`。**会在提交时静默失效。**
- 每份策略各存一个完整 `agent/` 副本 —— 重复 12 个文件，且 `protocol.py` 等会各自漂移。

## 决定

`strategies/<name>.py` 是唯一开发位置，每份都是自包含文件；
`python scripts/ao.py select <name>`（或 `run --strategy <name>`）**整文件复制**到
`agent/my_strategy.py`。每次 `ao.py run` 把当时的策略名与文件 SHA-256 写进
`runs/<id>/meta.json`，所以一个 run 目录永远能追溯到产生它的策略版本。

约定：`strategies/*.py` 第一行 `__strategy__ = "<name>"` 是名字的来源。

## 后果

- 「本地开发路径」与「提交产物」**完全同一**：跑通的那份文件就是要上传的那份，零转换步骤。
- 代价：`sweep` 是顺序的（提升会覆盖活动策略），不能并行跑多策略。接受 —— 本机一次
  dev-reference 要 ~10 分钟，CPU 也不是瓶颈在并行上。
- 代价：`git status` 会显示 `agent/my_strategy.py` 被改。这是**预期的**，它是产物不是源。
  策略演进的历史记在 `strategies/` 与 [submissions/LEDGER.md](../../submissions/LEDGER.md)。
- 若将来出现跨策略共享的工具函数，必须复制进每份文件（不能提到 `agent/` 共享模块里），
  除非同时改 `pack_agent.py` 的打包范围 —— 那属于改官方工具，禁止。
