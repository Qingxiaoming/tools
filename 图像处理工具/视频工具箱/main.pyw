import sys
import os

# 打包成 exe 后，需把运行目录加入 path，否则找不到同目录的 app、config 等模块
if getattr(sys, "frozen", False):
    sys.path.insert(0, sys._MEIPASS)
else:
    root_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, root_dir)
    sys.path.insert(0, os.path.join(root_dir, "src"))

from src.app import VideoTools


def main() -> None:
    app = VideoTools()
    app.mainloop()


if __name__ == "__main__":
    main()
