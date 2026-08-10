"""Taera模板匹配规则：匹配明日方舟/Arknights相关视频文件名。

匹配以下模式：
- 包含关卡名称（如 1-7, H12-4, DT-EX-8 等）
- 文件名中包含操作员名称（用+分隔）
"""

import re


# 常见的明日方舟关卡前缀模式
ARKNIGHTS_STAGE_PATTERNS = [
    r'^\d+-\d+',               # 1-7
    r'^\d+-jt\d+',             # 1-JT1
    r'^\d+-ex\d+',             # 1-EX2
    r'^\d+-s\d+(?:-[ab])?',    # 2-S1 / 2-S1-a
    r'^[a-z]+-\d+',            # DT-8
    r'^[a-z]+-ex\d+',          # DT-EX8
    r'^[a-z]+-s\d+(?:-[ab])?', # DT-S1
    r'^[a-z]+-mo\d+',          # DT-MO1
    r'^[a-z]+-hx\d+',          # 1-HX1
    r'^[a-z]+-f\d+',           # DT-F1
    r'^[a-z]+\d+-\d+',         # H12-4 字母+数字-数字
    r'^[a-z]+-[a-z]+-\d+',     # DT-EX-8 字母-字母-数字
    r'^vecT\d-[cd]',           # vecT1-c
    r'^tnT\d-\d+',             # tnT1-3
]

def match(filename: str, video_path: str = "") -> bool:
    """判断文件名是否符合Taera模板格式。

    匹配条件：
    1. 文件名包含下划线（分隔关卡名和操作员）
    2. 关卡名部分符合明日方舟关卡命名模式
    """
    base = filename.rsplit('.', 1)[0]  # 移除扩展名

    # 必须包含下划线来分隔关卡名和操作员
    if '_' not in base:
        return False

    # 获取关卡名部分（下划线前的部分）
    stage_part = base.split('_')[0]

    # 检查是否符合任意一种关卡模式
    for pattern in ARKNIGHTS_STAGE_PATTERNS:
        if re.search(pattern, stage_part, re.IGNORECASE):
            return True

    # 特殊标记：如果文件名中包含"突袭"、"剿灭"等关键词，也匹配
    ark_keywords = ['突袭', '剿灭', '危机合约', '集成战略', '肉鸽', '保全派驻', '高难']
    for keyword in ark_keywords:
        if keyword in filename:
            return True

    return False
