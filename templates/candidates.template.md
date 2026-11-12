# 候选选题池

> `/cheatx-trends` 写入，`/cheatx-recommend` 读取排序。也可以手动编辑——贴一行 H3 标题就行。
> Schema 见 cheat-on-x 的 `shared-references/candidate-schema.md`。

---

## 使用说明

每个候选是一个 H3（`### [tier] 标题`），下面带字段。最简只要标题一行，`/cheatx-recommend` 会自动粗打分补全。

字段速查：
- **id**：12 位 hash，去重用。手加留空
- **source**：`<类型>:<来源>`，如 `idea:self`、`trend:x-trends`、`paste:manual`
- **form_hint**：建议形态 single / thread / long / article / quote / reply
- **quote_target**：quote / reply 候选要引用或回复的帖子链接
- **expires_at**：热点的过期时间，过期不推荐
- **tier**：tier1 / tier2 / tier3 / skip / risky / done
- **composite (vN)**：粗打分，**不是预测**
- **category**：话题类别（推荐时避免连发同类）

最简手加格式：

```markdown
### 我用 AI 写作半年后删掉的提示词
- form_hint: thread
```

---

## 候选项

（删掉这行，从你的真实候选开始）
