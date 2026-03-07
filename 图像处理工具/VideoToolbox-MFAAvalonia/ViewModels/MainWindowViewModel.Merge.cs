using CommunityToolkit.Mvvm.Input;
using System;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace VideoToolbox.ViewModels;

public partial class MainWindowViewModel
{
    [RelayCommand]
    private async Task RunMergeAsync()
    {
        const int tab = 2;
        if (IsBusy)
        {
            return;
        }

        var videos = MergeVideoFiles.Where(File.Exists).ToList();
        if (!videos.Any())
        {
            videos = ParsePathLines(MergeVideoPathsText).Where(File.Exists).ToList();
        }
        if (!videos.Any())
        {
            SetTabStatus(tab, "视频合并列表为空");
            return;
        }

        var mode = MergeAudioMode switch
        {
            "替换音频" => "replace",
            "叠加音频" => "mix",
            _ => "none"
        };

        if ((mode == "replace" || mode == "mix") && (!File.Exists(MergeAudioPath)))
        {
            SetTabStatus(tab, "已选择音频模式，但音频文件不存在");
            return;
        }

        if (string.IsNullOrWhiteSpace(MergeOutputName))
        {
            SetTabStatus(tab, "请输入输出文件名");
            return;
        }

        SetTabBusy(tab, true);
        SetTabStatus(tab, "视频合并处理中...");
        var logCb = CreateTabLogCallback(tab);
        string? tempMerge = null;
        string? listFile = null;
        try
        {
            var outputPath = GetUniquePath(_paths.MergeOutput, MergeOutputName.Trim(), ".mp4");
            listFile = Path.Combine(_paths.MergeOutput, $"filelist-{Guid.NewGuid():N}.txt");
            File.WriteAllLines(listFile, videos.Select(p => $"file '{p.Replace("\\", "/")}'"), Encoding.UTF8);

            tempMerge = Path.Combine(_paths.MergeOutput, $"temp-{Guid.NewGuid():N}.mp4");
            var concatArgs =
                $"-hide_banner -loglevel info -stats -f concat -safe 0 -i \"{listFile}\" -c copy -y \"{tempMerge}\"";
            var concatCode = await _process.RunAsync("ffmpeg", concatArgs, logCb);
            if (concatCode != 0)
            {
                SetTabStatus(tab, "视频拼接失败");
                SetTabBusy(tab, false);
                return;
            }

            var useMusicFinish = MergeSpeed == "到音乐放完" && (mode == "replace" || mode == "mix");
            var speed = 1.0;
            if (useMusicFinish)
            {
                var videoDur = await _process.ProbeDurationAsync(tempMerge);
                var audioDur = await _process.ProbeDurationAsync(MergeAudioPath);
                if (videoDur is > 0 && audioDur is > 0)
                {
                    speed = videoDur.Value / audioDur.Value;
                }
            }
            else if (!double.TryParse(MergeSpeed, NumberStyles.Any, CultureInfo.InvariantCulture, out speed) || speed <= 0)
            {
                SetTabStatus(tab, "倍速必须是数字或\u201c到音乐放完\u201d");
                SetTabBusy(tab, false);
                return;
            }

            if (mode == "none" && Math.Abs(speed - 1.0) < 0.0001)
            {
                File.Move(tempMerge, outputPath);
                tempMerge = null;
                SetTabStatus(tab, $"视频合并成功: {Path.GetFileName(outputPath)}");
                SetTabBusy(tab, false);
                return;
            }

            var setpts = (1.0 / speed).ToString("0.########", CultureInfo.InvariantCulture);
            var atempo = BuildAtempoChain(speed);

            string filter;
            if (mode == "none")
            {
                filter = $"[0:v]setpts={setpts}*PTS[v];[0:a]{atempo}[a]";
                await RunMergeEncodeAsync(tempMerge, outputPath, filter, null, shortest: false, logCb);
            }
            else if (mode == "replace")
            {
                filter = useMusicFinish
                    ? $"[0:v]setpts={setpts}*PTS[v];[1:a]anull[a]"
                    : (Math.Abs(speed - 1.0) < 0.0001
                        ? "[0:v]null[v];[1:a]anull[a]"
                        : $"[0:v]setpts={setpts}*PTS[v];[1:a]{atempo}[a]");
                await RunMergeEncodeAsync(tempMerge, outputPath, filter, MergeAudioPath, shortest: true, logCb);
            }
            else
            {
                if (useMusicFinish)
                {
                    filter = $"[0:v]setpts={setpts}*PTS[v];[0:a]{atempo}[a0];[a0][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]";
                }
                else if (Math.Abs(speed - 1.0) < 0.0001)
                {
                    filter = "[0:v]null[v];[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]";
                }
                else
                {
                    filter = $"[0:v]setpts={setpts}*PTS[v];[0:a]{atempo}[a0];[1:a]{atempo}[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[a]";
                }

                await RunMergeEncodeAsync(tempMerge, outputPath, filter, MergeAudioPath, shortest: false, logCb);
            }

            SetTabStatus(tab, $"视频合并成功: {Path.GetFileName(outputPath)}");
        }
        catch (Exception ex)
        {
            _log.Error("视频合并异常", ex);
            SetTabStatus(tab, $"视频合并失败: {ex.Message}");
        }
        finally
        {
            SetTabBusy(tab, false);
            TryDeleteFile(tempMerge);
            TryDeleteFile(listFile);
        }
    }

    private async Task RunMergeEncodeAsync(
        string tempMerge,
        string outputPath,
        string filterComplex,
        string? extraAudio,
        bool shortest,
        Action<string> logCb
    )
    {
        var shortestArg = shortest ? " -shortest" : string.Empty;
        var args = string.IsNullOrWhiteSpace(extraAudio)
            ? $"-hide_banner -loglevel info -stats -i \"{tempMerge}\" -filter_complex \"{filterComplex}\" -map \"[v]\" -map \"[a]\" -c:v libx264 -c:a aac{shortestArg} -y \"{outputPath}\""
            : $"-hide_banner -loglevel info -stats -i \"{tempMerge}\" -i \"{extraAudio}\" -filter_complex \"{filterComplex}\" -map \"[v]\" -map \"[a]\" -c:v libx264 -c:a aac{shortestArg} -y \"{outputPath}\"";
        var code = await _process.RunAsync("ffmpeg", args, logCb);
        if (code != 0)
        {
            throw new InvalidOperationException($"ffmpeg 处理失败，返回码 {code}");
        }
    }
}
