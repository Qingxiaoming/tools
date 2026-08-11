"""B 站登录态校验与浏览器 cookie 导入。"""

import json
import sqlite3
import subprocess
import tempfile
import urllib.request
from pathlib import Path

NAV_URL = "https://api.bilibili.com/x/web-interface/nav"


def validate_cookie(cookie: str) -> tuple[bool, str]:
    """用 B 站 nav 接口校验 SESSDATA；返回 (是否有效, 说明)。"""
    cookie = (cookie or "").strip()
    if not cookie:
        return False, "cookie 为空"
    try:
        request = urllib.request.Request(
            NAV_URL,
            headers={"User-Agent": "Mozilla/5.0", "Cookie": cookie},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
    except Exception as exc:
        return False, f"校验请求失败: {exc}"
    if data.get("code") == 0 and data.get("data", {}).get("isLogin"):
        name = data.get("data", {}).get("uname", "")
        return True, f"有效（登录为 {name}）"
    return False, "无效（B 站返回账号未登录），请重新复制"


def _parse_sessdata(jar: Path) -> str:
    if not jar.exists():
        return ""
    for line in jar.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) >= 7 and parts[5] == "SESSDATA" and parts[0].strip() in (
            ".bilibili.com",
            "bilibili.com",
        ):
            return parts[6]
    return ""


def _firefox_profile_dirs() -> list[Path]:
    """扫描 Firefox 配置文件（标准 / Snap / Flatpak 路径）。"""
    roots = [
        Path.home() / ".mozilla" / "firefox",
        Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
        Path.home() / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
    ]
    dirs: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for profile in root.iterdir():
            if (profile / "cookies.sqlite").exists():
                dirs.append(profile)
    return dirs


def _read_firefox_sessdata() -> tuple[str, str]:
    """直接从 Firefox cookies.sqlite 读取 SESSDATA（cookie 值明文存储）。

    返回 (cookie, 来源)；找不到返回 ("", "")。
    """
    for profile in _firefox_profile_dirs():
        db = profile / "cookies.sqlite"
        try:
            try:
                con = sqlite3.connect(str(db), timeout=3)
            except sqlite3.Error:
                con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=3)
            row = con.execute(
                "SELECT value FROM moz_cookies WHERE name='SESSDATA' AND host LIKE '%bilibili%' LIMIT 1"
            ).fetchone()
            con.close()
            if row and row[0]:
                return f"SESSDATA={row[0]}", f"Firefox（{profile.parent.name}/{profile.name}）"
        except Exception:
            continue
    return "", ""


def default_browser_name() -> str:
    """Linux 下用 xdg-settings 识别默认浏览器，映射到 yt-dlp 名。"""
    try:
        out = subprocess.run(
            ["xdg-settings", "get", "default-web-browser"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip().lower()
    except Exception:
        return ""
    for key, name in (
        ("firefox", "firefox"),
        ("google-chrome", "chrome"),
        ("chromium", "chromium"),
        ("microsoft-edge", "edge"),
        ("brave", "brave"),
        ("vivaldi", "vivaldi"),
    ):
        if key in out:
            return name
    return ""


def import_cookie_from_browser() -> tuple[str, str]:
    """从浏览器读取 bilibili SESSDATA。

    Firefox 直读 cookies.sqlite（覆盖 Snap/Flatpak）；Chrome/Edge/Chromium/
    Brave/Vivaldi 用 yt-dlp --cookies-from-browser。返回 (cookie, 来源说明)。
    """
    # 1) Firefox 直读
    cookie, source = _read_firefox_sessdata()
    if cookie:
        return cookie, source

    # 2) yt-dlp 读 Chromium 系浏览器
    targets = ["chrome", "edge", "chromium", "brave", "vivaldi"]
    snap_chromium = Path.home() / "snap" / "chromium" / "common" / "chromium"
    if snap_chromium.exists():
        targets.append(f"chromium:{snap_chromium}")

    for browser in targets:
        jar = None
        try:
            handle = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
            jar = Path(handle.name)
            handle.close()
            result = subprocess.run(
                [
                    "yt-dlp",
                    "--cookies-from-browser",
                    browser,
                    "--cookies",
                    str(jar),
                    "--skip-download",
                    "-O",
                    "id",
                    "https://www.bilibili.com",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            sess = _parse_sessdata(jar)
            if sess:
                return f"SESSDATA={sess}", f"已从 {browser} 导入"
        except Exception:
            continue
        finally:
            if jar is not None:
                jar.unlink(missing_ok=True)
    hint = f"（默认浏览器: {default_browser_name()}）" if default_browser_name() else ""
    return (
        "",
        "未找到 B 站 cookie。常见原因：浏览器设置为关闭即清除 Cookie（自动导入读不到，请用手动粘贴），"
        f"或未登录。{hint}",
    )
