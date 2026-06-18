using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;

namespace VideoToolbox.Services;

public sealed class AppPaths
{
    // 获取 exe 实际所在目录，兼容单文件发布模式
    private static string GetExeDirectory()
    {
        try
        {
            var exePath = Process.GetCurrentProcess().MainModule?.FileName;
            if (!string.IsNullOrEmpty(exePath))
                return Path.GetDirectoryName(exePath)!;
        }
        catch { }

        var asm = Assembly.GetEntryAssembly()?.Location;
        if (!string.IsNullOrEmpty(asm))
            return Path.GetDirectoryName(asm)!;

        return AppContext.BaseDirectory;
    }

    private static readonly string ExeDirectory = GetExeDirectory();
    public string RootOutput { get; } = GetEnvOrDefault("VTB_ROOT_OUTPUT", @"E:\toolbox输出");
    public string SegmentOutput => Path.Combine(RootOutput, "多段截取");
    public string CropOutput => Path.Combine(RootOutput, "画幅裁剪");
    public string MergeOutput => Path.Combine(RootOutput, "合并输出");
    public string DocOutput => Path.Combine(RootOutput, "文档生成");
    public string WeeklyRoot { get; } = GetEnvOrDefault("VTB_WEEKLY_ROOT", @"I:\录屏");
    public string DocTransferDocDir { get; } =
        GetEnvOrDefault("VTB_DOC_TRANSFER_DOC_DIR", @"D:\Users\Windows10\Desktop\0V0燕小重的文库\姑且算作我的\打穿泰拉~");
    public string DocTransferMediaDir { get; } =
        GetEnvOrDefault("VTB_DOC_TRANSFER_MEDIA_DIR", @"D:\Users\Windows10\Desktop\0V0燕小重的文库\姑且算作我的\打穿泰拉~\附件");

    public string WeeklyPrefixTemplate { get; } = GetEnvOrDefault("VTB_WEEKLY_PREFIX_TEMPLATE", "{year}-{week:00}w");

    public string WeeklyOutput
    {
        get
        {
            var iso = DateTime.Today;
            var cal = System.Globalization.ISOWeek.GetWeekOfYear(iso);
            return Path.Combine(WeeklyRoot, $"{iso.Year}_{cal:00}");
        }
    }

    public string LogsDir => Path.Combine(ExeDirectory, "logs");
    public string AppLog => Path.Combine(LogsDir, "toolbox.log");
    public string LayoutFile => Path.Combine(ExeDirectory, "layout.json");

    private static string GetEnvOrDefault(string key, string fallback)
    {
        var value = Environment.GetEnvironmentVariable(key);
        return string.IsNullOrWhiteSpace(value) ? fallback : value.Trim();
    }

    public void EnsureDirectories()
    {
        Directory.CreateDirectory(RootOutput);
        Directory.CreateDirectory(SegmentOutput);
        Directory.CreateDirectory(CropOutput);
        Directory.CreateDirectory(MergeOutput);
        Directory.CreateDirectory(DocOutput);
        Directory.CreateDirectory(WeeklyRoot);
        Directory.CreateDirectory(WeeklyOutput);
        Directory.CreateDirectory(DocTransferDocDir);
        Directory.CreateDirectory(DocTransferMediaDir);
        Directory.CreateDirectory(LogsDir);
    }
}
