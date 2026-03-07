using System;
using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Threading.Tasks;

namespace VideoToolbox.Services;

public sealed class ProcessService(ILogService logService)
{
    private static readonly bool IsWindows = OperatingSystem.IsWindows();

    public async Task<int> RunAsync(string fileName, string arguments, Action<string>? onOutput = null)
    {
        var psi = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };

        using var process = new Process { StartInfo = psi, EnableRaisingEvents = true };
        process.OutputDataReceived += (_, e) =>
        {
            if (string.IsNullOrWhiteSpace(e.Data))
            {
                return;
            }

            onOutput?.Invoke(e.Data);
        };
        process.ErrorDataReceived += (_, e) =>
        {
            if (string.IsNullOrWhiteSpace(e.Data))
            {
                return;
            }

            onOutput?.Invoke(e.Data);
        };

        logService.Info($"Exec: {fileName} {arguments}");
        process.Start();
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        await process.WaitForExitAsync();
        return process.ExitCode;
    }

    public async Task<double?> ProbeDurationAsync(string path)
    {
        var output = new StringBuilder();
        var args =
            $"-v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 \"{path}\"";
        var code = await RunAsync("ffprobe", args, line => output.AppendLine(line));
        if (code != 0)
        {
            return null;
        }

        return double.TryParse(
            output.ToString().Trim(),
            NumberStyles.Any,
            CultureInfo.InvariantCulture,
            out var d
        )
            ? d
            : null;
    }

    public async Task<(int Width, int Height)?> ProbeResolutionAsync(string path)
    {
        var output = new StringBuilder();
        var args =
            $"-v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 \"{path}\"";
        var code = await RunAsync("ffprobe", args, line => output.AppendLine(line));
        if (code != 0)
        {
            return null;
        }

        var arr = output.ToString().Trim().Split(',');
        if (arr.Length != 2)
        {
            return null;
        }

        return int.TryParse(arr[0], out var w) && int.TryParse(arr[1], out var h)
            ? (w, h)
            : null;
    }
}
