using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using CommunityToolkit.Mvvm.Input;
using System;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using VideoToolbox.Views.Windows;

namespace VideoToolbox.ViewModels;

public partial class MainWindowViewModel
{
    [RelayCommand]
    private async Task SelectCropRoiVisualAsync()
    {
        const int tab = 1;
        var file = ParsePathLines(CropVideoPathsText).FirstOrDefault(File.Exists);
        if (string.IsNullOrWhiteSpace(file))
        {
            SetTabStatus(tab, "请先填入至少一个有效视频路径");
            return;
        }

        var meta = await _process.ProbeResolutionAsync(file);
        if (meta is null)
        {
            SetTabStatus(tab, "无法获取视频分辨率，不能进行ROI框选");
            return;
        }

        Directory.CreateDirectory(_paths.LogsDir);
        var previewPath = Path.Combine(_paths.LogsDir, $"roi-preview-{Guid.NewGuid():N}.jpg");
        var logCb = CreateTabLogCallback(tab);
        try
        {
            var extractArgs = $"-hide_banner -loglevel error -ss 1 -i \"{file}\" -frames:v 1 -y \"{previewPath}\"";
            var code = await _process.RunAsync("ffmpeg", extractArgs, logCb);
            if (code != 0 || !File.Exists(previewPath))
            {
                extractArgs = $"-hide_banner -loglevel error -i \"{file}\" -frames:v 1 -y \"{previewPath}\"";
                code = await _process.RunAsync("ffmpeg", extractArgs, logCb);
            }
            if (code != 0 || !File.Exists(previewPath))
            {
                SetTabStatus(tab, "提取预览帧失败，无法框选ROI");
                return;
            }

            var owner = (Application.Current?.ApplicationLifetime as IClassicDesktopStyleApplicationLifetime)?.MainWindow;
            if (owner is null)
            {
                SetTabStatus(tab, "无法获取主窗口，不能打开ROI选择器");
                return;
            }

            var selector = new RoiSelectorWindow(previewPath, meta.Value.Width, meta.Value.Height);
            var roi = await selector.ShowDialog<(int X, int Y, int W, int H)?>(owner);
            if (roi is null)
            {
                SetTabStatus(tab, "已取消ROI选择");
                return;
            }

            CropRoiText = $"{roi.Value.X},{roi.Value.Y},{roi.Value.W},{roi.Value.H}";
            SetTabStatus(tab, $"已设置ROI: {CropRoiText}");
        }
        catch (Exception ex)
        {
            _log.Error("ROI可视化框选失败", ex);
            SetTabStatus(tab, $"ROI框选失败: {ex.Message}");
        }
        finally
        {
            TryDeleteFile(previewPath);
        }
    }

    [RelayCommand]
    private async Task RunCropAsync()
    {
        const int tab = 1;
        if (IsBusy)
        {
            return;
        }

        var files = ParsePathLines(CropVideoPathsText).Where(File.Exists).ToList();
        if (!files.Any())
        {
            SetTabStatus(tab, "画幅裁剪视频列表为空");
            return;
        }

        if (!TryParseRoi(CropRoiText, out var x, out var y, out var w, out var h))
        {
            SetTabStatus(tab, "ROI 格式错误，请使用 x,y,w,h");
            return;
        }

        SetTabBusy(tab, true);
        SetTabStatus(tab, "画幅裁剪处理中...");
        CropLastOutputs = [];
        var success = 0;
        var fail = 0;
        var logCb = CreateTabLogCallback(tab);
        try
        {
            foreach (var vpath in files)
            {
                var meta = await _process.ProbeResolutionAsync(vpath);
                if (meta is null)
                {
                    fail++;
                    LogToTab(tab, $"无法获取分辨率: {Path.GetFileName(vpath)}");
                    continue;
                }

                var (origW, origH) = meta.Value;
                var cx = Math.Max(0, Math.Min(x, origW - 1));
                var cy = Math.Max(0, Math.Min(y, origH - 1));
                var cw = Math.Max(1, Math.Min(w, origW - cx));
                var ch = Math.Max(1, Math.Min(h, origH - cy));
                var fileName = Path.GetFileName(vpath);
                var outPath = GetUniquePath(
                    _paths.CropOutput,
                    Path.GetFileNameWithoutExtension(fileName),
                    Path.GetExtension(fileName)
                );

                string filter;
                if (ch != origH)
                {
                    var newH = origH;
                    var newW = (int)Math.Round(cw * origH / (double)ch);
                    if (newW > origW)
                    {
                        var newW2 = origW;
                        var newH2 = (int)Math.Round(ch * origW / (double)cw);
                        filter = $"crop={cw}:{ch}:{cx}:{cy},scale={newW2}:{newH2},pad={origW}:{origH}:0:(oh-ih)/2:black";
                    }
                    else
                    {
                        filter = $"crop={cw}:{ch}:{cx}:{cy},scale={newW}:{newH},pad={origW}:{origH}:(ow-iw)/2:0:black";
                    }
                }
                else
                {
                    filter = $"crop={cw}:{ch}:{cx}:{cy},pad={origW}:{origH}:({origW}-{cw})/2:({origH}-{ch})/2:black";
                }

                SetTabStatus(tab, $"处理中: {fileName}");
                var args = $"-hide_banner -loglevel info -stats -i \"{vpath}\" -vf \"{filter}\" -c:a copy -y \"{outPath}\"";
                var code = await _process.RunAsync("ffmpeg", args, logCb);
                if (code == 0)
                {
                    success++;
                    CropLastOutputs.Add(outPath);
                }
                else
                {
                    fail++;
                }
            }
        }
        catch (Exception ex)
        {
            _log.Error("画幅裁剪异常", ex);
            SetTabStatus(tab, $"画幅裁剪失败: {ex.Message}");
            SetTabBusy(tab, false);
            return;
        }

        SetTabBusy(tab, false);
        SetTabStatus(tab, $"画幅裁剪完成: 成功 {success} 个, 失败 {fail} 个");
    }

    private static bool TryParseRoi(string text, out int x, out int y, out int w, out int h)
    {
        x = y = w = h = 0;
        var parts = text.Split([',', '，', ' ', '\t'], StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length != 4)
        {
            return false;
        }

        if (!int.TryParse(parts[0], out x) || !int.TryParse(parts[1], out y) || !int.TryParse(parts[2], out w) || !int.TryParse(parts[3], out h))
        {
            return false;
        }

        return x >= 0 && y >= 0 && w > 0 && h > 0;
    }
}
