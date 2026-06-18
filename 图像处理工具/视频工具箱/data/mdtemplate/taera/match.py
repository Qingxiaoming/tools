"""Taera模板匹配规则：匹配明日方舟/Arknights相关视频文件名。

匹配以下模式：
- 包含关卡名称（如 1-7, H12-4, DT-EX-8 等）
- 文件名中包含操作员名称（用+分隔）
"""

import re


# 常见的明日方舟关卡前缀模式
ARKNIGNTS_STAGE_PATTERNS = [
    r'^\d+-\d+',              
    r'^\d+-jt\d+',           
    r'^\d+-ex\d+',         
    r'^\d+-s\d+(?:-[ab])?', 
    r'^[a-z]+-\d+',           
    r'^[a-z]+-ex\d+',         
    r'^[a-z]+-s\d+(?:-[ab])?', 
    r'^[a-z]+-mo\d+',         
    r'^[a-z]+-hx\d+',         
    r'^[a-z]+-f\d+',          
    r'^vecT\d-[cd]',          
    r'^tnT\d-\d+',            
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
    for pattern in ARKNIGNTS_STAGE_PATTERNS:
        if re.search(pattern, stage_part, re.IGNORECASE):
            return True

    # 特殊标记：如果文件名中包含"突袭"、"剿灭"等关键词，也匹配
    ark_keywords = ['突袭', '剿灭', '危机合约', '集成战略', '肉鸽', '保全派驻']
    for keyword in ark_keywords:
        if keyword in filename:
            return True

    return False
