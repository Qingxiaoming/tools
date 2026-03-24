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
- `src/app.py` - 主窗体类 `VideoTools`，继承多个 Mixin
- `src/config.py` - 全局配置（输出目录、路径模板等）
- `src/segment.py` - 多段截取功能 (SegmentMixin)
- `src/crop.py` - 画幅裁剪功能 (CropMixin)
- `src/merge.py` - 视频合并功能 (MergeMixin)
- `src/doc.py` - 文档生成功能 (DocMixin)
- `src/weekly.py` - 录屏整理功能 (WeeklyMixin)
- `src/roi_selector.py` - ROI 区域选择器（OpenCV）

### 关键配置

`src/config.py` 中定义了多个输出目录：
- `TOOLBOX_OUTPUT_ROOT` - 基础输出目录（默认 `E:\toolbox输出`）
- `DOC_TRANSFER_DOC_DIR` / `DOC_TRANSFER_MEDIA_DIR` - 文档转运目标路径
- `WEEKLY_OUTPUT_ROOT` - 录屏整理根目录（默认 `I:\录屏`）

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
| 多段截取 | `src/segment.py` | `MainWindowViewModel.Segment.cs` |
| 画幅裁剪 | `src/crop.py` | `MainWindowViewModel.Crop.cs` |
| 视频合并 | `src/merge.py` | `MainWindowViewModel.Merge.cs` |
| 文档生成 | `src/doc.py` | `MainWindowViewModel.Doc.cs` |
| 录屏整理 | `src/weekly.py` | `MainWindowViewModel.Weekly.cs` |

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

- `视频工具箱/打包说明.md` - Python 版本打包说明
- `VideoToolbox-MFAAvalonia/NEXT_AI_HANDOFF.md` - 最新 AI 交接文档
- `VideoToolbox-MFAAvalonia/UI_TODO.md` - UI 同款化任务列表
- `VideoToolbox-MFAAvalonia/UI_REFACTOR_LOG.md` - UI 重构变更日志
