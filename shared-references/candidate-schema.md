# Candidate Schema（候选项统一 schema）

被这些子 skill 引用：`cheatx-trends`、`cheatx-recommend`、`cheatx-seed`、`cheatx-init`、所有 `adapters/trend-sources/`、`x-csv-import trends`。

任何"待决定要不要发"的素材——手粘的列表、X 趋势、油猴导出的 Explore 页、aihot、你自己的收藏夹——都先 normalize 成本 schema 才进候选池。这是 adapter 的输出契约。

---

## 必填字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string（12） | 稳定 hash，算法见下 |
| `title` | string | 人类可读标题（一句话选题） |
| `source` | string | `<类型>:<来源名>`，如 `trend:x-trends`、`trend:aihot`、`pool:markdown-list`、`paste:manual`、`idea:self` |
| `snapshot_text` | string | 素材全文或摘要——**这是打分的输入**，不能只有 url |
| `snapshot_at` | ISO 8601 | 抓取 / 录入时间 |

## 可选字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `url` | string | 原链接 |
| `form_hint` | enum | 建议形态：`single` / `thread` / `long` / `article` / `quote` / `reply` |
| `quote_target` | string | `quote` / `reply` 候选：要引用或回复的那条帖子链接 |
| `expires_at` | ISO 8601 | 时效素材的过期时间（热点一般 ≤ 24h）。过期后不进推荐 |
| `tier` | enum | `tier1` / `tier2` / `tier3` / `skip` / `risky` / `done` |
| `read_status` | enum | `unread` / `skimmed` / `deep_read` / `done` |
| `category` | string | 自定义话题标签（如"AI 工具"、"独立开发"）——推荐时用来避免连发同类 |
| `composite_score` | float | 当前 rubric 下的粗打分 |
| `dimension_scores` | object | `{"HK":4,"RP":3,"SV":5,"RS":3,"DW":3,"FT":4,"NF":5,"NR":0}` |
| `scored_under_rubric_version` | string | |
| `predicted_bucket` | string | 粗预测（倍数桶名）。**不是正式预测**——选题阶段的粗估，和 `predictions/*.md` 完全独立 |
| `predicted_reason` | string | 一句话 |
| `note` | string | 备注 |
| `rejected_at` / `rejected_reason` | ISO / string | 用户主动跳过时记录 |

---

## JSON 范例

```json
{
  "id": "a3f2c1d4e5b6",
  "title": "我用 AI 写作半年后删掉的 7 个提示词",
  "source": "idea:self",
  "snapshot_text": "用户口述：半年里试过很多提示词，最后只留下 3 个……",
  "snapshot_at": "2026-11-12T09:30:00+08:00",
  "form_hint": "thread",
  "category": "AI 工具",
  "composite_score": 7.6,
  "dimension_scores": {"HK":4,"RP":3,"SV":5,"RS":3,"DW":4,"FT":4,"NF":5,"NR":1},
  "scored_under_rubric_version": "v0",
  "predicted_bucket": "命中",
  "predicted_reason": "SV 主导的清单 thread，核心话题"
}
```

```json
{
  "id": "8c4d92e1f0b3",
  "title": "（X 趋势）某开源模型发布",
  "source": "trend:x-trends",
  "snapshot_text": "趋势名 + 帖子量 + 领域标签 + 抓取时 top 帖子摘要（如有）",
  "snapshot_at": "2026-11-12T10:15:00+08:00",
  "url": "https://x.com/search?q=...",
  "form_hint": "quote",
  "expires_at": "2026-11-13T10:15:00+08:00",
  "composite_score": null,
  "dimension_scores": null
}
```

抓回来时打分字段为 null 是正常的——`cheatx-trends` 会对新候选做粗打分。

---

## Markdown 表示（`candidates.md`）

```markdown
### [tier1] 我用 AI 写作半年后删掉的 7 个提示词
- **id**: a3f2c1d4e5b6
- **source**: idea:self · **snapshot_at**: 2026-11-12
- **form_hint**: thread · **category**: AI 工具
- **composite (v0)**: 7.6 — HK4 RP3 SV5 RS3 DW4 FT4 NF5 NR1
- **predicted bucket**: 命中
- **expires_at**: —
- **note**:

> [snapshot_text]
```

---

## ID 稳定性

同一条素材被不同来源抓到 → 同一个 id：

```python
import hashlib
def candidate_id(source: str, title: str, url: str | None = None) -> str:
    normalized_title = title.strip().lower().replace(" ", "")
    url_path = url.split("?")[0].rstrip("/") if url else ""
    raw = f"{source.split(':')[0]}|{normalized_title}|{url_path}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
```

- `source` 只取冒号前的类型
- 标题 lowercase + 去空格
- url 去 query string

## 去重

写入 `candidates.md` 前：
1. 算 id
2. `candidates.md` 已有 → 跳过
3. `predictions/*.md` 的 header 里有同一来源 id（已发过）→ 跳过
4. `.cheatx-cache/trends-history.jsonl` 里有且 `rejected_at` 非空、距今 < 30 天 → 跳过
5. `expires_at` 已过 → 跳过
6. 通过则写入

`.cheatx-cache/trends-history.jsonl` append-only，每行一条。

---

## tier 语义

| Tier | 含义 |
|---|---|
| `tier1` | 强候选，进推荐池 |
| `tier2` | 备选，权重低 |
| `tier3` | 弱，留作长尾 |
| `skip` | 用户跳过，30 天内不再出现 |
| `risky` | 敏感 / 平台风险，推荐时额外标注 |
| `done` | 已发，由预测文件接管 |

未打分的候选**不出现在** `cheatx-recommend` 输出里。

## adapter 契约

1. 输出符合本 schema 的 items
2. 自己负责把 url / 趋势名扩展成可读的 `snapshot_text`
3. 配置缺失（无 token / 无导出文件）→ 返回空列表 + 写明原因，**不抛异常**
