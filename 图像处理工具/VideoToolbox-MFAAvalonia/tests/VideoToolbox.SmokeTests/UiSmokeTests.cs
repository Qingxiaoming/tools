using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using VideoToolbox.Services;
using VideoToolbox.ViewModels;
using Xunit;

namespace VideoToolbox.SmokeTests;

public sealed class UiSmokeTests : IDisposable
{
    private readonly string _tempRoot;

    public UiSmokeTests()
    {
        _tempRoot = Path.Combine(Path.GetTempPath(), $"videotoolbox-smoke-{Guid.NewGuid():N}");
        Directory.CreateDirectory(_tempRoot);
        SetTestEnvironment(_tempRoot);
    }

    [Fact]
    public void 五大入口命令_可访问()
    {
        var vm = CreateVm();
        Assert.NotNull(vm.RunSegmentCommand);
        Assert.NotNull(vm.RunCropCommand);
        Assert.NotNull(vm.RunMergeCommand);
        Assert.NotNull(vm.RunDocGenerationCommand);
        Assert.NotNull(vm.RunWeeklyCommand);
    }

    [Fact]
    public async Task 五大入口_空输入时有防呆提示()
    {
        var vm = CreateVm();

        await vm.RunSegmentCommand.ExecuteAsync(null);
        Assert.Contains("有效的视频路径", vm.StatusText, StringComparison.Ordinal);

        await vm.RunCropCommand.ExecuteAsync(null);
        Assert.Contains("画幅裁剪视频列表为空", vm.StatusText, StringComparison.Ordinal);

        await vm.RunMergeCommand.ExecuteAsync(null);
        Assert.Contains("视频合并列表为空", vm.StatusText, StringComparison.Ordinal);

        await vm.RunDocGenerationCommand.ExecuteAsync(null);
        Assert.Contains("文档生成列表为空", vm.StatusText, StringComparison.Ordinal);

        await vm.RunWeeklyCommand.ExecuteAsync(null);
        Assert.Contains("录屏整理列表为空", vm.StatusText, StringComparison.Ordinal);
    }

    [Fact]
    public void 拖拽分发_按页签导入目标列表()
    {
        var vm = CreateVm();
        var video = CreateDummyFile("demo.mp4");
        var audio = CreateDummyFile("bgm.mp3");
        var text = CreateDummyFile("ignore.txt");

        vm.SelectedTabIndex = 0;
        vm.HandleDroppedFiles([video, text]);
        Assert.Equal(video, vm.SegmentVideoPath);

        vm.SelectedTabIndex = 1;
        vm.HandleDroppedFiles([video, text]);
        Assert.Contains(video, vm.CropVideoFiles);

        vm.SelectedTabIndex = 2;
        vm.HandleDroppedFiles([audio]);
        Assert.Equal(audio, vm.MergeAudioPath);

        vm.HandleDroppedFiles([video, text]);
        Assert.Contains(video, vm.MergeVideoFiles);

        vm.SelectedTabIndex = 3;
        vm.HandleDroppedFiles([video, text]);
        Assert.Contains(video, vm.DocVideoFiles);

        vm.SelectedTabIndex = 4;
        vm.HandleDroppedFiles([video, text]);
        Assert.Contains(video, vm.WeeklyVideoFiles);
    }

    public void Dispose()
    {
        TryDeleteDirectory(_tempRoot);
        SetTestEnvironment(null);
    }

    private MainWindowViewModel CreateVm()
    {
        var log = new TestLogService();
        var paths = new AppPaths();
        var userConfig = new UserConfigService(log);
        var process = new ProcessService(log);
        return new MainWindowViewModel(paths, log, process, userConfig);
    }

    private string CreateDummyFile(string fileName)
    {
        var path = Path.Combine(_tempRoot, fileName);
        File.WriteAllText(path, "dummy");
        return path;
    }

    private static void SetTestEnvironment(string? root)
    {
        string? temp(string name) => root is null ? null : Path.Combine(root, name);

        Environment.SetEnvironmentVariable("VTB_ROOT_OUTPUT", temp("out-root"));
        Environment.SetEnvironmentVariable("VTB_WEEKLY_ROOT", temp("weekly-root"));
        Environment.SetEnvironmentVariable("VTB_DOC_TRANSFER_DOC_DIR", temp("doc-transfer"));
        Environment.SetEnvironmentVariable("VTB_DOC_TRANSFER_MEDIA_DIR", temp("doc-transfer-media"));
        Environment.SetEnvironmentVariable("VTB_WEEKLY_PREFIX_TEMPLATE", "{year}-{week:00}w");
    }

    private static void TryDeleteDirectory(string path)
    {
        try
        {
            if (Directory.Exists(path))
            {
                Directory.Delete(path, true);
            }
        }
        catch
        {
            // 测试清理失败不应影响结果。
        }
    }

    private sealed class TestLogService : ILogService
    {
        public event Action<string>? OnLog;

        public List<string> Lines { get; } = [];

        public void Info(string message)
        {
            Lines.Add(message);
            OnLog?.Invoke(message);
        }

        public void Error(string message, Exception? exception = null)
        {
            var full = exception is null ? message : $"{message}: {exception.Message}";
            Lines.Add(full);
            OnLog?.Invoke(full);
        }
    }
}
