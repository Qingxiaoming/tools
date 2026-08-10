"""<模板名> 信息提取（可选）：自定义从文件名提取哪些变量。

返回 dict 会成为模板变量；不提供本文件时使用全局默认规则（关卡_干员+干员）。
"""


def extract(filename: str, video_path: str = "") -> dict:
    return {
        "operators": ["示例干员"],
        "nature": "普通",
        "stage": "示例关卡",
        "备注": "自定义变量示例",
    }
