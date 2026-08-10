# 视频工具箱模板系统参考

## 变量表

`template.md` 支持 `${变量名}` 和 `{{变量名}}` 两种写法（通用渲染器），`${inject:变量名}` 表示需要用户在"批量注入元数据"时填写的字段。

| 变量 | 说明 | 示例 |
|------|------|------|
| `${filename}` | 视频文件名 | `1-7_突袭_能天使+塞雷娅.mp4` |
| `${operators}` | 干员列表（全局按 `_`+`+` 提取） | `能天使`、`塞雷娅` |
| `${nature}` | 关卡难度/性质 | `突袭`、`普通` |
| `${stage}` | 关卡名（全局按 `_` 前段提取） | `1-7` |
| `${year}` / `${month}` / `${day}` | 当前日期分量 | `2026` / `5` / `30` |
| `${date}` | `YYYY/MM/DD` | `2026/05/30` |
| `${datetime}` | `YYYY-MM-DD HH:MM:SS` | `2026-05-30 14:30:00` |
| `${inject:xxx}` | 批量注入字段（保留为占位符，生成文档前由用户填写） | `${inject:活动名称}` |

列表值（如 `${operators}`）在通用渲染器中输出为每行 `  - 值`。

## 匹配规则细节

- `MdTemplateManager.match_template()` 按优先级降序遍历，返回第一个 `can_handle()` 为 True 的模板；全部不匹配返回 None。
- `can_handle()` 用 `importlib` 动态加载 `match.py` 并调用 `match(filename, video_path)`；模块按 `match_<模板名>` 缓存。
- `priority.txt` 内容为纯数字，解析失败默认 0。
- 应用侧兜底：`_get_template_for_video()` 在 `match_template` 返回 None 时取 taera，再取第一个模板——实际正常流程中 generic（恒 True）总会命中，兜底分支很少触发。

## 信息提取（默认不解析，extract.py 自定义）

模板未提供 `extract.py` 时**不提取任何信息**（返回空字典），只有渲染自带的 `${filename}` 可用。通用模板（如 generic）直接用 `${filename}` 即可，不会产生 干员/关卡/性质 等变量（渲染时回落为 `未知 / 普通 / 文件名`）。

需要解析文件名时，模板提供可选 `extract.py` 完全接管提取，签名：

```python
def extract(filename: str, video_path: str = "") -> dict:
    ...
```

返回 dict 会作为模板变量：`operators/nature/stage` 覆盖默认位置参数，其他键经 `extra_vars` 合并进模板变量（可用 `${键名}` 引用）。`extract()` 返回非 dict 或抛异常时，应用打印警告并按"不提取"处理。

渲染与输出文件名的 stage 都使用同一套提取结果（`_generate_content_for_video` 与 `_doc_generation_thread`）。

参考实现：`data/mdtemplate/taera/extract.py`，按 `关卡_性质_干员+干员` 解析（operators 取最后 `_` 后按 `+` 拆分；nature 取性质关键词；stage 取最前段并去掉性质词）。

## render.py 高级用法（taera 参考实现）

`render.py` 可选，存在时接管整个渲染流程，签名固定：

```python
def render(
    content: str,
    filename: str,
    extra_vars: Optional[dict] = None,
    preserve_placeholders: bool = False,
) -> str:
```

核心 render 只内置 `filename` 与日期变量，其余变量一律来自 `extra_vars`（即 extract.py 的返回）。`operators/nature/stage` 只是约定俗成的 extra_vars 键名，核心不做特殊处理；模板引用了未提供的变量时保留字面占位符（如 `${operators}`）。

taera 的 render.py 实现了"同一变量不同位置不同格式"：YAML frontmatter 里的 `${operators}` 输出列表格式，正文里输出 `N-干员+干员` 紧凑格式。通用渲染器做不到这种区分，需要时用 render.py。

## 现有模板速查

| 模板 | 优先级 | 匹配方式 | 特殊文件 |
|------|--------|----------|----------|
| `generic` | 0 | `match()` 恒 True（兜底） | 无（不解析文件名） |
| `taera` | 10 | 明日方舟关卡正则（`1-7`、`DT-EX-8` 等）+ 关键词 | `render.py`、`extract.py` |

## 排错

- 模板不生效：确认文件夹位于 `data/mdtemplate/`、`match.py` 存在且无语法错误、优先级没有压过其他模板、应用已重启（无刷新按钮）。
- 提取不对：默认不做解析，需要解析就在模板里加 `extract.py` 自定义（参考 taera）。
- 打包版与源码模板不一致：发布包用的是 `打包/dist/data/mdtemplate/` 副本。
