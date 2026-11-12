# 评分规则（rubric_notes.md）

> 本文件是 `cheatx-score-blind` 打分 sub-agent **唯一**能读的规则文件。
> **只写通用语言**：公式、维度定义、bucket 规则、抽象后的规律。
> **绝不写**：具体帖子名、链接、status id、复盘数字、回复原文——那些写 `rubric-memo.md`。
> 每次改完本文件跑 `python <cheat-on-x>/tools/leak_check.py rubric_notes.md`，非 0 退出就回滚。

---

## 版本

**当前版本**: `v0`

| 版本 | 生效日期 | 变更类型 | 驱动样本数 |
|---|---|---|---|
| v0 | [INIT-DATE] | 初版占位（cold-start，等权） | 0 |

升级规则见 cheat-on-x 的 `shared-references/bump-validation-protocol.md`：
- 任何系数 / 维度变化 → 走完整 bump
- 维度定义的边际细化 → 不 bump，在下面对应维度后标注

---

## 当前规则

<!-- cheatx-init 在这里粘贴 starter-rubrics/<x-post-zero|x-longform-zero>.md 的全文；之后由 cheatx-bump 维护 -->

[STARTER-RUBRIC]

---

## 规律沉淀区（打分前必看）

> 只放通过 bump 流程确认、并且**已经抽象化**的规律。格式：`规律 N：<一句话>（适用形态）`。
> 不写样本名、不写数字。

（暂无）

---

## 对标账号派生的方向信号

> 由 `/cheatx-learn-from` 填入：对标账号的高 / 中 / 低样本里**哪些维度看起来重要**。
> 只写定性方向（"高表现样本 SV 普遍 ≥4"），不写对标帖子原文、不写对方数字。
> 不直接改权重——等你自己有 ≥5 条校准样本、正式 bump 时再决定。

（待 cheatx-learn-from 填入）
