using System;
using System.IO;

namespace VideoToolbox.Services;

public sealed class FileLogService(AppPaths paths) : ILogService
{
    public event Action<string>? OnLog;

    public void Info(string message)
    {
        Write("INFO", message);
    }

    public void Error(string message, Exception? exception = null)
    {
        var full = exception is null ? message : $"{message}\n{exception}";
        Write("ERROR", full);
    }

    private void Write(string level, string message)
    {
        var line = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] {message}";
        try
        {
            paths.EnsureDirectories();
            File.AppendAllText(paths.AppLog, line + Environment.NewLine);
        }
        catch
        {
            // Logging must not break UI workflow.
        }

        OnLog?.Invoke(line);
    }
}
