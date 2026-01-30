# PyInstaller hook：确保 tkinterdnd2 的 tkdnd 库文件被打包进 exe
# 使用方式：pyinstaller 时加上 --additional-hooks-dir=.
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files('tkinterdnd2')
