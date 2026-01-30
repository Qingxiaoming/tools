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

a = Analysis(
    [os.path.join(root_dir, 'main.pyw')],
    pathex=[root_dir],
    binaries=[],
    datas=tkdnd_datas,
    hiddenimports=[
        'src',
        'src.app',
        'src.config',
        'src.segment',
        'src.crop',
        'src.merge',
        'src.doc',
        'src.roi_selector',
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
