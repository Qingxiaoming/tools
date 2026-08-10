"""Taera模板渲染脚本：处理特有的变量替换逻辑。"""

import re
from typing import List, Optional


def render(
    content: str,
    filename: str,
    extra_vars: Optional[dict] = None,
    preserve_placeholders: bool = False,
) -> str:
    """渲染taera模板内容。

    特殊处理（operators/nature/stage 从 extra_vars 读取，由模板的 extract.py 提供）：
    - YAML frontmatter 中的 ${operators} 输出为列表格式
    - 其他位置（如标题）的 ${operators} 输出为 "人数-干员+干员" 格式
    - ${inject:xxx} 是可注入占位符，preserve_placeholders=True 时保留

    Args:
        preserve_placeholders: 如果为 True，保留 ${inject:xxx} 占位符不替换
    """
    from datetime import datetime
    import uuid

    today = datetime.today()
    extra = dict(extra_vars or {})
    ops = extra.get("operators") or ["未知"]

    # 处理 ${inject:xxx} 格式的可注入占位符
    placeholder_map = {}
    if preserve_placeholders:
        # 保留 ${inject:xxx} 占位符，保护起来不被后续变量替换处理
        for m in re.finditer(r"\$\{inject:(\w+)\}", content):
            var_name = m.group(1)
            token = "__INJECT_" + var_name.upper() + "_" + uuid.uuid4().hex[:8] + "__"
            placeholder_map[token] = m.group(0)
            content = content.replace(m.group(0), token, 1)
    else:
        # 不保留占位符时，直接替换成空字符串
        content = re.sub(r"\$\{inject:\w+\}", "", content)

    # 基础变量
    default_vars = {
        "filename": filename,
        "nature": extra.get("nature") or "普通",
        "stage": extra.get("stage") or filename,
        "year": today.year,
        "month": today.month,
        "day": today.day,
        "date": today.strftime("%Y/%m/%d"),
        "datetime": today.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 额外变量（operators 由下方特殊逻辑处理，不进入通用替换）
    if extra:
        default_vars.update({k: v for k, v in extra.items() if k != "operators"})

    # 替换普通变量
    def replace_var(match):
        var_name = match.group(1).strip()
        value = default_vars.get(var_name, match.group(0))
        if isinstance(value, list):
            return "\n".join(f"  - {v}" for v in value)
        return str(value)

    content = re.sub(r"\$\{(\w+)\}", replace_var, content)
    content = re.sub(r"\{\{(\w+)\}\}", replace_var, content)

    # 特殊处理 ${operators}
    # 先处理 YAML frontmatter 中的（行首有空格或-）
    def replace_operators_yaml(match):
        return "\n".join(f"  - {v}" for v in ops)

    # 再处理其他位置的（紧凑格式）
    def replace_operators_compact(match):
        return f"{len(ops)}-{ '+'.join(ops) }"

    # 在 YAML frontmatter 区域使用列表格式
    lines = content.split('\n')
    result_lines = []
    in_frontmatter = False
    frontmatter_started = False

    for line in lines:
        if line.strip() == '---':
            frontmatter_started = not frontmatter_started
            in_frontmatter = frontmatter_started
            result_lines.append(line)
            continue

        if in_frontmatter:
            # 在 frontmatter 中，检查是否是 operators 行
            if '${operators}' in line:
                result_lines.append(re.sub(r"\$\{operators\}", replace_operators_yaml, line))
            else:
                result_lines.append(line)
        else:
            # 在 frontmatter 外，使用紧凑格式
            result_lines.append(re.sub(r"\$\{operators\}", replace_operators_compact, line))

    result = '\n'.join(result_lines)

    # 恢复 ${inject:xxx} 占位符
    for token, original in placeholder_map.items():
        result = result.replace(token, original)

    return result
