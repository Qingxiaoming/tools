using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text.Json;

namespace VideoToolbox.Services;

public sealed class UserConfigService(ILogService log)
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true
    };

    // 使用 Process 获取 exe 实际路径，兼容单文件发布模式
    private static string GetExeDirectory()
    {
        try
        {
            var exePath = Process.GetCurrentProcess().MainModule?.FileName;
            if (!string.IsNullOrEmpty(exePath))
                return Path.GetDirectoryName(exePath)!;
        }
        catch { }

        // 降级到 Assembly 位置
        var asm = Assembly.GetEntryAssembly()?.Location;
        if (!string.IsNullOrEmpty(asm))
            return Path.GetDirectoryName(asm)!;

        return AppContext.BaseDirectory;
    }

    public string ConfigPath => Path.Combine(GetExeDirectory(), "config.json");

    public UserConfig LoadOrCreate()
    {
        try
        {
            if (!File.Exists(ConfigPath))
            {
                var created = new UserConfig();
                Save(created);
                return created;
            }

            var text = File.ReadAllText(ConfigPath);
            var cfg = JsonSerializer.Deserialize<UserConfig>(text);
            if (cfg is null)
            {
                cfg = new UserConfig();
                Save(cfg);
            }

            return cfg;
        }
        catch (Exception ex)
        {
            log.Error("读取配置失败，使用默认配置", ex);
            return new UserConfig();
        }
    }

    public void Save(UserConfig config)
    {
        var text = JsonSerializer.Serialize(config, JsonOptions);
        File.WriteAllText(ConfigPath, text);
    }

    public DateTime GetLastWriteUtc()
    {
        return File.Exists(ConfigPath) ? File.GetLastWriteTimeUtc(ConfigPath) : DateTime.MinValue;
    }

    public void OpenInDefaultEditor()
    {
        if (!File.Exists(ConfigPath))
        {
            Save(new UserConfig());
        }

        if (OperatingSystem.IsWindows())
        {
            Process.Start(new ProcessStartInfo("explorer.exe", $"\"{ConfigPath}\"") { UseShellExecute = true });
            return;
        }

        if (OperatingSystem.IsMacOS())
        {
            Process.Start("open", ConfigPath);
            return;
        }

        Process.Start("xdg-open", ConfigPath);
    }
}
