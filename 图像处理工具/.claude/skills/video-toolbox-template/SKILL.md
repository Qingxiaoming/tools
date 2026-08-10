---
name: video-toolbox-template
description: Create, modify, or debug MD templates for the 视频工具箱 (Video Toolbox) document-generation tab. Use when a user asks to add a new template, adjust template matching rules (match.py), template content (template.md), priority (priority.txt), or custom rendering (render.py), or when template match/render behavior needs verification.
---

# 视频工具箱模板（Video Toolbox MD Templates）

## 概述

模板系统位于 `视频工具箱/data/mdtemplate/<模板名>/`，供"文档生成"页签把视频文件名渲染成 Obsidian Markdown 文档。本 skill 用于创建、修改和验证模板。

## 模板目录结构

每个模板是一个独立文件夹：

```
data/mdtemplate/<name>/
├── template.md     # 必需：模板内容，支持 ${var} / {{var}} / ${inject:xxx}
├── match.py        # 必需：匹配函数 match(filename, video_path) -> bool
├── priority.txt    # 可选：优先级数字，越大越优先，默认 0
└── render.py       # 可选：自定义渲染脚本（taera 有参考实现）
```

## 匹配与优先级规则

- 系统按 priority 从高到低调用每个模板的 `match()`，**第一个返回 True 的模板被选中**。
- 没有任何模板匹配时落到 generic（`match()` 恒 True，优先级 0）——generic 是兜底模板，不要删除。
- `match()` 只决定"用哪个模板"，**不决定信息提取**。

## 关键约束：信息提取是全局写死的

`operators / nature / stage` 的提取规则在 `src/services/md_templates.py` 中全局实现，**按 `关卡_干员+干员` 的文件名格式解析**：

- operators：`_` 后最后一段，按 `+` 拆分；
- nature：文件名中出现的性质关键词（默认列表：突袭/无解/待压/剧情/他人记录/剿灭/沙盘/普通）；
- stage：`_` 前第一段，去掉性质关键词。

模板可用的 `${stage}`、`${operators}` 等变量来自这套全局解析。**若新模板的文件名格式与"关卡_干员+干员"不符，提取结果会不正确**——先与用户确认文件名格式；需要改提取逻辑时，先获得用户授权再动 `src/services/md_templates.py`。

## 创建新模板

1. 复制骨架 `assets/template-skeleton/` 到 `data/mdtemplate/<新名字>/`（模板文件夹名即显示名）。
2. 编辑 `template.md`：用变量占位（变量表见 references/template-system.md），`${inject:xxx}` 标记需要用户批量填写的字段。
3. 实现 `match.py`：定义 `match(filename, video_path="") -> bool`。参考 taera（正则匹配）或 generic（恒 True）。
4. 设置 `priority.txt`：专用模板建议 10，通用模板 0。
5. 验证：运行 `scripts/validate_template.py <模板目录> <示例文件名>... --render` 确认匹配与渲染；再按项目说明启动应用在"文档生成"页签实测。模板没有"刷新"按钮，**修改后重启应用生效**。

## 修改现有模板

- 改内容：直接编辑 `template.md`。
- 改匹配：编辑 `match.py`，保持 `match(filename, video_path="") -> bool` 签名。
- 改优先级：编辑 `priority.txt`。
- 高级渲染：新增或修改 `render.py`，签名见 taera 示例与 references/template-system.md。

## 验证命令

```bash
python scripts/validate_template.py data/mdtemplate/taera "1-7_突袭_能天使+塞雷娅.mp4" "H12-4_无解_银灰.mp4" --render
```

脚本打印每个示例文件名的匹配结果，`--render` 时打印渲染出的 Markdown。

## 注意

- 打包发布版使用 `打包/dist/data/mdtemplate/` 的独立副本，改源码模板后如需发布需同步该目录。
- `match.py` 抛出异常时应用会在控制台打印 `[模板匹配错误] <模板名>`，匹配不上先看这个。
