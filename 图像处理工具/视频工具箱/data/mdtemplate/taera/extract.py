"""Taera 模板信息提取：按 `关卡_性质_干员+干员` 文件名格式解析。"""

import os

NATURE_LIST = ["突袭", "无解", "待压", "剧情", "他人记录", "剿灭", "沙盘", "高难", "普通"]


def extract(filename: str, video_path: str = "") -> dict:
    base, _ = os.path.splitext(filename)
    if "_" not in base:
        operators = ["未知"]
        stage_part = base
    else:
        op_field = base.split("_")[-1]
        operators = [op.strip() for op in op_field.split("+") if op.strip()]
        stage_part = base.split("_")[0]
    raw = stage_part
    nature = "普通"
    for n in NATURE_LIST:
        if n in filename:
            nature = n
            break
    for n in NATURE_LIST:
        stage_part = stage_part.replace(n, "")
    stage_part = stage_part.strip("_- ")
    return {
        "filename": filename,
        "operators": operators,
        "nature": nature,
        "stage": stage_part if stage_part else raw,
    }
