# -*- mode: python ; coding: utf-8 -*-
# 视频工具箱 PyInstaller 打包配置
# 使用方式：在 打包 目录下运行 build.bat，或执行 pyinstaller video_tools.spec

import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# 收集 tkinterdnd2 的 tkdnd 库文件，否则 exe 运行会报 "Unable to load tkdnd library"
tkdnd_datas = collect_data_files('tkinterdnd2')

# 项目根目录（视频工具箱），含 main.pyw 和 src/
spec_dir = os.path.dirname(os.path.abspath(SPEC))
root_dir = os.path.abspath(os.path.join(spec_dir, '..'))

# 收集数据文件：tkdnd 库 + 配置文件
# 注意：data 目录不打包，用户可在 exe 旁自定义
all_datas = tkdnd_datas + [
    (os.path.join(root_dir, 'config.json'), '.'),  # 打包 config.json 到 exe 同级目录
]

a = Analysis(
    [os.path.join(root_dir, 'main.pyw')],
    pathex=[root_dir],
    binaries=[],
    datas=all_datas,
    hiddenimports=[
        'src',
        'src.core',
        'src.core.app',
        'src.core.config',
        'src.core.overlay',
        'src.core.subprocess_util',
        'src.services',
        'src.services.repair',
        'src.tabs',
        'src.tabs.segment',
        'src.tabs.crop',
        'src.tabs.merge',
        'src.tabs.doc',
        'src.tabs.weekly',
        'src.tabs.roi',
        'tkinterdnd2',
        'cv2',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'plyer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VideoTools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # 不显示黑色控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
