using CommunityToolkit.Mvvm.Input;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace VideoToolbox.ViewModels;

public partial class MainWindowViewModel
{
    [RelayCommand]
    private async Task RunSegmentAsync()
    {
        const int tab = 0;
        if (IsBusy)
        {
            return;
        }

        var input = ParsePathLines(SegmentVideoPath).FirstOrDefault();
        if (string.IsNullOrWhiteSpace(input) || !File.Exists(input))
        {
            SetTabStatus(tab, "请先填写有效的视频路径");
            return;
        }

        var lines = SegmentBatchText.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries);
        var tasks = new List<(string Start, string End, string Name)>();
        var errors = new List<string>();
        for (var i = 0; i < lines.Length; i++)
        {
            var ok = TryParseSegmentLine(lines[i], out var parsed, out var err);
            if (!ok || parsed is null)
            {
                errors.Add($"第{i + 1}行: {err}");
                continue;
            }

            tasks.Add(parsed.Value);
        }

        if (errors.Count > 0)
        {
            foreach (var e in errors)
            {
                LogToTab(tab, e);
            }

            SetTabStatus(tab, "输入格式有误，请先修正");
            return;
        }

        SetTabBusy(tab, true);
        SetTabStatus(tab, "多段截取处理中...");
        SegmentLastOutputs = [];
        var success = 0;
        var fail = 0;
        var logCb = CreateTabLogCallback(tab);
        try
        {
            foreach (var task in tasks)
            {
                var baseName = Path.GetFileNameWithoutExtension(task.Name);
                var ext = Path.GetExtension(task.Name);
                if (string.IsNullOrWhiteSpace(ext))
                {
                    ext = ".mp4";
                }

                var outPath = GetUniquePath(_paths.SegmentOutput, baseName, ext);
                var startSec = ToSeconds(task.Start);
                var endSec = ToSeconds(task.End);
                if (startSec is null || endSec is null || endSec <= startSec)
                {
                    fail++;
                    continue;
                }

                var duration = (endSec.Value - startSec.Value).ToString(CultureInfo.InvariantCulture);
                var startNorm = task.Start.Replace('：', ':');

                var args = SegmentPreciseCrop
                    ? $"-hide_banner -loglevel info -stats -ss {startNorm} -i \"{input}\" -t {duration} -c:v libx264 -c:a aac -avoid_negative_ts make_zero -y \"{outPath}\""
                    : $"-hide_banner -loglevel info -stats -ss {startNorm} -i \"{input}\" -ss 0 -t {duration} -c copy -avoid_negative_ts make_zero -y \"{outPath}\"";

                SetTabStatus(tab, $"处理中: {Path.GetFileName(outPath)}");
                var code = await _process.RunAsync("ffmpeg", args, logCb);
                if (code == 0)
                {
                    success++;
                    SegmentLastOutputs.Add(outPath);
                }
                else
                {
                    fail++;
                }
            }
        }
        catch (Exception ex)
        {
            _log.Error("多段截取异常", ex);
            SetTabStatus(tab, $"多段截取失败: {ex.Message}");
            SetTabBusy(tab, false);
            return;
        }

        SetTabBusy(tab, false);
        SetTabStatus(tab, $"多段截取完成: 成功 {success} 段, 失败 {fail} 段");
    }

    private bool TryParseSegmentLine(
        string line,
        out (string Start, string End, string Name)? parsed,
        out string err
    )
    {
        parsed = null;
        err = string.Empty;

        const string timePatternColon = @"\b\d{1,2}[:：]\d{2}[:：]\d{2}(?:\.\d{1,3})?\b";
        const string timePattern6 = @"\b\d{6}\b";
        var matches = new List<(int Start, int End, string Value)>();

        foreach (Match m in Regex.Matches(line, timePatternColon))
        {
            matches.Add((m.Index, m.Index + m.Length, m.Value));
        }

        foreach (Match m in Regex.Matches(line, timePattern6))
        {
            var overlap = matches.Any(x => m.Index < x.End && m.Index + m.Length > x.Start);
            if (overlap)
            {
                continue;
            }

            var t = m.Value;
            matches.Add((m.Index, m.Index + m.Length, $"{t[..2]}:{t[2..4]}:{t[4..6]}"));
        }

        matches = matches.OrderBy(x => x.Start).ToList();
        if (matches.Count == 0)
        {
            err = "未检测到时间";
            return false;
        }

        if (matches.Count == 1)
        {
            err = "仅检测到一个时间";
            return false;
        }

        if (matches.Count > 2)
        {
            err = "检测到超过两个时间";
            return false;
        }

        var t1 = matches[0].Value;
        var t2 = matches[1].Value;
        var s1 = ToSeconds(t1);
        var s2 = ToSeconds(t2);
        if (s1 is null || s2 is null)
        {
            err = "时间格式不合法";
            return false;
        }

        if (Math.Abs(s1.Value - s2.Value) < 0.0001)
        {
            err = "开始与结束时间不能相同";
            return false;
        }

        var start = s1 < s2 ? t1 : t2;
        var end = s1 < s2 ? t2 : t1;
        var a0 = matches[0].Start;
        var a1 = matches[0].End;
        var b0 = matches[1].Start;
        var b1 = matches[1].End;
        var name = (line[..a0] + line[a1..b0] + line[b1..]).Trim().Trim('"', '\'');
        if (string.IsNullOrWhiteSpace(name))
        {
            err = "缺少文件名";
            return false;
        }

        var lower = name.ToLowerInvariant();
        if (!(lower.EndsWith(".mp4") || lower.EndsWith(".mkv") || lower.EndsWith(".mov") || lower.EndsWith(".avi")))
        {
            name += ".mp4";
        }

        parsed = (start, end, name);
        return true;
    }
}
