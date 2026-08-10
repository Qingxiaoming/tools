"""<模板名> 匹配规则。"""


def match(filename: str, video_path: str = "") -> bool:
    """返回 True 表示使用此模板。示例：按关键词匹配。"""
    return "关键词" in filename
