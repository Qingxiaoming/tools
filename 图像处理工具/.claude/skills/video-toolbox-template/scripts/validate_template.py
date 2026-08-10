#!/usr/bin/env python3
"""验证视频工具箱 MD 模板：对示例文件名执行 match()，可选渲染输出。

用法：
    validate_template.py <模板目录> <示例文件名> [<示例文件名> ...] [--render]

模板目录通常是 data/mdtemplate/<模板名>/。
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path


def _load_match(template_dir: Path, name: str):
    match_path = template_dir / "match.py"
    if not match_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"match_{name}", match_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return getattr(module, "match", None)


def render(template_dir: Path, name: str, filename: str, project_root: Path) -> str:
    """复用项目 md_templates.MdTemplate.render（按文件路径加载，避免触发应用级依赖）。"""
    md_path = project_root / "src" / "services" / "md_templates.py"
    if not md_path.exists():
        sys.exit(f"找不到 md_templates.py：{md_path}（用 --project-root 指定视频工具箱根目录）")
    spec = importlib.util.spec_from_file_location("vtt_md_templates", md_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    tpl = module.MdTemplate(name=name, template_dir=template_dir)
    extracted = tpl.extract(filename)
    return tpl.render(
        filename=filename,
        operators=extracted.get("operators"),
        nature=extracted.get("nature", "普通"),
        stage=extracted.get("stage", ""),
        extra_vars={
            k: v for k, v in extracted.items()
            if k not in ("operators", "nature", "stage")
        },
        preserve_placeholders=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="验证视频工具箱 MD 模板")
    parser.add_argument("template_dir", help="模板目录（含 template.md / match.py / priority.txt）")
    parser.add_argument("filenames", nargs="+", help="示例视频文件名")
    parser.add_argument("--render", action="store_true", help="对匹配的示例渲染并打印 Markdown")
    parser.add_argument(
        "--project-root",
        help="视频工具箱项目根目录（含 src/）；默认从模板目录向上推断",
    )
    args = parser.parse_args()

    template_dir = Path(args.template_dir).resolve()
    if not template_dir.is_dir():
        sys.exit(f"模板目录不存在: {template_dir}")
    name = template_dir.name
    project_root = Path(args.project_root).resolve() if args.project_root else template_dir.parents[2]

    priority = 0
    pfile = template_dir / "priority.txt"
    if pfile.exists():
        try:
            priority = int(pfile.read_text(encoding="utf-8").strip())
        except ValueError:
            pass

    print(f"模板: {name} (优先级 {priority})")
    print(f"目录: {template_dir}")

    match_fn = _load_match(template_dir, name)
    if match_fn is None:
        sys.exit("未找到 match.py 或其中没有 match() 函数")

    for filename in args.filenames:
        try:
            ok = bool(match_fn(filename))
        except Exception as e:
            print(f"  [异常] {filename}: {type(e).__name__}: {e}")
            continue
        print(f"  {'[匹配]' if ok else '[不匹配]'} {filename}")
        if ok and args.render:
            try:
                content = render(template_dir, name, filename, project_root)
                print("----- 渲染结果 -----")
                print(content.rstrip("\n"))
                print("-------------------")
            except Exception as e:
                print(f"  [渲染异常] {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
