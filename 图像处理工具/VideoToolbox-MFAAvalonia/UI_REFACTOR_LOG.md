# UI Refactor Log

## 2026-02-16

### 本轮目标

- 执行 `UI-01`：建立并接入全局主题层（不改业务行为）。
- 执行 `UI-02`：主窗口改为“左导航 + 内容区 + 日志区”骨架。
- 执行 `UI-03`：5 个功能页细化为分区卡片布局。
- 执行 `UI-04`：增加忙碌态反馈与关键操作禁用。
- 执行 `UI-05`：日志面板自动滚动与可折叠。
- 执行 `UI-06`：主次按钮视觉层级与主题细节统一。
- 执行 `UI-07`：预留并接入深浅色主题切换入口。

### 变更内容

- 更新 `App.axaml`：
  - 在 `Application.Styles` 中新增 `StyleInclude`，加载 `avares://VideoToolbox/Styles/Theme.axaml`。
- 新增 `Styles/Theme.axaml`：
  - 建立基础设计 token（间距、字号、圆角、语义色）。
  - 增加基础控件样式（`Button`、`TextBox`、`ComboBox`、`CheckBox`、`ListBox`、`TextBlock`、`Window`）。
- 更新 `Views/MainWindow.axaml`：
  - 将主内容区包裹为卡片式容器。
  - `TabControl` 改为左侧页签导航（`TabStripPlacement="Left"`）。
  - 状态条与日志区改为独立容器，结构上形成“主内容 + 状态条 + 日志区”三段布局。
  - 多段截取、画幅裁剪、视频合并、文档生成、录屏整理 5 个页签均拆分为卡片分区（输入区/参数区/操作区）。
  - 关键操作按钮绑定 `CanOperate`（忙碌时禁用，空闲时可点）。
  - 状态条新增 `ProgressBar`（`IsBusy` 时显示不确定进度）。
  - 状态栏新增主题下拉（跟随系统/深色/浅色）。
  - 日志区新增“收起/展开日志”按钮。
  - 日志 ListBox 支持绑定显隐状态。
- 更新 `ViewModels/MainWindowViewModel.cs`：
  - 新增 `CanOperate => !IsBusy`。
  - `IsBusy` 属性变更时自动通知 `CanOperate`。
  - 新增 `IsLogPanelExpanded` 与 `ToggleLogPanelCommand`。
  - 新增 `ThemeMode`、`ThemeModeOptions`，切换时同步 `Application.RequestedThemeVariant`。
- 清理历史目录 `video-tools-avalonia` 的残留文件（该目录未被主项目引用）：
  - 删除 `video-tools-avalonia/Views/MainWindow.axaml.cs`
  - 删除 `video-tools-avalonia/REFACTOR_TEST_LOG.md`
- 更新 `Views/MainWindow.axaml.cs`：
  - 监听日志集合变化并自动滚动到最后一条（auto-scroll）。
- 更新 `Styles/Theme.axaml`：
  - 新增 `Button.primary` 样式（主按钮主色、悬停/按下反馈）。
  - 重构色板与视觉 token（Brand/Surface/Border/TextSecondary），提升层级对比。
  - 新增 `Border.card`、`Border.panel`、`TextBlock.caption` 样式。
  - 优化 `TabItem` 导航态（选中态、hover 态、圆角与内边距）。
- 修复功能回归与体验问题：
  - 补回合并/录屏页的清空、删除、上移、下移操作逻辑与 UI。
  - 补回裁剪/文档页清空列表按钮。
  - 拖拽导入按页签过滤文件类型；合并页支持单独拖入音频文件自动填充。
  - ROI 框选增加边界保护；短视频取帧失败时回退首帧提取。
- 本轮 UI 美化（不改业务逻辑）：
  - 主窗口新增标题头部卡片与副标题说明。
  - 主内容/状态栏/日志区统一卡片化与边框语言。
  - 关键“开始*”按钮统一使用主按钮视觉样式。
  - 状态栏维持主题切换、进度反馈与工具按钮布局一致性。
- 窗口与托盘行为调整：
  - 隐藏系统标题栏（无白色顶部栏），保留自定义头部区域用于拖动窗口。
  - 新增系统托盘菜单：显示主窗口 / 最小化到托盘 / 退出。
  - 最小化窗口时自动隐藏到托盘。
  - 点击关闭按钮时默认改为隐藏到托盘，真正退出通过托盘“退出”执行。
  - 新增托盘双击行为：双击托盘图标可在“显示主窗口/隐藏到托盘”之间切换。
  - 默认窗口尺寸调整为更小（760x620，最小 680x520）。
  - 默认窗口启动位置对齐原 Tk 工具习惯坐标（约 `+2532,+1050`）。
- 视觉微调：
  - 左侧页签标题字号下调并统一为标题字号（与“输入区/截取规则”等标题接近）。
  - 页签内边距由 `12,8` 调整为 `10,6`，降低视觉膨胀感。
  - 移除各页“输入区/截取规则/参数区/操作区/元信息”等分区标题文字，保留控件与卡片结构以提升紧凑度。
  - 多段截取的“输入视频路径（单个）”改为仅拖拽导入展示（紧凑文本显示，不支持手动输入）。
  - 托盘菜单新增“拖拽移动窗口”开关；默认关闭，按需开启后才允许拖拽标题区移动窗口。
  - 去除多段截取路径区“仅支持拖拽导入”文字说明，进一步收紧垂直空间。
  - 画幅裁剪路径输入改为“仅拖拽 + 紧凑列表显示”（移除可编辑多行输入框）。
  - 文档生成路径输入改为“仅拖拽 + 紧凑列表显示”（移除可编辑多行输入框）。
- 文档收口与交接：
  - 重写 `UI_TODO.md` 为当前状态版，移除过时 Sprint 内容。
  - 新增 `NEXT_AI_HANDOFF.md`，整理下一个 AI 的优化项、优先级与用户偏好。

### 影响范围

- 仅影响 UI 视觉层，不改 ViewModel/服务层/ffmpeg 参数构建逻辑。
- 清理了未被引用的历史文件，不影响 `VideoToolbox-MFAAvalonia` 构建。

### 验证

- `dotnet build -c Debug`：通过（0 error, 0 warning）。
- `ReadLints`（`App.axaml`、`Styles/Theme.axaml`）：无错误。
- 新增变更后再次验证：`dotnet build -c Debug` 通过（0 error, 0 warning）。
- 本轮涉及文件 `ReadLints` 结果均为无错误。

## 2026-02-16（回归与优化第二轮）

### 本轮目标

- 优先完成 `UI-10` 回归验证记录并落库到日志。
- 按交接优先级推进 `P1`：增加“紧凑/标准”两档 UI 密度。

### 变更内容

- 更新 `ViewModels/MainWindowViewModel.cs`：
  - 新增 `UiDensityMode`、`UiDensityModeOptions`（紧凑/标准）。
  - 新增密度派生参数：`SectionCardPadding`、`PageContentMargin`、`PageStackSpacing`、`CropListHeight`、`MergeListHeight`、`DocListHeight`、`WeeklyListHeight`。
  - 切换密度时触发上述派生属性刷新，不影响业务命令与 ffmpeg 参数语义。
- 更新 `Views/MainWindow.axaml`：
  - 五大页签的卡片内边距、页面间距改为绑定密度参数。
  - 裁剪/合并/文档/录屏列表高度改为密度联动。
  - 状态栏新增“密度”下拉，可随时切换 `紧凑/标准`。
- 更新 `UI_TODO.md`：
  - `UI-10` 状态调整为“已完成（代码链路回归）”。
  - 下一步建议改为“补充运行态回归记录 + 继续密度细化”。

### UI-10 回归验证记录（代码链路）

- `多段截取`：
  - 入口命令绑定：`RunSegmentCommand`。
  - 拖拽路径：`HandleDroppedFiles` 在页签 0 仅接收视频并写入 `SegmentVideoPath`。
  - 边界处理：空输入、时间格式错误、起止时间非法均有状态提示与日志。
- `画幅裁剪（含 ROI）`：
  - 入口命令绑定：`RunCropCommand`、`SelectCropRoiVisualCommand`。
  - 拖拽路径：页签 1 仅接收视频并进入 `CropVideoFiles/CropVideoPathsText` 同步链路。
  - 边界处理：ROI 解析失败、分辨率探测失败、短视频取帧失败回退首帧、ROI 越界钳制均存在。
- `视频合并（含排序与音频）`：
  - 入口命令绑定：`RunMergeCommand`，排序命令链 `MoveUp/MoveDown/Remove/Clear` 完整。
  - 拖拽路径：页签 2 支持“单音频文件直接填入”与“视频列表导入”双路径。
  - 边界处理：列表为空、音频模式与音频文件不匹配、倍速非法均有拦截提示。
- `文档生成与转运`：
  - 入口命令绑定：`RunDocGenerationCommand`、`RunDocTransferCommand`。
  - 拖拽路径：页签 3 仅接收视频并写入文档输入列表。
  - 边界处理：无输入文档、引用视频缺失、目标已存在、转运失败回滚均存在。
- `录屏整理（含排序）`：
  - 入口命令绑定：`RunWeeklyCommand`，排序命令链 `MoveUp/MoveDown/Remove/Clear` 完整。
  - 拖拽路径：页签 4 仅接收视频，支持覆盖/追加模式。
  - 边界处理：时长探测失败、空可用时间轴、分段处理失败均有日志与状态反馈。

### 影响范围

- 本轮仅涉及 `VideoToolbox-MFAAvalonia` 的 UI/交互层。
- 未修改原 Python 项目 `图像处理工具/视频工具箱`。
- 未调整 ffmpeg 业务逻辑与参数语义。

### 验证

- 已完成 `UI-10` 代码链路回归核对（命令绑定、拖拽分发、边界处理、状态反馈）。
- 按当前用户偏好，本轮未执行 `dotnet build`（改完先看效果）。

## 2026-02-16（UI 紧凑度细化第三轮）

### 本轮目标

- 持续推进 `P1`：紧凑/标准两档密度的可视化细化。
- 统一“仅拖拽导入”弱提示文案，减少页面认知切换。

### 变更内容

- 更新 `ViewModels/MainWindowViewModel.cs`：
  - 新增 `LogListMaxHeight`，并纳入 `UiDensityMode` 的联动刷新。
  - 日志区在 `紧凑/标准` 两档下使用不同最大高度，避免内容区被日志挤压。
- 更新 `Styles/Theme.axaml`：
  - 新增 `NavTabFontSize` 资源，左侧导航 `TabItem` 改为独立字号。
  - 调小 `TabItem` 内边距（`8,5`），提升导航区紧凑度。
- 更新 `Views/MainWindow.axaml`：
  - 统一五个页签的拖拽弱提示文案为 `TextBlock.caption` 风格（“拖拽导入（视频...）”）。
  - 日志 `ListBox` 新增 `MaxHeight="{Binding LogListMaxHeight}"` 与 `MinHeight="96"`，形成可控高度策略。

### 影响范围

- 仅涉及 UI 视觉表达与布局密度，不改业务处理流程。
- ffmpeg 参数构建、任务命令语义、原 Python 项目均未改动。

### 验证

- 按当前用户偏好，本轮未执行编译检查。
- 已对本轮改动文件执行 `ReadLints`，无错误。

## 2026-02-16（按用户要求回退密度功能）

### 本轮目标

- 删除“紧凑/标准”密度相关代码与 UI 入口。
- 保留自动化测试脚本，不回退测试工程。
- 清理 `UI_TODO.md` 中关于自选密度的计划描述。

### 变更内容

- 更新 `ViewModels/MainWindowViewModel.cs`：
  - 删除 `UiDensityMode`、`UiDensityModeOptions` 及其联动属性/回调。
  - 删除密度派生参数（卡片 padding、列表高度、日志高度等）。
- 更新 `Views/MainWindow.axaml`：
  - 删除状态栏“密度”下拉。
  - 将卡片 padding、页面间距、列表高度恢复为固定值（回到本次接手前形态）。
  - 撤销本轮新增的统一拖拽弱提示改动，恢复原文案样式。
  - 撤销日志区密度联动高度绑定。
- 更新 `Styles/Theme.axaml`：
  - 删除 `NavTabFontSize`，恢复 `TabItem` 原字号与内边距。
- 更新 `UI_TODO.md`：
  - 删除关于“自选密度/两档密度”的下一步计划。

### 影响范围

- 自动化回归脚本与测试工程保留（`run_ui_smoke_tests.ps1`、`tests/VideoToolbox.SmokeTests`）。
- 未修改原 Python 项目与 ffmpeg 业务语义。

### 验证

- 已对本轮变更文件执行 `ReadLints`，无错误。

## 2026-02-16（配置化与三栏布局）

### 本轮目标

- 文档改为“按需构建校验（提交前/用户要求时执行）”。
- 中间主区改为三栏结构（页签栏 + 功能栏 + 操作栏），并去除卡片边框。
- 将“主题/跨页覆盖模式”从界面移至 `config` 文件配置。
- 点击标题可打开 `config`，保存后自动重启程序并尽量保留当前输入状态。

### 变更内容

- 更新 `UI_TODO.md`：
  - `UI-09` 与 DoD 文案改为按需构建策略，避免每轮强制构建。
- 更新 `Styles/Theme.axaml`：
  - `Border.card` 取消边框（`BorderThickness=0`），保留卡片背景与圆角。
- 更新 `Views/MainWindow.axaml`：
  - 五个页签内部改为两列（功能区 + 操作区），配合左侧页签形成三栏布局。
  - 删除“从上到下第三个操作框”的垂直堆叠形态，操作集中到右侧操作栏。
  - 将“打开输出文件夹 / 下一步”统一放入右侧操作栏。
  - 状态栏移除“主题/跨页覆盖”编辑入口，仅保留状态与进度反馈。
  - 标题 `VideoToolbox` 增加可点击控件标识。
- 更新 `Services` 与 `ViewModels`：
  - 新增 `Services/UserConfig.cs`、`Services/UserConfigService.cs`，读写 `config.json`（位于程序目录）。
  - `MainWindowViewModel` 启动时加载 `ThemeMode` 与 `CrossTabTransferMode` 配置。
  - 新增 `OpenConfigFileCommand`，用于打开 `config.json`。
  - 新增配置文件变更监听触发点：保存后回到窗口会检测并请求重启。
- 更新 `App.axaml.cs`：
  - 注入 `UserConfigService`。
  - 支持 `--session` 启动参数，用于重启后恢复当前 UI 输入状态。
  - 配置保存后触发“重启并携带会话快照”机制，尽量保留已导入/已填写项。
- 更新 `Views/MainWindow.axaml.cs`：
  - 点击标题触发 `OpenConfigFileCommand`。
  - 窗口激活时检查配置文件是否更新，若更新则执行自动重启流程。
- 自动化相关保留：
  - `run_ui_smoke_tests.ps1` 与 `tests/VideoToolbox.SmokeTests` 保持可用。

### 影响范围

- 仅改动 Avalonia 工程 UI 与配置加载逻辑，不改原 Python 项目。
- ffmpeg 参数构建与业务处理流程未变更。

### 验证

- 按当前偏好未执行全量编译。
- 本轮改动文件 `ReadLints` 无错误。

## 2026-02-16（细调：去第三框 + 缩窄右栏）

### 本轮目标

- 删除从上到下第三个框（与标题旁状态显示重复）。
- 缩窄左数第三栏（右侧操作栏），给中间功能区更多宽度。

### 变更内容

- 更新 `Views/MainWindow.axaml`：
  - 主容器行定义由 `Auto,*,Auto,Auto` 调整为 `Auto,*,Auto`。
  - 删除中间下方独立状态框（原 `Grid.Row="2"` 的状态面板）。
  - 日志区上移为第三块（`Grid.Row="2"`）。
  - 五个页签内部右侧操作栏宽度从 `220` 统一改为 `180`。

### 影响范围

- 仅影响布局展示，不改业务命令与参数语义。

### 验证

- 按当前偏好未执行编译检查。
- 本轮改动文件 `ReadLints` 无错误。

## 2026-02-16（样式覆盖修正）

### 本轮目标

- 修正“纵向两块看起来无间距”的视觉问题。
- 确保三栏分隔线不被控件模板覆盖。

### 变更内容

- 更新 `Styles/Theme.axaml`：
  - `TabStrip` 分隔线样式改为模板级选择器：`TabControl /template/ TabStrip`，增强命中稳定性。
  - 新增 `Border.section` 样式（无边框、较深底色）用于中间功能块与右侧操作块，增强层次对比。
- 更新 `Views/MainWindow.axaml`：
  - 五个页签中主要内容块由 `card` 切换为 `section`，避免与外层同色导致“看起来贴在一起”。
  - 上下两块首块的下边距从 `10` 调整到 `12`，拉开垂直间距体感。

### 影响范围

- 仅样式层与布局视觉，不涉及业务逻辑。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

### 补充修复（分割线拖拽编译错误）

- 修复 `Views/MainWindow.axaml.cs` 中拖拽实现的编译问题：
  - `CapturePointer` 调用改为 `e.Pointer.Capture(...)`。
  - 增加 `using System;`，恢复 `Math.Clamp` 可用。
- 验证：
  - `dotnet build -c Release` 通过（0 error, 0 warning）。

### 补充修复（分割线拖拽不生效排查）

- 现象：
  - 左/右分割线拖拽后，部分场景宽度未发生可见变化。
- 原因：
  - 仅更新资源键值在某些控件链路下刷新不稳定，导致“事件触发但布局不重排”的体感。
- 处理：
  - 为五个页签布局 `Grid` 增加命名（`SegmentLayoutGrid` 等）并在窗口打开时缓存目标控件。
  - 拖拽时改为“资源 + 目标控件”双写：
    - 左侧：直接更新 `TabStrip` 的 `Width/MinWidth/MaxWidth`。
    - 右侧：直接更新五个页签 `Grid.ColumnDefinitions[3].Width`。
- 验证：
  - `dotnet build -c Release` 通过（0 error, 0 warning）。
  - `ReadLints` 无错误。

### 补充修复（左分割线不生效）

- 现象：
  - 右分割线可调，左分割线在部分运行态下无明显响应。
- 原因：
  - 左宽度资源键在主题资源层存在同名定义，窗口级更新可能被资源解析链路覆盖。
  - 个别时机 `TabStrip` 引用未命中，导致未直接写入控件宽度。
- 处理：
  - 移除主题层 `MainLeftTabWidth` 资源定义，统一由窗口资源提供。
  - 左拖拽宽度更新时同时写入：
    - `Window.Resources["MainLeftTabWidth"]`
    - `Application.Current.Resources["MainLeftTabWidth"]`
    - `TabStrip.Width/MinWidth/MaxWidth`（直接控件赋值）
  - 新增 `EnsureTabStrip()`，拖拽过程中兜底查找 `TabStrip`。
- 验证：
  - `dotnet build -c Release` 通过（0 error, 0 warning）。
  - `ReadLints` 无错误。

### 补充修复（左分割线改为直接调中间列）

- 现象：
  - 在部分模板渲染条件下，左分割线调 `TabStrip` 宽度不稳定。
- 处理：
  - 左分割线机制重写为：直接调整页签内容 `Grid` 的中间列宽（`ColumnDefinitions[1]`）。
  - `MainMiddleColumnWidth` 改回像素宽（默认 `400`），拖拽实时写入所有页签同位列。
  - 右分割线继续调整右侧列宽，形成“左线调中间区 / 右线调操作区”对称模型。
- 结果：
  - 左右两根线都在同一层布局对象上生效，拖动响应一致性更高。
- 验证：
  - `dotnet build -c Release` 通过（0 error, 0 warning）。
  - `ReadLints` 无错误。

### 补充回调（左分割线语义修正）

- 用户反馈“抓左边动右边”，说明左手柄语义与预期不一致。
- 调整：
  - 左分割线恢复为“只调左页签栏宽度”。
  - 右分割线保持“只调右侧操作区宽度”。
  - 中间列恢复自适应（`*`），避免左拖动被解释为右侧联动。
- 验证：
  - `dotnet build -c Release` 通过（0 error, 0 warning）。
  - `ReadLints` 无错误。

### 补充修复（右分割线由全局联动改为当前页签生效）

- 现象：
  - 调整当前页签右分割线时，其他页签宽度也被一起改动，造成“改下面会上来”的体感。
- 原因：
  - 右分割线实现为遍历全部页签 `Grid` 统一写列宽（全局联动）。
- 处理：
  - 拖拽按下时定位当前手柄所属 `Grid`（当前页签布局）。
  - 拖拽移动时仅更新该 `Grid` 的右列宽，不再全量遍历更新。
  - 保留资源键更新用于默认值同步，但不再强制覆盖其它页签当前布局。
- 验证：
  - `dotnet build -c Release` 通过（0 error, 0 warning）。
  - `ReadLints` 无错误。

### 补充重构（分割线逻辑收敛为“中间/右侧两宽度”）

- 背景：
  - 用户持续反馈“改一个所有东西都在变”，期望两根线只对应中间/右侧两块宽度。
- 重构：
  - 左分割线：只调整当前页签中间列宽（`ColumnDefinitions[1]`）。
  - 右分割线：只调整当前页签右侧列宽（`ColumnDefinitions[3]`）。
  - 取消左分割线对页签栏模板宽度的控制路径，避免模板层带来的联动与不确定性。
- 验证：
  - `dotnet build -c Release` 通过（0 error, 0 warning）。
  - `ReadLints` 无错误。

## 2026-02-16（可拖双分割线：左栏/右栏宽度实时调节）

### 本轮目标

- 支持通过拖拽两根竖向分割线实时调整布局宽度，避免反复手改固定值。

### 变更内容

- 更新 `Views/MainWindow.axaml`：
  - 新增窗口级可调资源：
    - `MainLeftTabWidth`（页签栏宽度，Double）
    - `MainMiddleColumnWidth`（中间区宽度，改为 `*` 自适应）
    - `MainRightColumnWidth`（右侧操作区宽度，像素）
  - 五个页签内容区的两根分隔线改为可拖拽手柄（左/右），绑定拖拽事件：
    - 左手柄：调节页签栏宽度
    - 右手柄：调节右侧操作区宽度
  - 列宽资源引用改为 `DynamicResource`，拖拽时实时生效。
- 更新 `Styles/Theme.axaml`：
  - `TabStrip` 宽度样式从 `StaticResource` 改为 `DynamicResource`，支持运行时更新。
  - 新增 `Border.resize-splitter` 样式（可见手柄 + `SizeWestEast` 光标 + hover 高亮）。
- 更新 `Views/MainWindow.axaml.cs`：
  - 新增左右分割线拖拽处理逻辑（按下/移动/释放）与宽度边界限制：
    - 左栏：`140 ~ 280`
    - 右栏：`96 ~ 260`
  - 拖拽过程中实时写回窗口资源，界面即时重排。

### 影响范围

- 仅 UI 布局交互增强，不改业务流程与命令语义。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

## 2026-02-16（根因修正：右栏固定宽改为自适应）

### 本轮目标

- 解决“右栏看起来始终偏宽”的根因，而非继续微调内边距。

### 变更内容

- 更新 `Views/MainWindow.axaml`：
  - `MainRightColumnWidth` 从固定值 `132` 调整为 `Auto`。
  - 右侧操作栏宽度改为按页签内容自适应，不再强制占固定列宽。

### 影响范围

- 仅布局宽度策略调整，不改业务逻辑与命令行为。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

## 2026-02-16（右栏再收窄：132 + 右侧内边距下调）

### 本轮目标

- 针对“右栏仍显宽”的反馈，进一步压缩右栏视觉占比。

### 变更内容

- 更新 `Views/MainWindow.axaml`：
  - `MainRightColumnWidth` 从 `150` 调整为 `132`。
  - 主内容卡片 `Padding` 从 `8,8,4,8` 调整为 `8,8,2,8`，继续缩短最右侧外留白。
  - 五个页签右侧操作区 `Border` 的 `Padding` 从 `6` 调整为 `4`。
- 更新 `Styles/Theme.axaml`：
  - 右栏专用按钮样式 `StackPanel.action-panel > Button` 的 `Padding` 从 `10,6` 调整为 `8,6`。

### 影响范围

- 仅布局/样式微调，不改业务逻辑与命令行为。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

## 2026-02-16（右侧贴边微调 + 调试背景回退）

### 本轮目标

- 继续缩短右侧外留白，验证“主卡片右内边距收敛”效果。
- 移除用于排查布局的高亮背景/描边，恢复正常主题观感。

### 变更内容

- 更新 `Views/MainWindow.axaml`：
  - 主内容卡片 `Grid.Row="1"` 的 `Padding` 从 `8` 调整为 `8,8,4,8`。
  - 五个页签右侧操作区 `Border` 移除 `action-area` 类，恢复普通 `section`。
- 更新 `Styles/Theme.axaml`：
  - `Border.card` 与 `Border.section` 从调试色/描边回退为常规 `SurfaceCardBrush` + `BorderThickness=0`。
  - 删除调试用 `Border.action-area` 样式。

### 影响范围

- 仅视觉布局微调与调试样式回退，不改业务逻辑。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

## 2026-02-16（统一边距基线：左中右对称性）

### 本轮目标

- 统一左栏页签、中间内容区、右侧操作区的横向留白规则，降低“右侧过长空白”。

### 变更内容

- 更新 `Styles/Theme.axaml`：
  - `TabStrip`（含高优先级选择器）右侧 `Margin/Padding` 从 `10/8` 统一收敛到 `6/6`。
- 更新 `Views/MainWindow.axaml`：
  - 五个页签内容 `Grid` 的外边距从 `Margin="8"` 调整为 `Margin="8,8,0,8"`，消除右侧重复留白层。
  - 五个页签右侧 `action-area` 的内边距从 `Padding="4"` 调整为 `Padding="6"`，与整体节奏更一致。

### 影响范围

- 仅布局间距与视觉对称性细调，不改业务逻辑和命令行为。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

### 补充回调（按钮铺满回退）

- 根据用户反馈，撤回右侧操作按钮“铺满宽度”样式：
  - 移除 `StackPanel.action-panel > Button` 自定义样式。
  - 各页签右侧操作区 `StackPanel` 去除 `action-panel` 类。
- 保留当前三栏宽度参数，不改业务逻辑。

### 补充修复（右栏按钮靠右且保留内容宽）

- 用户反馈：按钮不应铺满，但应更贴近右边界，避免“左侧间隔小、右侧间隔大”的不对称感。
- 处理：
  - 新增 `StackPanel.action-panel` 与其子按钮样式：
    - 按钮保持内容宽（不拉伸）
    - 按钮组整体右对齐
    - 收紧按钮右侧留白（`Margin` 右边为 `0`）与内边距，减少文字被过早压缩。
  - 右侧操作区继续使用 `Classes="action-panel"`。

### 补充回调（撤销按钮靠右 + 右栏宽度回调）

- 根据用户反馈撤销“按钮靠右”改动（恢复默认布局，不强制右对齐）。
- 为避免“右侧看起来空但文字仍被压缩”，右栏宽度从 `120` 回调至 `140`（仍比早期版本窄）。
- 说明：右栏没有隐藏元素，空白主要来自固定列宽与按钮文本宽度/内边距之间的平衡。

## 2026-02-16（对称性修正：右栏空间回收）

### 本轮目标

- 依据“固定列宽 + 全局按钮内外边距叠加”的成因，缓解右栏空白与文本挤压并存的问题。
- 不启用按钮铺满，不做按钮靠右，维持原有交互习惯。

### 变更内容

- 更新 `Views/MainWindow.axaml`：
  - `MainRightColumnWidth` 从 `140` 调整为 `150`，给右栏按钮文本留出更稳定的内容宽度。
  - 五个页签右侧操作区 `Border` 的 `Padding` 从 `6` 收紧到 `4`，减少“被容器吃掉”的可用宽度。
  - 五个页签右侧操作区 `StackPanel` 增加 `Classes="action-panel"` 以承载右栏专用按钮样式。
- 更新 `Styles/Theme.axaml`：
  - 新增 `StackPanel.action-panel > Button` 样式，收紧右栏按钮 `Margin/Padding`（`2` / `10,6`）。
  - 保持按钮为内容宽，不做 `Stretch` 与右对齐，避免偏离用户偏好。

### 影响范围

- 仅布局与样式细调，不改业务逻辑、命令绑定与 ffmpeg 参数语义。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

## 2026-02-16（对称性修正：右栏视觉空白）

### 本轮目标

- 修正“右侧看起来偏宽、不对称”的视觉问题。

### 变更内容

- 更新 `Views/MainWindow.axaml`：
  - `MainRightColumnWidth` 从 `130` 调整为 `120`，进一步压缩右栏。
  - 五个页签右侧操作区 `StackPanel` 增加 `Classes="action-panel"`。
- 更新 `Styles/Theme.axaml`：
  - 新增 `StackPanel.action-panel > Button` 样式：
    - `HorizontalAlignment=Stretch`（按钮铺满右栏可用宽度）
    - 收紧按钮 `Margin/Padding`，减少空白损耗。

### 影响范围

- 仅右栏视觉与排布优化，不改业务逻辑。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

## 2026-02-16（三栏固定宽度：近似 2:5:2）

### 本轮目标

- 左中右三栏改为固定宽度。
- 相对当前多段截取界面：左栏更宽、右栏更窄、中间保持主区域。

### 变更内容

- 更新 `Styles/Theme.axaml`：
  - 新增 `MainLeftTabWidth=160`。
  - `TabStrip`（含模板高优先级选择器）统一设置 `Width/MinWidth/MaxWidth=160`，确保左栏固定且更宽。
- 更新 `Views/MainWindow.axaml`：
  - 新增主区固定列宽资源：
    - `MainMiddleColumnWidth=400`
    - `MainRightColumnWidth=160`
  - 五个页签内部三栏统一改为固定列：
    - 中间功能区 `400`
    - 分隔线 `1`
    - 右侧操作区 `160`

### 影响范围

- 仅布局宽度参数调整，不改业务逻辑。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

### 补充修复（启动崩溃）

- 现象：
  - `dotnet watch` / `dotnet run` 出现 `-532462766` 退出码。
  - 根因是 `MainWindow.axaml` 中将 `ColumnDefinitions` 资源定义为 `String/Double`，运行时无法转换到 `ColumnDefinitions/GridLength`。
- 处理：
  - 将三栏宽度资源改为 `GridLength` 类型（`SegmentRightColumnWidth` 等）。
  - 保留“集中配置 + 分页不同宽度”的方案，不回退为硬编码。
- 结果：
  - 重新 `dotnet run` 后不再抛 `InvalidCastException`，程序可正常启动。

### 补充修复（页签分隔线可见性）

- 现象：
  - 部分主题/模板渲染下，`TabStrip` 的模板级边线仍可能视觉不可见。
- 处理：
  - 保留模板级分隔线样式。
  - 在主区外层增加“单点兜底分割线”（仅一处，不在每个页签硬写），保证页签与中间区分隔始终可见。
- 说明：
  - 优先模板级方案不变；兜底线仅用于规避模板吞样式的稳定性问题。

### 补充修复（分隔线连续性 + 右栏再收窄）

- 问题：
  - 页签与中间分隔线在部分场景下出现断续显示。
- 调整：
  - 移除主区外层的单点兜底线容器，改为在每个页签内容网格内统一使用四列结构：
    - 左分隔线 / 中间功能区 / 右分隔线 / 右侧操作区。
  - 两根线均为同一层级绘制，避免被 `TabControl` 内容层覆盖导致断裂。
  - 右侧操作区宽度从 `160` 收窄到 `145`，给分隔线与中间区留出更多空间。
- 结果：
  - 中间两根线稳定可见，且右栏更紧凑。

## 2026-02-16（宽度微调：页签更宽、操作区更窄）

### 本轮目标

- 在现有三栏结构不变前提下，继续提升左栏可读性并压缩右栏占比。

### 变更内容

- 更新 `Styles/Theme.axaml`：
  - `MainLeftTabWidth` 从 `160` 调整为 `175`（页签更宽）。
- 更新 `Views/MainWindow.axaml`：
  - `MainRightColumnWidth` 从 `145` 调整为 `130`（操作区更窄）。

### 影响范围

- 仅宽度参数微调，不改业务逻辑与交互流程。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

## 2026-02-16（三栏宽度集中化，支持分页差异）

### 本轮目标

- 保持三栏宽度“可集中修改”，同时允许不同页签使用不同宽度。

### 变更内容

- 更新 `Views/MainWindow.axaml`：
  - 在 `Window.Resources` 中新增 5 组列定义资源：`SegmentColumns`、`CropColumns`、`MergeColumns`、`DocColumns`、`WeeklyColumns`。
  - 五个页签的三栏 `Grid` 改为引用对应资源（`ColumnDefinitions="{StaticResource ...}"`）。
  - 现在可以“一处集中管理 + 分页不同宽度”。

### 影响范围

- 仅布局参数管理方式调整，不改业务逻辑。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

## 2026-02-16（按需求重修：两根线 + 统一10px间距）

### 本轮目标

- 不加深 `section` 背景，仅保留分块。
- 中间三部分保持两根分割线（页签↔中间、以及中间↔右栏）。
- 上下三个主块与页签内上下分块间距统一为 `10px`。

### 变更内容

- 更新 `Styles/Theme.axaml`：
  - `Border.section` 背景恢复为 `SurfaceCardBrush`（不再加深）。
  - `TabStrip` 分割线透明度增强为 `#99FFFFFF`，提高“第一根线”可见性。
  - 为 `TabStrip` 分割线补充更高优先级模板选择器（含 `#PART_TabStrip` 与 `TabControl:left`），规避默认模板样式覆盖导致的“分割线被吞掉”。
- 更新 `Views/MainWindow.axaml`：
  - 外层“主区卡片”补 `Margin="0,0,0,10"`，确保标题 / 主区 / 日志三块之间为 `10px` 间距。
  - 去除页签内首块额外下边距，统一由 `StackPanel Spacing="10"` 控制上下块间距。
  - 中间与右栏之间的竖线统一增强为 `#99FFFFFF`，确保“第二根线”可见。

### 影响范围

- 仅视觉样式与间距调整，不改业务逻辑。
- 样式策略约定：优先用模板级选择器修复渲染层覆盖问题，非必要不做页面硬编码分割线。

### 验证

- 本轮改动文件 `ReadLints` 无错误。

## 2026-02-16（细调：三栏分隔线与垂直间距）

### 本轮目标

- 恢复中间功能区上下两块卡片的可感知间距。
- 为三栏结构增加白色半透明分隔线，强化分区边界。

### 变更内容

- 更新 `Views/MainWindow.axaml`：
  - 多段截取/画幅裁剪/视频合并/文档生成页中，首块卡片补 `Margin="0,0,0,10"`，恢复上下间距。
  - 五个页签内部两列布局改为三列（`功能区, 分隔线, 操作区`），中间新增 `#66FFFFFF` 半透明竖线。
- 更新 `Styles/Theme.axaml`：
  - 为 `TabStrip` 增加右侧半透明边线（`BorderThickness="0,0,1,0"`），形成“页签栏 ↔ 中间功能区”分隔。

### 影响范围

- 仅视觉布局微调，不改命令、参数与业务逻辑。

### 验证

- 按当前偏好未执行编译检查。
- 本轮改动文件 `ReadLints` 无错误。
