# dotabyss-translation（社区维护版）

《ドットアビスX》AbyssMod 简体中文（`zh_Hans`）翻译资源仓库。

本仓库不包含任何游戏本体文件，只包含 AbyssMod 插件按约定格式读取的**文本/图片替换资源**与**清单（manifest）**。
原框架与原始汉化由 [anosu/AbyssMod](https://github.com/anosu/AbyssMod) / `anosu/dotabyss-translation` 提供；
原仓库不可用后，本仓库按同样的目录结构与哈希算法重建，用于让插件改连一个新的 CDN 继续工作。

---

## 1. 插件是怎么读这个仓库的

`BepInEx/config/AbyssMod.cfg`：

```ini
[Translation]
CDN = https://raw.githubusercontent.com/<owner>/<repo>/refs/heads/main/translations
Language = zh_Hans
```

启动时插件按这个顺序工作：

1. `GET {CDN}/manifest/zh_Hans.json` —— 主清单，里面记录每个文件的 MD5；
2. 用清单里的 `hash` 字段校验清单自身；
3. 按需下载/读取 `novels/<剧情ID>/zh_Hans.json`、`names/`、`static/`、`ui_texts/`、`replacements/`；
4. 每个文件下载后都会和清单里的 MD5 对比，**不一致就判定损坏并重新下载**。

所以：**文本可以随便改，manifest 必须跟着重算**。manifest 不对的典型现象是每次进游戏都在重复下载、
日志里反复出现 `Remote hash mismatch` / `Cache hash mismatch`，或者干脆回退成日文。

> 结论：不要手改 `translations/manifest/zh_Hans.json`，用 `tools/build_manifest.py` 生成。

---

## 2. 目录结构

```
translations/
  manifest/zh_Hans.json          主清单（唯一需要工具生成的文件）
  names/zh_Hans.json             人名
  static/zh_Hans.json            技能、道具、任务等 MasterData 静态文本
  ui_texts/zh_Hans.json          UI 文本（按控件路径索引）
  novels/<剧情ID>/zh_Hans.json   剧情：{"日文原文": "中文译文"}
  replacements/                  UI 图片替换
    manifest.json                图片替换清单（version=1，插件读取）
    *.png                        替换图（当前 8 张按钮图）
tools/
  build_manifest.py              算 manifest / 校验（本仓库的核心工具）
  rebuild_from_dump.py           游戏更新后从 TextAsset dump 增量补新文本
  dump_context.py                按剧本顺序导出上下文（翻译用）
  apply_batch.py                 把整段译文按顺序回填
.github/workflows/
  manifest.yml                   push 后自动重算并提交 manifest
  verify.yml                     PR 检查 manifest 与哈希
```

剧情 JSON 的键是**游戏里实际显示的整段文本**（含 `<br>`、`<user>`、`<ruby=...>`），
不是台词编号；插件就是拿显示文本直接查表。所以键里**不能**带 `,,vc_xxx`、`,106501000G,mcv_...`、
`,chara_3` 这类语音/角色元数据，否则永远匹配不上（旧版草稿最大的坑）。

---

## 3. 发布 / 换 CDN（复活流程）

1. 新建仓库，把本目录全部内容推到 `main`；
2. 改 `BepInEx/config/AbyssMod.cfg` 的 `CDN`：

```ini
CDN = https://raw.githubusercontent.com/<你的用户名>/<仓库名>/refs/heads/main/translations
```

3. 删除 `BepInEx/plugins/AbyssMod/cache` 后启动，让插件重新拉取（或只删 `cache/translations`）。

国内访问 `raw.githubusercontent.com` 不稳定时，可换 jsDelivr（同一份文件，无需改仓库）：

```ini
CDN = https://cdn.jsdelivr.net/gh/<你的用户名>/<仓库名>@main/translations
```

jsDelivr 有缓存，更新后用 `https://purge.jsdelivr.net/gh/<owner>/<repo>@main/translations/manifest/zh_Hans.json`
刷新一下清单即可。

### 我不在了，别人怎么接手

任何人 fork 本仓库后，只需要改 `AbyssMod.cfg` 里的 `CDN` 一行指向自己的 fork；
若要发布给其他人用，也可以在自己的 README 里写清新的 CDN。仓库内所有路径都是相对的，
不依赖任何个人域名或账号，搬迁成本就是「fork + 改一行配置」。

---

## 4. 日常维护（改译文）

```bash
# 1. 直接编辑 translations/novels/<id>/zh_Hans.json
# 2. 本地重算并校验
python tools/build_manifest.py --root .
python tools/build_manifest.py --root . --verify

# 3. 提交；CI 也会再算一遍，manifest 没更新会被自动补提交
git add -A && git commit -m "fix(novel): ..." && git push
```

只改译文、不改键时，也可以只跑 `--check` 看差异：

```bash
python tools/build_manifest.py --root . --check
# manifest is stale:
#   ~3 novel hashes changed (e.g. ['hmr_...', ...])
```

`--strict` 会把以下问题当错误（默认只是 warning）：空译文、键名残留元数据、
`<br>` / `<user>` 数量不一致、译文残留假名（`<ruby>` 注音除外）。

---

## 5. 游戏更新后补新文本

需要一份 AssetStudio 导出的 `TextAsset` 目录（每个剧本一个 `.txt`）：

```bash
# 保留仓库已有译文，把新出现的台词以空值追加，并输出 new-lines.json
python tools/rebuild_from_dump.py --root . --dump-dir "D:/导出/TextAsset"

# 看某个剧本的完整上下文（NEW 行就是待翻译）
python tools/dump_context.py --root . --dump-dir "D:/导出/TextAsset" hmr_11120100032

# 把按顺序写好的译文回填（行数必须与 NEW 行数完全一致，防止错位）
python tools/apply_batch.py --root . hmr_11120100032 batch.txt

# 最后重算 manifest
python tools/build_manifest.py --root .
```

`rebuild_from_dump.py` 不会删除仓库里已有但新 dump 中不存在的键，避免丢译文；
这些多余键不影响插件（查不到就不会用到）。

---

## 6. manifest 格式与哈希算法

`translations/manifest/zh_Hans.json`：

```json
{
  "hash": "<清单自身哈希>",
  "names": "<names/zh_Hans.json 的对象哈希>",
  "static": "<static/zh_Hans.json 的对象哈希>",
  "ui_texts": "<ui_texts/zh_Hans.json 的对象哈希>",
  "novels": { "<剧情ID>": "<该剧情 JSON 的对象哈希>" },
  "replacements": { "Button_Party.png": "<文件字节 MD5>", "manifest.json": "<文件字节 MD5>" }
}
```

对象哈希（与插件一致）：

1. 按键名排序，递归展开嵌套对象，嵌套键用 `\x01` 连接；
2. 依次把 `"key" + \0 + "value" + \0` 喂给 MD5（UTF-8）；
3. `hash` 字段 = 去掉 `hash` 后的整个清单按同样算法得到的 MD5；
4. `replacements/` 下文件用**文件字节 MD5**。

`replacements/manifest.json` 是图片替换清单（`version: 1`），由插件读取，与主清单里的哈希分开。

---

## 7. 排查表

| 日志 / 现象 | 原因 | 处理 |
|---|---|---|
| `Manifest fetch returned NotFound` | CDN 地址错、分支不是 main、路径少了 `/translations` | 浏览器直接打开 `{CDN}/manifest/zh_Hans.json` 验证 |
| `Loaded cached manifest from local` | 远程 404，用了旧缓存 | 同上，修好 CDN |
| `Remote hash mismatch for novels/...` | 改了 JSON 没重算 manifest | `python tools/build_manifest.py --root .` |
| `manifest exceeds N KiB` | 清单异常膨胀（通常是误把大文件塞进来） | 检查 `novels/` 是否混入非剧本 JSON |
| 剧情仍是日文 | 键名带元数据 / 该剧情 ID 不在清单里 | 用 `dump_context.py` 对比键名 |
| 图片没替换 | `replacements/manifest.json` 与主清单哈希不匹配 | 重算主清单并确认图片未被压缩 |
| `unsupported manifest version` | 清单被加过 `version` 字段或结构被改 | 用本工具重新生成 |

---

## 8. 数据规模

- 剧情文件：1,409 个（`evs / hmn / hmr / men / mas`，覆盖当前客户端 Addressables 目录里的全部剧情 ID）
- 剧情条目：61,805 条
  - 其中 653 条是本次从新客户端 bundle 里新抽出的剧情（1017 号角色「阿什莉」个人线 + 零散新台词），已全部翻译
  - 其余来自既有译文与社区镜像（见致谢），并做了键名去重与统一
- MasterData 静态文本：86 张表 / 13,137 条（已与游戏 `DownloadCache/*.dat` 的 MasterData 全量对齐）
  - 其中 455 条是原作者停更后新增/变更的内容（技能描述 151、剧情简介 36、活动关卡 18、道具 6、武器 2、称号/任务等）
  - 覆盖率校验：MasterData 86 张表内 11,965 条唯一日文，缺口 0
- 人名 492 条、UI 文本 735 个控件
- 图片替换：8 张按钮图

剧情含成人内容，均为原作文本的完整翻译；设定中出场角色均为成年人。

## 9. 致谢

- AbyssMod 插件与原始翻译：anosu
- 剧情文本部分合并自社区镜像，特此致谢：
  - [ztztfdsf/dotabyss-translation](https://github.com/ztztfdsf/dotabyss-translation)（简体，1,377 话快照）
  - [liuyuns2/Dot-abyess-Lienchu-version](https://github.com/liuyuns2/Dot-abyess-Lienchu-version)（繁体 1,697 话，经 OpenCC 转简体后合并）
- 本仓库为社区维护的重建版本，目录结构与哈希算法与原仓库保持一致，便于随时切回或迁移。

