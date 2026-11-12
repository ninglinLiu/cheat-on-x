# Adapter: x-csv-import（CSV 导入器）

`cheatx-retro` / `cheatx-publish` / `cheatx-init` / `cheatx-learn-from` / `cheatx-trends` 在 `data_collection = csv`（默认）时调用。只用 Python 标准库（3.9+），不需要装任何依赖。

## 吃哪些文件

| 来源 | 怎么拿 | 备注 |
|---|---|---|
| [cheatx 油猴脚本](../../../userscripts/README.md) | 浏览 x.com 时点导出 | 默认路线。列名就是本工具的标准列，零配置 |
| X Analytics 导出 | Premium 账号在 Analytics 页导出内容 CSV | 列名靠 `aliases.py` 识别；第一次用先 `inspect` 看映射 |
| 其他油猴脚本 / 浏览器插件 | 各自的导出 | `inspect` 看哪些列没认出来，用 `--map` 补 |

识别规则：列名做归一化（小写、去空格下划线）后查 [`aliases.py`](aliases.py)。中英文列名都有。数字支持 `1,234` / `1.2K` / `3.4M` / `1.2万` / `2.5w`。

## 子命令

```bash
IMP=<cheat-on-x>/adapters/perf-data/x-csv-import/import_csv.py

# 看一个文件怎么映射（不打印任何指标数值）
python $IMP inspect imports/foo.csv

# 只取一条帖子发出的正文（发布登记时做文本一致性检查；不输出指标）
python $IMP text imports/foo.csv --id https://x.com/me/status/1988765432109876543

# 单条复盘：写 posts/<id>/report.md，stdout 输出该条的指标 JSON
python $IMP post imports/foo.csv --id 1988765432109876543 --out posts/2026-11-12_xxx_短名/ \
    --published-at 2026-11-12T21:03+08:00 --final posts/2026-11-12_xxx_短名/final.md --window-hours 48

# 批量复盘：读 .cheatx-state.json 的 pending_retros，只处理已到期的
python $IMP due imports/a.csv imports/b.csv --project .

# 账号历史 / 对标导入：按形态的曝光中位数 + 每条的档位（≥2× 中位数为高，≤0.5× 为低）
python $IMP history imports/foo.csv --handle @me --project .            # 自己的历史（跳过待复盘的帖子）
python $IMP history imports/bench.csv --handle @someone --samples-dir samples/someone

# 趋势导出 → 候选 JSON lines
python $IMP trends imports/cheatx-trends-xxx.csv
```

全局选项放在子命令**前面**：

```bash
python $IMP --map "Views=impressions,Tweet ID=post_id" post ...
python $IMP --tz +08:00 history ...      # 导出里的时间没带时区时按这个解释（默认本机时区）
```

多个文件可以一起传：同一条帖子按 `captured_at` 合并——新快照的非空值覆盖旧值，旧快照里独有的字段（如分析页读到的主页访问）保留。

## 保盲设计

- `due` 只处理 `due_at` 已过的帖子；文件里其他帖子的数字不会出现在输出里
- `history --project .` 跳过仍在 `pending_retros` 里的帖子
- `text` / `inspect` 不输出任何指标
- `report.md` 不写回复者 handle、不写导出文件的绝对路径

## report.md 格式

帖子信息（status id / 链接 / 形态 / 发布时间 / 快照时间与距发布小时数 / 数据来源）→ 数据快照表（只列数据源真有的指标）→ 派生比率（互动率、收藏/赞比、回复率、转引率、主页访问率、每千曝光新增关注）→ 发出的正文 → 按赞排序的回复 top 20 → 引用 top 10 → 预测时的定稿。

快照早于复盘窗口时标 `early_snapshot`。

## 退出码

`0` 成功 · `2` 输入有误或没找到帖子 · `3` 文件问题

## 测试

```bash
cd adapters/perf-data/x-csv-import
python -m unittest test_xcsv.py
```

## 已知局限

- X Analytics 导出的确切列名会随版本变化；`aliases.py` 里的英文列名来自常见导出格式，**没有用 2026 年的真实导出文件验证过**。对不上就 `inspect` + `--map`，再把新列名补进 `aliases.py`
- `derive_form` 靠回复 / 引用关系推断形态；预测文件 header 里的 `Form` 优先
