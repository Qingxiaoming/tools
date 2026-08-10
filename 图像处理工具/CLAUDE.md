# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

本仓库包含两个独立的视频工具箱项目：

1. **视频工具箱** (`视频工具箱/`) - Python + Tkinter 的原始版本
2. **VideoToolbox-MFAAvalonia** (`VideoToolbox-MFAAvalonia/`) - C# + Avalonia UI 的重构版本（目标与 Python 版本功能同款）

两个项目共享相同的业务逻辑和 ffmpeg 命令构建方式。

---

## Python 视频工具箱

### 常用命令

```bash
# 进入目录
cd "视频工具箱"

# 安装依赖
pip install -r requirements.txt

# 运行（开发模式）
python main.pyw

# 打包成 exe（一键打包）
打包\build.bat

# 或手动打包
cd 打包
pyinstaller --noconfirm --clean video_tools.spec
```

### 项目结构

- `main.pyw` - 入口文件，处理路径并启动主窗体
- `src/core/app.py` - 主窗体类 `VideoTools`，组合各 Mixin
- `src/core/config.py` - 全局配置（输出目录、路径模板等）
- `src/core/overlay.py` - 页签内容区内嵌覆盖层
- `src/core/subprocess_util.py` - ffmpeg 子进程跟踪与退出清理
- `src/core/file_lock.py` - 跨平台文件独占锁（修复输出等共享写防多实例并发）
- `src/core/common_mixins.py` - 共用 Mixin：列表刷新/增删/拖拽排序、拖入过滤、批量任务收尾
- `src/services/repair.py` - 损坏流式录屏检测与修复 (RepairMixin)
- `src/tabs/segment.py` - 多段截取 (SegmentMixin)
- `src/tabs/crop.py` - 画幅裁剪 (CropMixin)
- `src/tabs/merge.py` - 视频合并 (MergeMixin)
- `src/tabs/doc.py` - 文档生成 (DocMixin)
- `src/tabs/weekly.py` - 录屏整理 (WeeklyMixin)
- `src/tabs/roi.py` - 画幅裁剪 ROI 框选（OpenCV）

### 关键配置

`src/core/config.py` 中定义了多个输出目录（无 `config.json` 时使用这些中性默认值，不写死开发者路径）：
- `TOOLBOX_OUTPUT_ROOT` - 基础输出目录（默认：用户主目录 `Videos/toolbox输出`）
- `DOC_TRANSFER_DOC_DIR` / `DOC_TRANSFER_MEDIA_DIR` - 文档转运目标路径（默认：用户主目录 `Documents/VideoToolbox/文库`）
- `WEEKLY_OUTPUT_ROOT` - 录屏整理根目录（默认：用户主目录 `Videos/toolbox录屏`）

### Linux 运行说明

Linux 下不要用 conda 自带的 Tk（官方构建未启用 Xft，中文字体会回退成丑陋的位图字体），推荐用系统 Python + venv：

```bash
# 前置：系统包（Ubuntu/Debian 一次性）
sudo apt-get install -y python3-tk python3-venv

# 建环境 + 装依赖（一次性）
cd "视频工具箱"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 运行
.venv/bin/python main.pyw
```

其他要点：

- 系统需安装 `ffmpeg`（含 libx264，重编码/1080p 扩展依赖）与 CJK 字体（如 `fonts-noto-cjk`；若已装霞鹜文楷会自动使用）。
- 本机个性化配置在 `config.json`（输出目录、窗口位置、文档转运路径）。该文件已被 `.gitignore` 忽略、不进版本库，各机器各自维护，互不影响。
- 字体自动适配：Windows 用微软雅黑/Consolas，其他平台用霞鹜文楷/DejaVu Sans Mono（见 `src/core/config.py` 的 `UI_FONT_FAMILY` / `MONO_FONT_FAMILY`）。
- 窗口默认几何：Windows 保持原坐标，其他平台默认 `420x460+100+100`，实际位置可在 `config.json` 的 `window.geometry` 覆盖。
- 打包：`打包/` 下的 `build.bat` / `video_tools.spec` 是 Windows 专用；Linux 直接以 `.venv` 运行即可，暂不打包。

### 已知注意事项

- 录屏整理的片段提取使用 `-t <片段时长>`，不依赖输出时间戳是否保留绝对值（旧写法是 `-to <绝对结束时间戳>`）。若出现片段边界/时长异常，改回旧写法即可，见 `src/tabs/weekly.py` 内注释。
- 批处理任务全局互斥：多段截取/画幅裁剪/视频合并/录屏整理/文档生成/文档转运同一时间只允许运行一个，避免底部日志互相覆盖；处理期间其他标签仍可拖入文件、调整输入（各线程启动时已快照输入）。
- 损坏检测进入"修复"阶段后，期间的新拖入会直接加入列表（跳过新一轮损坏检测），避免修复弹窗重叠。
- 支持同时打开多个实例：合并临时文件（`filelist_<pid>.txt`、`temp_merge_for_music_<pid>.mp4`）与录屏整理临时目录（`_tmp_weekly_<pid>`）按 PID 隔离；修复输出（`*_repaired.mp4`）用文件锁防并发写（见 `src/core/file_lock.py`）。

---

## C# Avalonia 版本

### 常用命令

```bash
# 进入目录
cd VideoToolbox-MFAAvalonia

# 构建项目
dotnet build -c Debug
dotnet build -c Release

# 运行
dotnet run

# 运行单个测试
dotnet test tests/VideoToolbox.SmokeTests -c Release --filter "FullyQualifiedName~TestName"

# 运行所有冒烟测试
.\run_ui_smoke_tests.ps1
# 或
dotnet test tests/VideoToolbox.SmokeTests -c Release
```

### 项目结构

采用 MVVM 模式 + 依赖注入：

```
VideoToolbox-MFAAvalonia/
├── App.axaml.cs              # DI 容器配置 (ConfigureServices)
├── Views/
│   ├── MainWindow.axaml      # 主窗口（左导航 + 右内容 + 底部日志）
│   └── Windows/              # 子窗口（ROI 选择器等）
├── ViewModels/
│   ├── MainWindowViewModel.cs           # 核心 ViewModel
│   ├── MainWindowViewModel.Segment.cs   # 多段截取
│   ├── MainWindowViewModel.Crop.cs      # 画幅裁剪
│   ├── MainWindowViewModel.Merge.cs     # 视频合并
│   ├── MainWindowViewModel.Doc.cs       # 文档生成
│   ├── MainWindowViewModel.Weekly.cs    # 录屏整理
│   └── MainWindowViewModel.Navigation.cs # 导航与工具方法
├── Services/
│   ├── AppPaths.cs           # 路径服务
│   ├── FileLogService.cs     # 日志服务
│   ├── ProcessService.cs     # 进程执行服务（ffmpeg）
│   └── UserConfigService.cs  # 用户配置管理
└── tests/VideoToolbox.SmokeTests/  # 冒烟测试
```

### 依赖注入配置

`App.axaml.cs` 中 `ConfigureServices` 方法注册了以下服务：
- `AppPaths` - 单例，管理应用路径
- `ILogService` / `FileLogService` - 日志服务
- `ProcessService` - ffmpeg 进程执行
- `UserConfigService` - 用户配置持久化
- `MainWindowViewModel` / `MainWindow` - 主窗体和视图模型

### 用户偏好

- 交流语言：中文
- 界面改完后**默认不做编译检查**（除非用户明确要求）
- 减少冗余说明文字，优先紧凑布局

---

## 五大功能模块

两个项目共享相同的五大功能：

| 功能 | Python 文件 | C# ViewModel 分部类 |
|------|-------------|---------------------|
| 多段截取 | `src/tabs/segment.py` | `MainWindowViewModel.Segment.cs` |
| 画幅裁剪 | `src/tabs/crop.py` | `MainWindowViewModel.Crop.cs` |
| 视频合并 | `src/tabs/merge.py` | `MainWindowViewModel.Merge.cs` |
| 文档生成 | `src/tabs/doc.py` | `MainWindowViewModel.Doc.cs` |
| 录屏整理 | `src/tabs/weekly.py` | `MainWindowViewModel.Weekly.cs` |

### 行为一致性要点

1. **拖拽输入**：支持文件拖拽到窗口自动导入
2. **跨标签传递**：视频列表可在不同功能标签间传递（模式由 `CROSS_TAB_TRANSFER_MODE` 控制）
3. **ffmpeg 命令构建**：参考 Python 版本的参数构建逻辑，C# 版本保持一致
4. **列表排序**：视频合并和录屏整理支持拖拽排序

---

## 重要约束

1. 不改动原 Python 项目文件（除非明确授权）
2. 不改变 ffmpeg 命令参数构建逻辑
3. C# 版本 UI 以 MAA/MFAAvalonia 为视觉参考
4. 提交前按需执行 `dotnet build -c Debug`，保持 0 error

---

## 关键文件

- `视频工具箱/打包/打包说明.md` - Python 版本打包说明
- `VideoToolbox-MFAAvalonia/NEXT_AI_HANDOFF.md` - 最新 AI 交接文档
- `VideoToolbox-MFAAvalonia/UI_TODO.md` - UI 同款化任务列表
- `VideoToolbox-MFAAvalonia/UI_REFACTOR_LOG.md` - UI 重构变更日志
