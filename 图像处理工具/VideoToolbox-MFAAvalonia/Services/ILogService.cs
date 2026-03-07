using System;

namespace VideoToolbox.Services;

public interface ILogService
{
    event Action<string>? OnLog;
    void Info(string message);
    void Error(string message, Exception? exception = null);
}
