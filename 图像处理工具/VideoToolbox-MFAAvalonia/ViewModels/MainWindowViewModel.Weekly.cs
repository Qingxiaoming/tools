using CommunityToolkit.Mvvm.Input;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading.Tasks;

namespace VideoToolbox.ViewModels;

public partial class MainWindowViewModel
{
    [RelayCommand]
    private async Task RunWeeklyAsync()
    {
        const int tab = 4;
        if (IsBusy)
        {
            return;
        }

        var files = WeeklyVideoFiles.Where(File.Exists).ToList();
        if (!files.Any())
        {
            files = ParsePathLines(WeeklyVideoPathsText).Where(File.Exists).ToList();
        }
        if (!files.Any())
        {
            SetTabStatus(tab, "录屏整理列表为空");
            return;
        }

        SetTabBusy(tab, true);
        var success = 0;
        var fail = 0;
        var logCb = CreateTabLogCallback(tab);
        try
        {
            var timeline = new List<(string Path, string Name, double Start, double End)>();
            var currentStart = 0.0;
            foreach (var file in files)
            {
                var d = await _process.ProbeDurationAsync(file);
                if (d is null || d <= 0)
                {
                    fail++;
                    LogToTab(tab, $"无法获取时长: {System.IO.Path.GetFileName(file)}");
                    continue;
                }

                timeline.Add((file, System.IO.Path.GetFileName(file), currentStart, currentStart + d.Value));
                currentStart += d.Value;
            }

            if (timeline.Count == 0)
            {
                SetTabStatus(tab, "录屏整理失败: 无可用时长");
                SetTabBusy(tab, false);
                return;
            }

            const int segmentSeconds = 24 * 3600;
            var totalDuration = timeline[^1].End;
            var totalParts = Math.Max(1, (int)Math.Ceiling(totalDuration / segmentSeconds));
            var isoWeek = System.Globalization.ISOWeek.GetWeekOfYear(DateTime.Today);
            var prefix = _paths.WeeklyPrefixTemplate
                .Replace("{year}", DateTime.Today.Year.ToString(CultureInfo.InvariantCulture))
                .Replace("{week:00}", isoWeek.ToString("00", CultureInfo.InvariantCulture));

            var tmpRoot = System.IO.Path.Combine(_paths.WeeklyOutput, "_tmp_weekly");
            Directory.CreateDirectory(tmpRoot);

            for (var part = 0; part < totalParts; part++)
            {
                var partStart = part * segmentSeconds;
                var partEnd = Math.Min(totalDuration, (part + 1) * segmentSeconds);
                var slices = new List<(string Path, string Name, double LocalStart, double Dur)>();
                foreach (var item in timeline)
                {
                    var overlapStart = Math.Max(partStart, item.Start);
                    var overlapEnd = Math.Min(partEnd, item.End);
                    if (overlapEnd <= overlapStart)
                    {
                        continue;
                    }

                    slices.Add((item.Path, item.Name, overlapStart - item.Start, overlapEnd - overlapStart));
                }

                if (slices.Count == 0)
                {
                    continue;
                }

                var partTag = $"part{part + 1:00}";
                var partTmp = System.IO.Path.Combine(tmpRoot, partTag);
                Directory.CreateDirectory(partTmp);

                var audioChunks = new List<string>();
                for (var i = 0; i < slices.Count; i++)
                {
                    var slice = slices[i];
                    var chunk = System.IO.Path.Combine(partTmp, $"{prefix}_{partTag}_a_{i + 1:00}.m4a");
                    var args = $"-hide_banner -loglevel info -stats -ss {slice.LocalStart.ToString(CultureInfo.InvariantCulture)} -i \"{slice.Path}\" -t {slice.Dur.ToString(CultureInfo.InvariantCulture)} -vn -c:a aac -y \"{chunk}\"";
                    var code = await _process.RunAsync("ffmpeg", args, logCb);
                    if (code != 0)
                    {
                        fail++;
                        break;
                    }

                    audioChunks.Add(chunk);
                }

                if (audioChunks.Count == 0)
                {
                    continue;
                }

                var audioList = System.IO.Path.Combine(partTmp, $"{prefix}_{partTag}_audio_list.txt");
                await File.WriteAllLinesAsync(audioList, audioChunks.Select(x => $"file '{x.Replace("\\", "/")}'"));
                var audioOutput = GetUniquePath(_paths.WeeklyOutput, $"{prefix}_{partTag}_audio", ".m4a");
                var audioConcat = $"-hide_banner -loglevel info -stats -f concat -safe 0 -i \"{audioList}\" -c:a aac -y \"{audioOutput}\"";
                if (await _process.RunAsync("ffmpeg", audioConcat, logCb) != 0)
                {
                    fail++;
                    continue;
                }

                var videoChunks = new List<string>();
                for (var i = 0; i < slices.Count; i++)
                {
                    var slice = slices[i];
                    var chunk = System.IO.Path.Combine(partTmp, $"{prefix}_{partTag}_v_{i + 1:00}.mp4");
                    var args = $"-hide_banner -loglevel info -stats -ss {slice.LocalStart.ToString(CultureInfo.InvariantCulture)} -i \"{slice.Path}\" -t {slice.Dur.ToString(CultureInfo.InvariantCulture)} -an -filter:v setpts=PTS/60 -c:v libx264 -y \"{chunk}\"";
                    var code = await _process.RunAsync("ffmpeg", args, logCb);
                    if (code != 0)
                    {
                        fail++;
                        break;
                    }

                    videoChunks.Add(chunk);
                }

                if (videoChunks.Count == 0)
                {
                    continue;
                }

                var videoList = System.IO.Path.Combine(partTmp, $"{prefix}_{partTag}_video_list.txt");
                await File.WriteAllLinesAsync(videoList, videoChunks.Select(x => $"file '{x.Replace("\\", "/")}'"));
                var videoOutput = GetUniquePath(_paths.WeeklyOutput, $"{prefix}_{partTag}_x60", ".mp4");
                var videoConcat = $"-hide_banner -loglevel info -stats -f concat -safe 0 -i \"{videoList}\" -c copy -y \"{videoOutput}\"";
                if (await _process.RunAsync("ffmpeg", videoConcat, logCb) != 0)
                {
                    fail++;
                    continue;
                }

                success++;
            }
        }
        catch (Exception ex)
        {
            _log.Error("录屏整理异常", ex);
            SetTabStatus(tab, $"录屏整理失败: {ex.Message}");
            SetTabBusy(tab, false);
            return;
        }

        SetTabBusy(tab, false);
        SetTabStatus(tab, $"录屏整理完成: 成功 {success} 段, 失败 {fail} 段");
    }
}
