"""站点解析结果实体。"""

from dataclasses import dataclass


@dataclass
class SiteEntity:
    site: str  # "bilibili" / "generic" / ...
    display: str  # 人类可读站点名
    type: str  # video / bangumi / collection / favorite / shortlink / unknown ...
    clean_url: str  # 清洗后的下载 URL（去追踪参数）
    raw_url: str = ""
    id: str = ""  # BV / av / ep / ss / ml 等实体标识
    p: str = ""  # 分P序号（如 "1" / "3-5"）
    note: str = ""  # 解析器提示（如短链展开结果）
