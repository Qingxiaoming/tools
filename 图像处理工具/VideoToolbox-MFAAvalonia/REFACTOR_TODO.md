# VideoToolbox 重构 TODO（基于 MFAAvalonia 结构思路）

## 已完成

- [x] 在 `命令行小工具~` 同级新建独立项目 `VideoToolbox-MFAAvalonia`（未修改原 `视频工具箱`）。
- [x] 参考 MFAAvalonia 的主结构完成基础重构：
  - [x] `App` 中使用依赖注入（`ServiceCollection`）创建 ViewModel/View。
  - [x] 将业务逻辑从视图层迁移到 `MainWindowViewModel`。
  - [x] 建立统一服务层：`AppPaths`、`FileLogService`、`ProcessService`。
- [x] 功能页签迁移（与原功能对应）：
  - [x] 多段截取
  - [x] 画幅裁剪
  - [x] 视频合并（包含音频模式和倍速）
  - [x] 文档生成
  - [x] 录屏整理（24h 分段 + 60x 视频流程）
- [x] 跨页签传递机制（右箭头）：
  - [x] 多段截取 -> 画幅裁剪
  - [x] 画幅裁剪 -> 视频合并 + 文档生成
  - [x] 视频合并 -> 文档生成
  - [x] 文档生成 -> 触发转运
- [x] 输出目录快捷打开按钮。
- [x] 日志系统落盘到 `logs/toolbox.log`，并在 UI 列表实时显示。
- [x] 构建验证：`dotnet build -c Debug` 通过（0 Error）。

## 本轮自检记录

- [x] 依赖还原：`dotnet restore` 成功。
- [x] 编译检查：`dotnet build -c Debug` 成功。
- [x] 代码诊断：IDE Lint 无错误。
- [x] 关键流程异常捕获已接入日志（ffmpeg 执行、转运回滚、跨页传递）。

## 后续优化（可选）

- [x] 将 ROI 从“文本输入 x,y,w,h”升级为可视化框选窗口（Avalonia 交互画布）。
- [x] 将超大 `MainWindowViewModel` 拆分为多文件模块：
  - [x] `MainWindowViewModel.Navigation.cs`
  - [x] `MainWindowViewModel.Segment.cs`
  - [x] `MainWindowViewModel.Crop.cs`
  - [x] `MainWindowViewModel.Merge.cs`
  - [x] `MainWindowViewModel.Doc.cs`
  - [x] `MainWindowViewModel.Weekly.cs`
- [ ] 为关键规则增加自动化测试（时间解析、输出重名策略、文档转运事务回滚）。
