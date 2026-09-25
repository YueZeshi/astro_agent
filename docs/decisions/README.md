# 决策记录 · Architecture decisions

| # | 标题 | 状态 |
|---|---|---|
| 0001 | [用 ADR 记录结构与合约决定](0001-record-architecture-decisions.md) | 已接受 |
| 0002 | [面向 v3 正式规则设计，而不是只面向 dev-reference](0002-target-the-v3-rules-not-just-dev-reference.md) | 已接受 |
| 0003 | [原样 vendor 官方入门包到 `harness/`，只读](0003-vendor-the-starter-kit-unmodified-in-harness.md) | 已接受 |
| 0004 | [`strategies/` 是开发源，`agent/my_strategy.py` 是提升产物](0004-strategies-dir-is-source-my-strategy-is-a-promoted-artifact.md) | 已接受 |

格式：状态 / 背景 / 决定 / 后果，每篇 ≤ 30 行。教程与事实归 `docs/*.md`，这里只记**为什么这么选**
以及**代价**。被取代的决定改状态为「已取代 by 000N」，不删文件。
