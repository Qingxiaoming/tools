using Avalonia.Threading;
using Avalonia;
using Avalonia.Styling;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using VideoToolbox.Services;

namespace VideoToolbox.ViewModels;

public partial class MainWindowViewModel : ViewModelBase
{
    private const int TabCount = 5;
    private readonly AppPaths _paths;
    private readonly ILogService _log;
    private readonly ProcessService _process;
    private readonly UserConfigService _userConfig;
    private readonly HashSet<string> _docGeneratedMdNames = [];
    private readonly string[] _videoNatureList = ["突袭", "无解", "待压", "剧情", "他人记录", "剿灭", "沙盘", "普通"];
    private readonly string[] _tabStatusTexts = ["待机中", "待机中", "待机中", "待机中", "待机中"];
    private readonly bool[] _tabBusyStates = new bool[TabCount];
    private readonly string[] _tabLastLogLines = ["", "", "", "", ""];
    private bool _watchConfigChanges;
    private DateTime _configBaselineWriteUtc;
    private bool _anyBusy;
    public event Action? RequestRestartForConfigChange;

    public MainWindowViewModel(AppPaths paths, ILogService log, ProcessService process, UserConfigService userConfig)
    {
        _paths = paths;
        _log = log;
        _process = process;
        _userConfig = userConfig;
        _paths.EnsureDirectories();

        _log.Info("VideoToolbox-MFAAvalonia 启动");
        ApplyUserConfig(_userConfig.LoadOrCreate());
    }

    [ObservableProperty] private int _selectedTabIndex;
    [ObservableProperty] private string _statusText = "待机中";
    [ObservableProperty] private string _currentLastLogLine = "";

    public bool IsBusy => _anyBusy;
    public bool CanOperate => !_anyBusy;

    [ObservableProperty] private string _segmentVideoPath = string.Empty;
    [ObservableProperty] private string _segmentBatchText =
        "00:00:01 01:00:02 test1\nclipA 00:00:03 00:00:08\n00:00:11 my clip 00:00:20";
    [ObservableProperty] private bool _segmentPreciseCrop;

    [ObservableProperty] private string _cropVideoPathsText = string.Empty;
    [ObservableProperty] private int _cropSelectedIndex = -1;
    [ObservableProperty] private string _cropRoiText = string.Empty;

    [ObservableProperty] private string _mergeVideoPathsText = string.Empty;
    [ObservableProperty] private int _mergeSelectedIndex = -1;
    [ObservableProperty] private string _mergeAudioPath = string.Empty;
    [ObservableProperty] private string _mergeAudioMode = "保持原音频";
    [ObservableProperty] private string _mergeOutputName = "合并视频";
    [ObservableProperty] private string _mergeSpeed = "1.0";

    [ObservableProperty] private string _docVideoPathsText = string.Empty;
    [ObservableProperty] private int _docSelectedIndex = -1;
    [ObservableProperty] private string _docActivity = string.Empty;
    [ObservableProperty] private string _docBv = string.Empty;

    [ObservableProperty] private string _weeklyVideoPathsText = string.Empty;
    [ObservableProperty] private int _weeklySelectedIndex = -1;
    [ObservableProperty] private bool _overwriteCrossTabTransfer = true;
    [ObservableProperty] private string _themeMode = "跟随系统";

    public IReadOnlyList<string> AudioModeOptions { get; } = ["保持原音频", "替换音频", "叠加音频"];
    public IReadOnlyList<string> SpeedOptions { get; } = ["1.0", "0.5", "0.25", "2.0", "到音乐放完"];
    public IReadOnlyList<string> ThemeModeOptions { get; } = ["跟随系统", "深色", "浅色"];
    public ObservableCollection<string> CropVideoFiles { get; } = [];
    public ObservableCollection<string> MergeVideoFiles { get; } = [];
    public ObservableCollection<string> DocVideoFiles { get; } = [];
    public ObservableCollection<string> WeeklyVideoFiles { get; } = [];

    private bool _syncingCropPaths;
    private bool _syncingMergePaths;
    private bool _syncingDocPaths;
    private bool _syncingWeeklyPaths;

    private List<string> SegmentLastOutputs { get; set; } = [];
    private List<string> CropLastOutputs { get; set; } = [];

    partial void OnStatusTextChanged(string value)
    {
        var idx = Math.Clamp(SelectedTabIndex, 0, TabCount - 1);
        _tabStatusTexts[idx] = value;
    }

    partial void OnSelectedTabIndexChanged(int value)
    {
        var idx = Math.Clamp(value, 0, TabCount - 1);
        StatusText = _tabStatusTexts[idx];
        CurrentLastLogLine = _tabLastLogLines[idx];
    }

    private void SetTabBusy(int tab, bool busy)
    {
        _tabBusyStates[tab] = busy;
        var newBusy = _tabBusyStates.Any(b => b);
        if (_anyBusy != newBusy)
        {
            _anyBusy = newBusy;
            OnPropertyChanged(nameof(IsBusy));
            OnPropertyChanged(nameof(CanOperate));
        }
    }

    private void SetTabStatus(int tab, string text)
    {
        _tabStatusTexts[tab] = text;
        if (tab == SelectedTabIndex)
        {
            StatusText = text;
        }
    }

    private void SetTabLastLog(int tab, string text)
    {
        _tabLastLogLines[tab] = text;
        if (tab == SelectedTabIndex)
        {
            CurrentLastLogLine = text;
        }
    }

    private Action<string> CreateTabLogCallback(int tab)
    {
        return msg =>
        {
            _log.Info(msg);
            Dispatcher.UIThread.Post(() => SetTabLastLog(tab, msg));
        };
    }

    private void LogToTab(int tab, string message)
    {
        _log.Info(message);
        SetTabLastLog(tab, message);
    }

    [RelayCommand]
    private void OpenConfigFile()
    {
        try
        {
            _userConfig.OpenInDefaultEditor();
            _configBaselineWriteUtc = _userConfig.GetLastWriteUtc();
            _watchConfigChanges = true;
            StatusText = "已打开 config.json，保存后将自动重启并保留当前输入";
        }
        catch (Exception ex)
        {
            _log.Error("打开配置文件失败", ex);
            StatusText = $"打开配置文件失败: {ex.Message}";
        }
    }

    partial void OnThemeModeChanged(string value)
    {
        if (Application.Current is null)
        {
            return;
        }

        Application.Current.RequestedThemeVariant = value switch
        {
            "深色" => ThemeVariant.Dark,
            "浅色" => ThemeVariant.Light,
            _ => ThemeVariant.Default
        };
    }

    public void CheckConfigChangeAndRequestRestart()
    {
        if (!_watchConfigChanges)
        {
            return;
        }

        var lastWrite = _userConfig.GetLastWriteUtc();
        if (lastWrite <= _configBaselineWriteUtc)
        {
            return;
        }

        _watchConfigChanges = false;
        StatusText = "检测到 config 已保存，正在重启应用...";
        RequestRestartForConfigChange?.Invoke();
    }

    public UiSessionSnapshot CaptureSessionSnapshot()
    {
        return new UiSessionSnapshot
        {
            SelectedTabIndex = SelectedTabIndex,
            SegmentVideoPath = SegmentVideoPath,
            SegmentBatchText = SegmentBatchText,
            SegmentPreciseCrop = SegmentPreciseCrop,
            CropVideoPathsText = CropVideoPathsText,
            CropSelectedIndex = CropSelectedIndex,
            CropRoiText = CropRoiText,
            MergeVideoPathsText = MergeVideoPathsText,
            MergeSelectedIndex = MergeSelectedIndex,
            MergeAudioPath = MergeAudioPath,
            MergeAudioMode = MergeAudioMode,
            MergeOutputName = MergeOutputName,
            MergeSpeed = MergeSpeed,
            DocVideoPathsText = DocVideoPathsText,
            DocSelectedIndex = DocSelectedIndex,
            DocActivity = DocActivity,
            DocBv = DocBv,
            WeeklyVideoPathsText = WeeklyVideoPathsText,
            WeeklySelectedIndex = WeeklySelectedIndex
        };
    }

    public void RestoreSessionSnapshot(UiSessionSnapshot? snapshot)
    {
        if (snapshot is null)
        {
            return;
        }

        SegmentVideoPath = snapshot.SegmentVideoPath;
        SegmentBatchText = string.IsNullOrWhiteSpace(snapshot.SegmentBatchText) ? SegmentBatchText : snapshot.SegmentBatchText;
        SegmentPreciseCrop = snapshot.SegmentPreciseCrop;

        CropVideoPathsText = snapshot.CropVideoPathsText;
        CropSelectedIndex = snapshot.CropSelectedIndex;
        CropRoiText = snapshot.CropRoiText;

        MergeVideoPathsText = snapshot.MergeVideoPathsText;
        MergeSelectedIndex = snapshot.MergeSelectedIndex;
        MergeAudioPath = snapshot.MergeAudioPath;
        MergeAudioMode = snapshot.MergeAudioMode;
        MergeOutputName = snapshot.MergeOutputName;
        MergeSpeed = snapshot.MergeSpeed;

        DocVideoPathsText = snapshot.DocVideoPathsText;
        DocSelectedIndex = snapshot.DocSelectedIndex;
        DocActivity = snapshot.DocActivity;
        DocBv = snapshot.DocBv;

        WeeklyVideoPathsText = snapshot.WeeklyVideoPathsText;
        WeeklySelectedIndex = snapshot.WeeklySelectedIndex;
        SelectedTabIndex = snapshot.SelectedTabIndex;

        StatusText = "已恢复重启前输入状态";
    }

    private void ApplyUserConfig(UserConfig config)
    {
        ThemeMode = NormalizeThemeMode(config.ThemeMode);
        OverwriteCrossTabTransfer = string.Equals(config.CrossTabTransferMode, "append", StringComparison.OrdinalIgnoreCase)
            ? false
            : true;
    }

    private static string NormalizeThemeMode(string? theme)
    {
        return theme switch
        {
            "深色" => "深色",
            "浅色" => "浅色",
            _ => "跟随系统"
        };
    }

    private static string BuildAtempoChain(double speed)
    {
        if (speed <= 0)
        {
            return "atempo=1.0";
        }

        var chain = new List<double>();
        var remain = speed;
        while (remain > 2.0)
        {
            chain.Add(2.0);
            remain /= 2.0;
        }

        while (remain < 0.5)
        {
            chain.Add(0.5);
            remain /= 0.5;
        }

        chain.Add(remain);
        return string.Join(",", chain.Select(x => $"atempo={x.ToString("0.########", CultureInfo.InvariantCulture)}"));
    }

    private static double? ToSeconds(string t)
    {
        try
        {
            if (t.Length == 6 && t.All(char.IsDigit))
            {
                t = $"{t[..2]}:{t[2..4]}:{t[4..6]}";
            }

            t = t.Replace('：', ':');
            var ms = 0.0;
            var hhmmss = t;
            if (t.Contains('.'))
            {
                var parts = t.Split('.', 2);
                hhmmss = parts[0];
                ms = double.Parse("0." + parts[1], CultureInfo.InvariantCulture);
            }

            var segs = hhmmss.Split(':');
            if (segs.Length != 3)
            {
                return null;
            }

            var h = int.Parse(segs[0], CultureInfo.InvariantCulture);
            var m = int.Parse(segs[1], CultureInfo.InvariantCulture);
            var s = int.Parse(segs[2], CultureInfo.InvariantCulture);
            if (m is < 0 or >= 60 || s is < 0 or >= 60)
            {
                return null;
            }

            return h * 3600 + m * 60 + s + ms;
        }
        catch
        {
            return null;
        }
    }


    private static List<string> ParsePathLines(string text)
    {
        return text.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .Select(x => x.Trim().Trim('"'))
            .Where(x => !string.IsNullOrWhiteSpace(x))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static string ComposePathText(IEnumerable<string> newLines, string? appendFrom)
    {
        var all = new List<string>();
        if (!string.IsNullOrWhiteSpace(appendFrom))
        {
            all.AddRange(ParsePathLines(appendFrom));
        }

        all.AddRange(newLines);
        return string.Join(Environment.NewLine, all.Distinct(StringComparer.OrdinalIgnoreCase));
    }

    partial void OnMergeVideoPathsTextChanged(string value)
    {
        if (_syncingMergePaths)
        {
            return;
        }

        var lines = ParsePathLines(value);
        MergeVideoFiles.Clear();
        foreach (var line in lines)
        {
            MergeVideoFiles.Add(line);
        }

        if (MergeSelectedIndex >= MergeVideoFiles.Count)
        {
            MergeSelectedIndex = MergeVideoFiles.Count - 1;
        }
    }

    partial void OnCropVideoPathsTextChanged(string value)
    {
        if (_syncingCropPaths)
        {
            return;
        }

        var lines = ParsePathLines(value);
        CropVideoFiles.Clear();
        foreach (var line in lines)
        {
            CropVideoFiles.Add(line);
        }

        if (CropSelectedIndex >= CropVideoFiles.Count)
        {
            CropSelectedIndex = CropVideoFiles.Count - 1;
        }
    }

    partial void OnWeeklyVideoPathsTextChanged(string value)
    {
        if (_syncingWeeklyPaths)
        {
            return;
        }

        var lines = ParsePathLines(value);
        WeeklyVideoFiles.Clear();
        foreach (var line in lines)
        {
            WeeklyVideoFiles.Add(line);
        }

        if (WeeklySelectedIndex >= WeeklyVideoFiles.Count)
        {
            WeeklySelectedIndex = WeeklyVideoFiles.Count - 1;
        }
    }

    partial void OnDocVideoPathsTextChanged(string value)
    {
        if (_syncingDocPaths)
        {
            return;
        }

        var lines = ParsePathLines(value);
        DocVideoFiles.Clear();
        foreach (var line in lines)
        {
            DocVideoFiles.Add(line);
        }

        if (DocSelectedIndex >= DocVideoFiles.Count)
        {
            DocSelectedIndex = DocVideoFiles.Count - 1;
        }
    }

    private void SyncCropTextFromList()
    {
        _syncingCropPaths = true;
        CropVideoPathsText = string.Join(Environment.NewLine, CropVideoFiles);
        _syncingCropPaths = false;
    }

    private void SyncMergeTextFromList()
    {
        _syncingMergePaths = true;
        MergeVideoPathsText = string.Join(Environment.NewLine, MergeVideoFiles);
        _syncingMergePaths = false;
    }

    private void SyncDocTextFromList()
    {
        _syncingDocPaths = true;
        DocVideoPathsText = string.Join(Environment.NewLine, DocVideoFiles);
        _syncingDocPaths = false;
    }

    private void SyncWeeklyTextFromList()
    {
        _syncingWeeklyPaths = true;
        WeeklyVideoPathsText = string.Join(Environment.NewLine, WeeklyVideoFiles);
        _syncingWeeklyPaths = false;
    }

    private static bool IsVideoFile(string path)
    {
        var ext = Path.GetExtension(path).ToLowerInvariant();
        return ext is ".mp4" or ".mkv" or ".mov" or ".avi" or ".flv" or ".ts";
    }

    private static bool IsAudioFile(string path)
    {
        var ext = Path.GetExtension(path).ToLowerInvariant();
        return ext is ".mp3" or ".wav" or ".aac" or ".flac" or ".m4a" or ".ogg";
    }

    private static string GetUniquePath(string directory, string baseName, string ext)
    {
        Directory.CreateDirectory(directory);
        var idx = 1;
        while (true)
        {
            var suffix = idx == 1 ? string.Empty : $"({idx})";
            var full = Path.Combine(directory, $"{baseName}{suffix}{ext}");
            if (!File.Exists(full))
            {
                return full;
            }

            idx++;
        }
    }

    private static void TryDeleteFile(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        try
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
        catch
        {
            // ignore
        }
    }

    private void TryOpenFolder(string path)
    {
        try
        {
            if (!Directory.Exists(path))
            {
                StatusText = "目标目录不存在";
                return;
            }

            if (OperatingSystem.IsWindows())
            {
                Process.Start(new ProcessStartInfo("explorer.exe", $"\"{path}\"") { UseShellExecute = true });
            }
            else if (OperatingSystem.IsMacOS())
            {
                Process.Start("open", path);
            }
            else
            {
                Process.Start("xdg-open", path);
            }
        }
        catch (Exception ex)
        {
            _log.Error("打开目录失败", ex);
            StatusText = $"打开目录失败: {ex.Message}";
        }
    }

    private List<string> ExtractOperatorList(string filename)
    {
        var baseName = Path.GetFileNameWithoutExtension(filename);
        if (!baseName.Contains('_'))
        {
            return ["未知"];
        }

        var opField = baseName.Split('_').Last();
        var list = opField.Split('+', StringSplitOptions.RemoveEmptyEntries)
            .Select(x => x.Trim())
            .Where(x => !string.IsNullOrWhiteSpace(x))
            .ToList();
        return list.Count == 0 ? ["未知"] : list;
    }

    private string ExtractNature(string filename)
    {
        foreach (var n in _videoNatureList)
        {
            if (filename.Contains(n, StringComparison.Ordinal))
            {
                return n;
            }
        }

        return "普通";
    }

    private string ExtractStageName(string filename)
    {
        var baseName = Path.GetFileNameWithoutExtension(filename);
        var part = baseName.Contains('_') ? baseName.Split('_')[0] : baseName;
        foreach (var n in _videoNatureList)
        {
            part = part.Replace(n, string.Empty, StringComparison.Ordinal);
        }

        part = part.Trim('_', '-', ' ');
        return string.IsNullOrWhiteSpace(part) ? baseName : part;
    }
}
