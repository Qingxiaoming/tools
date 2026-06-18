"""MD模板管理服务：支持动态加载、文件名匹配和模板渲染。"""

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional


@dataclass
class MdTemplate:
    """表示一个MD模板。"""

    name: str
    template_dir: Path
    priority: int = 0  # 优先级，数字越大优先级越高

    def get_template_path(self) -> Path:
        """获取模板文件路径。"""
        return self.template_dir / "template.md"

    def get_match_path(self) -> Path:
        """获取匹配脚本路径。"""
        return self.template_dir / "match.py"

    def get_render_path(self) -> Path:
        """获取渲染脚本路径（可选）。"""
        return self.template_dir / "render.py"

    def load_content(self) -> str:
        """加载模板内容。"""
        template_path = self.get_template_path()
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        return ""

    def can_handle(self, filename: str, video_path: str = "") -> bool:
        """检查此模板是否匹配给定的文件名。"""
        match_path = self.get_match_path()
        if not match_path.exists():
            return False

        try:
            # 动态导入匹配模块
            spec = __import__("importlib.util").util.spec_from_file_location(
                f"match_{self.name}", match_path
            )
            if spec is None or spec.loader is None:
                return False
            module = __import__("importlib.util").util.module_from_spec(spec)
            sys.modules[f"match_{self.name}"] = module
            spec.loader.exec_module(module)

            # 调用 match 函数
            if hasattr(module, "match"):
                return module.match(filename, video_path)
        except Exception as e:
            print(f"[模板匹配错误] {self.name}: {e}")
            return False

        return False

    def render(
        self,
        filename: str,
        operators: Optional[List[str]] = None,
        nature: str = "普通",
        stage: str = "",
        extra_vars: Optional[dict] = None,
        preserve_placeholders: bool = False,
    ) -> str:
        """渲染模板内容。

        Args:
            preserve_placeholders: 如果为 True，保留 ${inject:xxx} 格式的可注入占位符不替换，
                                   用于后续注入操作
        """
        content = self.load_content()
        if not content:
            raise ValueError(f"模板 {self.name} 没有内容")

        # 如果有自定义渲染脚本，使用它
        render_path = self.get_render_path()
        if render_path.exists():
            try:
                spec = __import__("importlib.util").util.spec_from_file_location(
                    f"render_{self.name}", render_path
                )
                if spec and spec.loader:
                    module = __import__("importlib.util").util.module_from_spec(spec)
                    sys.modules[f"render_{self.name}"] = module
                    spec.loader.exec_module(module)
                    if hasattr(module, "render"):
                        return module.render(
                            content=content,
                            filename=filename,
                            operators=operators,
                            nature=nature,
                            stage=stage,
                            extra_vars=extra_vars,
                            preserve_placeholders=preserve_placeholders,
                        )
            except Exception as e:
                print(f"[模板渲染错误] {self.name}: {e}")

        # 默认变量
        today = __import__("datetime").datetime.today()
        default_vars = {
            "filename": filename,
            "operators": operators or ["未知"],
            "nature": nature or "普通",
            "stage": stage or filename,
            "year": today.year,
            "month": today.month,
            "day": today.day,
            "date": today.strftime("%Y/%m/%d"),
            "datetime": today.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 处理 ${inject:xxx} 格式的可注入占位符
        # 如果 preserve_placeholders=True，保留原样给后续注入
        # 如果 preserve_placeholders=False，直接替换成空字符串
        if preserve_placeholders:
            # 保留 ${inject:xxx} 占位符，保护起来不被后续变量替换处理
            import uuid
            placeholder_map = {}
            for m in re.finditer(r"\$\{inject:(\w+)\}", content):
                var_name = m.group(1)
                token = "__INJECT_" + var_name.upper() + "_" + uuid.uuid4().hex[:8] + "__"
                placeholder_map[token] = m.group(0)
                content = content.replace(m.group(0), token, 1)
        else:
            # 不保留占位符时，直接替换成空字符串
            content = re.sub(r"\$\{inject:\w+\}", "", content)
            placeholder_map = {}

        # 合并额外变量
        if extra_vars:
            default_vars.update(extra_vars)

        # 简单变量替换 ${var} 或 {{var}}
        def replace_var(match):
            var_name = match.group(1).strip()
            value = default_vars.get(var_name, match.group(0))
            if isinstance(value, list):
                return "\n".join(f"  - {v}" for v in value)
            return str(value)

        # 支持 ${var} 和 {{var}} 两种格式
        content = re.sub(r"\$\{(\w+)\}", replace_var, content)
        content = re.sub(r"\{\{(\w+)\}\}", replace_var, content)

        # 恢复占位符
        for token, original in placeholder_map.items():
            content = content.replace(token, original)

        return content

class MdTemplateManager:
    """MD模板管理器：扫描、管理和自动匹配模板。"""

    def __init__(self, templates_dir: Optional[Path] = None):
        """初始化模板管理器。

        Args:
            templates_dir: 模板根目录，默认为项目下的 data/mdtemplate
        """
        if templates_dir is None:
            templates_dir = self._get_default_templates_dir()

        self.templates_dir = Path(templates_dir)
        self._templates: List[MdTemplate] = []
        self._scan_templates()

    def _get_default_templates_dir(self) -> Path:
        """获取默认模板目录路径，兼容开发模式和 PyInstaller 打包模式。"""
        # PyInstaller 打包模式：exe 同级目录的 data 文件夹
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent / "data" / "mdtemplate"

        # 开发模式：从当前文件位置计算项目根目录
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        return project_root / "data" / "mdtemplate"

    def _scan_templates(self) -> None:
        """扫描模板目录，加载所有模板。"""
        self._templates.clear()

        if not self.templates_dir.exists():
            print(f"[模板管理器] 模板目录不存在: {self.templates_dir}")
            return

        # 遍历所有子目录
        for item in self.templates_dir.iterdir():
            if item.is_dir():
                template_name = item.name
                priority = self._get_template_priority(item)
                template = MdTemplate(
                    name=template_name, template_dir=item, priority=priority
                )
                self._templates.append(template)

        # 按优先级排序（高优先级在前）
        self._templates.sort(key=lambda t: t.priority, reverse=True)

        print(f"[模板管理器] 加载了 {len(self._templates)} 个模板")
        for t in self._templates:
            print(f"  - {t.name} (优先级: {t.priority})")

    def _get_template_priority(self, template_dir: Path) -> int:
        """获取模板优先级，从 priority.txt 读取，默认为 0。"""
        priority_file = template_dir / "priority.txt"
        if priority_file.exists():
            try:
                return int(priority_file.read_text(encoding="utf-8").strip())
            except ValueError:
                pass
        return 0

    def get_all_templates(self) -> List[MdTemplate]:
        """获取所有已加载的模板。"""
        return self._templates.copy()

    def get_template_names(self) -> List[str]:
        """获取所有模板名称列表。"""
        return [t.name for t in self._templates]

    def get_template(self, name: str) -> Optional[MdTemplate]:
        """根据名称获取模板。"""
        for template in self._templates:
            if template.name == name:
                return template
        return None

    def match_template(self, filename: str, video_path: str = "") -> Optional[MdTemplate]:
        """根据文件名自动匹配最合适的模板。

        按照优先级从高到低遍历模板，返回第一个匹配的模板。
        """
        for template in self._templates:
            if template.can_handle(filename, video_path):
                return template
        return None

    def reload(self) -> None:
        """重新扫描模板目录。"""
        self._scan_templates()

    def extract_operators(self, filename: str) -> List[str]:
        """从文件名中提取操作员列表。"""
        base = os.path.splitext(filename)[0]
        if "_" not in base:
            return ["未知"]
        op_field = base.split("_")[-1]
        return [op.strip() for op in op_field.split("+") if op.strip()]

    def extract_nature(self, filename: str, nature_list: Optional[List[str]] = None) -> str:
        """从文件名中提取性质/难度。"""
        if nature_list is None:
            nature_list = ["突袭", "无解", "待压", "剧情", "他人记录", "剿灭", "沙盘", "普通"]
        for n in nature_list:
            if n in filename:
                return n
        return "普通"

    def extract_stage_name(self, filename: str, nature_list: Optional[List[str]] = None) -> str:
        """从文件名中提取关卡/阶段名称。"""
        if nature_list is None:
            nature_list = ["突袭", "无解", "待压", "剧情", "他人记录", "剿灭", "沙盘", "普通"]
        base, _ = os.path.splitext(filename)
        part = base.split("_")[0] if "_" in base else base
        raw = part
        for n in nature_list:
            part = part.replace(n, "")
        part = part.strip("_- ")
        return part if part else raw


# 全局模板管理器实例
_template_manager: Optional[MdTemplateManager] = None


def get_template_manager() -> MdTemplateManager:
    """获取全局模板管理器实例（单例模式）。"""
    global _template_manager
    if _template_manager is None:
        _template_manager = MdTemplateManager()
    return _template_manager


def reload_templates() -> None:
    """重新加载所有模板。"""
    manager = get_template_manager()
    manager.reload()


__all__ = ["MdTemplate", "MdTemplateManager", "get_template_manager", "reload_templates"]
