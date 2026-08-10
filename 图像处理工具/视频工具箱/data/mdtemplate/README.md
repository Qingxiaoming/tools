# MD模板系统说明

本文档说明如何为视频工具箱创建和使用自定义MD模板。

## 模板结构

每个模板是一个独立的文件夹，位于 `data/mdtemplate/` 目录下：

```
data/mdtemplate/
├── generic/              # 默认通用模板（优先级最低）
│   ├── template.md       # 模板内容文件
│   ├── match.py          # 匹配规则脚本
│   ├── extract.py        # 信息提取脚本（可选）
│   └── priority.txt      # 优先级数字（可选）
├── taera/                # 示例：明日方舟专用模板
│   ├── template.md
│   ├── match.py
│   ├── extract.py        # 信息提取（taera 自带：按 关卡_干员+干员 解析）
│   └── priority.txt
└── your_template/        # 你的自定义模板
    ├── template.md
    ├── match.py
    ├── extract.py        # 信息提取脚本（可选）
    └── priority.txt
```

## 文件说明

### 1. template.md - 模板内容

支持变量替换，使用 `${变量名}` 或 `{{变量名}}` 格式：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `${filename}` | 视频文件名 | `1-7_突袭_能天使+塞雷娅.mp4` |
| `${operators}` | 操作员列表（从文件名提取） | `能天使` `塞雷娅` |
| `${nature}` | 关卡难度/性质 | `突袭` `普通` |
| `${stage}` | 关卡名称 | `1-7` |
| `${date}` | 当前日期 | `2026/05/30` |
| `${datetime}` | 当前日期时间 | `2026-05-30 14:30:00` |
| `${year}` | 当前年份 | `2026` |
| `${month}` | 当前月份 | `5` |
| `${day}` | 当前日期 | `30` |

### 可注入变量

使用 `${inject:变量名}` 格式标记需要在批量注入时由用户填写的字段：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `${inject:activity}` | 活动名称 | `感谢庆典` |
| `${inject:bv}` | BV号 | `BV1xx411c7mD` |
| `${inject:备注}` | 自定义备注 | `无` |

示例模板内容：

```markdown
---
属于活动:
  - ${inject:activity}
是否完成: true
bv号: ${inject:bv}
关卡难度:
  - ${nature}
备注: ${inject:备注}
参战干员:
${operators}
攻略者: 项泓小时候/
创建时间: ${date}
---
# 本地视频
![[${filename}]]
```

### 2. match.py - 匹配规则

必须包含 `match(filename: str, video_path: str = "") -> bool` 函数，返回是否使用此模板。

示例 - 通用匹配（始终匹配）：

```python
def match(filename: str, video_path: str = "") -> bool:
    return True
```

示例 - 根据文件名模式匹配：

```python
import re

def match(filename: str, video_path: str = "") -> bool:
    # 匹配明日方舟关卡格式：1-7, H12-4, DT-EX-8 等
    base = filename.rsplit('.', 1)[0]
    if '_' not in base:
        return False
    stage_part = base.split('_')[0]
    patterns = [
        r'^\d+-\d+',
        r'^[A-Z]+-\d+',
        r'^H\d+-\d+',
    ]
    return any(re.search(p, stage_part) for p in patterns)
```

### 3. priority.txt - 优先级

纯数字文件，数字越大优先级越高。自动匹配时按优先级从高到低尝试。

- `generic` 模板建议优先级：`0`
- 专用模板建议优先级：`10` 或更高

### 4. extract.py - 信息提取（可选）

定义 `extract(filename: str, video_path: str = "") -> dict`，返回的字典会成为模板变量：

```python
def extract(filename: str, video_path: str = "") -> dict:
    return {
        "operators": ["能天使", "塞雷娅"],
        "nature": "突袭",
        "stage": "1-7",
        "活动": "感谢庆典",   # 自定义变量，模板里用 ${活动} 引用
    }
```

**不提供 extract.py 时不做任何文件名解析**，只有 `${filename}` 可用（`operators/nature/stage` 为空，渲染时回落为 `未知 / 普通 / 文件名`）。需要从文件名解析信息（如干员/关卡/性质）时，用 extract.py 自定义，参考 `taera/extract.py`。

## 界面功能说明

### 文档生成页签

1. **拖入视频文件**：支持拖入多个视频文件到窗口

2. **模板选择**：
   - 下拉框选择指定模板
   - 选择「自动匹配」让系统根据文件名自动选择
   - 点击「🔄 自动匹配」按钮强制重新匹配所有视频
   - 修改模板目录后重启应用重新扫描模板

3. **批量注入元数据**：
   - 点击「📋 批量注入元数据」按钮
   - 在弹出的表格中填写每个视频的可注入字段（`${inject:xxx}` 标记的变量）
   - 执行注入后，如需修改请在视频列表中双击编辑

4. **内容预览/编辑**：
   - 左右切换按钮浏览不同视频的生成内容
   - 在文本框中直接编辑内容
   - 点击「应用更改」保存修改（不影响源模板文件）
   - 修改后的内容会在生成文档时使用

5. **生成文档**：
   - 点击「预览全部」在日志区查看所有文档摘要
   - 点击「生成文档」生成所有MD文件到输出目录

### 模板自动匹配流程

1. 用户拖入视频或点击「自动匹配」
2. 系统按优先级从高到低遍历模板
3. 对每个模板调用 `match.py` 中的 `match()` 函数
4. 第一个返回 `True` 的模板被选中
5. 如果没有匹配，使用默认模板

## 创建新模板的步骤

1. 在 `data/mdtemplate/` 下创建新文件夹，如 `my_template`
2. 创建 `template.md`，使用变量设计模板格式
3. 创建 `match.py`，编写匹配逻辑
4. 创建 `priority.txt`，设置优先级数字
5. （可选）需要从文件名解析信息时，创建 `extract.py`（参考 `taera/extract.py`）；不需要解析的模板跳过此步
6. 重启应用即可看到并使用新模板

## 注意事项

- 模板修改后需重启应用生效（界面暂无"刷新模板"按钮）
- 内容编辑区的修改仅保存在内存中，不影响源模板文件
- 重启程序后需要重新进行内容微调
- 模板文件夹名即为模板显示名称
