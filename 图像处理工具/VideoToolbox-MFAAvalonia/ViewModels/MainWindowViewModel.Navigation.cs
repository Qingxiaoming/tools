using CommunityToolkit.Mvvm.Input;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace VideoToolbox.ViewModels;

public partial class MainWindowViewModel
{
    public void HandleDroppedFiles(IReadOnlyList<string> files)
    {
        try
        {
            var validFiles = files
                .Where(x => !string.IsNullOrWhiteSpace(x))
                .Select(x => x.Trim().Trim('"'))
                .Where(File.Exists)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();

            if (validFiles.Count == 0)
            {
                StatusText = "拖拽失败：没有检测到有效文件";
                return;
            }

            switch (SelectedTabIndex)
            {
                case 0:
                    var firstVideo = validFiles.FirstOrDefault(IsVideoFile);
                    if (string.IsNullOrWhiteSpace(firstVideo))
                    {
                        StatusText = "多段截取仅支持视频文件";
                        return;
                    }

                    SegmentVideoPath = firstVideo;
                    StatusText = $"已导入多段截取输入：{Path.GetFileName(firstVideo)}";
                    break;
                case 1:
                    var cropVideos = validFiles.Where(IsVideoFile).ToList();
                    if (cropVideos.Count == 0)
                    {
                        StatusText = "画幅裁剪仅支持视频文件";
                        return;
                    }

                    CropVideoPathsText = ComposePathText(cropVideos, !OverwriteCrossTabTransfer ? CropVideoPathsText : null);
                    StatusText = $"已导入画幅裁剪输入：{cropVideos.Count} 个文件";
                    break;
                case 2:
                    if (validFiles.Count == 1 && IsAudioFile(validFiles[0]))
                    {
                        MergeAudioPath = validFiles[0];
                        StatusText = $"已导入合并音频：{Path.GetFileName(validFiles[0])}";
                        return;
                    }

                    var mergeVideos = validFiles.Where(IsVideoFile).ToList();
                    if (mergeVideos.Count == 0)
                    {
                        StatusText = "视频合并仅支持视频文件（单独拖入一个音频可设置背景音）";
                        return;
                    }

                    MergeVideoPathsText = ComposePathText(mergeVideos, !OverwriteCrossTabTransfer ? MergeVideoPathsText : null);
                    StatusText = $"已导入视频合并输入：{mergeVideos.Count} 个文件";
                    break;
                case 3:
                    var docVideos = validFiles.Where(IsVideoFile).ToList();
                    if (docVideos.Count == 0)
                    {
                        StatusText = "文档生成仅支持视频文件";
                        return;
                    }

                    DocVideoPathsText = ComposePathText(docVideos, !OverwriteCrossTabTransfer ? DocVideoPathsText : null);
                    StatusText = $"已导入文档生成输入：{docVideos.Count} 个文件";
                    break;
                case 4:
                    var weeklyVideos = validFiles.Where(IsVideoFile).ToList();
                    if (weeklyVideos.Count == 0)
                    {
                        StatusText = "录屏整理仅支持视频文件";
                        return;
                    }

                    WeeklyVideoPathsText = ComposePathText(weeklyVideos, !OverwriteCrossTabTransfer ? WeeklyVideoPathsText : null);
                    StatusText = $"已导入录屏整理输入：{weeklyVideos.Count} 个文件";
                    break;
                default:
                    StatusText = "当前页签不支持拖拽导入";
                    break;
            }
        }
        catch (Exception ex)
        {
            _log.Error("处理拖拽文件失败", ex);
            StatusText = $"处理拖拽文件失败: {ex.Message}";
        }
    }

    [RelayCommand]
    private void ClearCropList()
    {
        CropVideoFiles.Clear();
        CropSelectedIndex = -1;
        SyncCropTextFromList();
        StatusText = "已清空画幅裁剪列表";
    }

    [RelayCommand]
    private void ClearDocList()
    {
        DocVideoFiles.Clear();
        DocSelectedIndex = -1;
        SyncDocTextFromList();
        StatusText = "已清空文档生成列表";
    }

    [RelayCommand]
    private void ClearMergeList()
    {
        MergeVideoFiles.Clear();
        MergeSelectedIndex = -1;
        SyncMergeTextFromList();
        StatusText = "已清空视频合并列表";
    }

    [RelayCommand]
    private void RemoveSelectedMerge()
    {
        if (MergeSelectedIndex < 0 || MergeSelectedIndex >= MergeVideoFiles.Count)
        {
            StatusText = "请先选择要删除的合并视频";
            return;
        }

        MergeVideoFiles.RemoveAt(MergeSelectedIndex);
        if (MergeSelectedIndex >= MergeVideoFiles.Count)
        {
            MergeSelectedIndex = MergeVideoFiles.Count - 1;
        }

        SyncMergeTextFromList();
        StatusText = "已删除选中合并视频";
    }

    [RelayCommand]
    private void MoveUpMerge()
    {
        if (MergeSelectedIndex <= 0 || MergeSelectedIndex >= MergeVideoFiles.Count)
        {
            return;
        }

        var idx = MergeSelectedIndex;
        (MergeVideoFiles[idx - 1], MergeVideoFiles[idx]) = (MergeVideoFiles[idx], MergeVideoFiles[idx - 1]);
        MergeSelectedIndex = idx - 1;
        SyncMergeTextFromList();
    }

    [RelayCommand]
    private void MoveDownMerge()
    {
        if (MergeSelectedIndex < 0 || MergeSelectedIndex >= MergeVideoFiles.Count - 1)
        {
            return;
        }

        var idx = MergeSelectedIndex;
        (MergeVideoFiles[idx + 1], MergeVideoFiles[idx]) = (MergeVideoFiles[idx], MergeVideoFiles[idx + 1]);
        MergeSelectedIndex = idx + 1;
        SyncMergeTextFromList();
    }

    [RelayCommand]
    private void ClearWeeklyList()
    {
        WeeklyVideoFiles.Clear();
        WeeklySelectedIndex = -1;
        SyncWeeklyTextFromList();
        StatusText = "已清空录屏整理列表";
    }

    [RelayCommand]
    private void RemoveSelectedWeekly()
    {
        if (WeeklySelectedIndex < 0 || WeeklySelectedIndex >= WeeklyVideoFiles.Count)
        {
            StatusText = "请先选择要删除的录屏视频";
            return;
        }

        WeeklyVideoFiles.RemoveAt(WeeklySelectedIndex);
        if (WeeklySelectedIndex >= WeeklyVideoFiles.Count)
        {
            WeeklySelectedIndex = WeeklyVideoFiles.Count - 1;
        }

        SyncWeeklyTextFromList();
        StatusText = "已删除选中录屏视频";
    }

    [RelayCommand]
    private void MoveUpWeekly()
    {
        if (WeeklySelectedIndex <= 0 || WeeklySelectedIndex >= WeeklyVideoFiles.Count)
        {
            return;
        }

        var idx = WeeklySelectedIndex;
        (WeeklyVideoFiles[idx - 1], WeeklyVideoFiles[idx]) = (WeeklyVideoFiles[idx], WeeklyVideoFiles[idx - 1]);
        WeeklySelectedIndex = idx - 1;
        SyncWeeklyTextFromList();
    }

    [RelayCommand]
    private void MoveDownWeekly()
    {
        if (WeeklySelectedIndex < 0 || WeeklySelectedIndex >= WeeklyVideoFiles.Count - 1)
        {
            return;
        }

        var idx = WeeklySelectedIndex;
        (WeeklyVideoFiles[idx + 1], WeeklyVideoFiles[idx]) = (WeeklyVideoFiles[idx], WeeklyVideoFiles[idx + 1]);
        WeeklySelectedIndex = idx + 1;
        SyncWeeklyTextFromList();
    }

    [RelayCommand]
    private void OpenCurrentOutputFolder()
    {
        var path = SelectedTabIndex switch
        {
            0 => _paths.SegmentOutput,
            1 => _paths.CropOutput,
            2 => _paths.MergeOutput,
            3 => _paths.DocOutput,
            4 => _paths.WeeklyOutput,
            _ => _paths.RootOutput
        };

        TryOpenFolder(path);
    }

    [RelayCommand]
    private void JumpNextStep()
    {
        try
        {
            switch (SelectedTabIndex)
            {
                case 0:
                {
                    var candidates = SegmentLastOutputs.Count > 0
                        ? SegmentLastOutputs.Where(File.Exists).ToList()
                        : ParsePathLines(SegmentVideoPath).Where(File.Exists).ToList();
                    if (!candidates.Any())
                    {
                        StatusText = "当前没有可传递的多段截取输入/输出";
                        return;
                    }

                    CropVideoPathsText = ComposePathText(candidates, !OverwriteCrossTabTransfer ? CropVideoPathsText : null);
                    SelectedTabIndex = 1;
                    StatusText = "已传递到画幅裁剪";
                    break;
                }
                case 1:
                {
                    var candidates = CropLastOutputs.Count > 0
                        ? CropLastOutputs.Where(File.Exists).ToList()
                        : ParsePathLines(CropVideoPathsText).Where(File.Exists).ToList();
                    if (!candidates.Any())
                    {
                        StatusText = "当前没有可传递的画幅裁剪输入/输出";
                        return;
                    }

                    MergeVideoPathsText = ComposePathText(candidates, !OverwriteCrossTabTransfer ? MergeVideoPathsText : null);
                    DocVideoPathsText = ComposePathText(candidates, !OverwriteCrossTabTransfer ? DocVideoPathsText : null);
                    SelectedTabIndex = 2;
                    StatusText = "已传递到视频合并和文档生成";
                    break;
                }
                case 2:
                    SelectedTabIndex = 3;
                    StatusText = "已切换到文档生成";
                    break;
                case 3:
                    _ = RunDocTransferAsync();
                    break;
                default:
                    StatusText = "当前页签不支持跳转";
                    break;
            }
        }
        catch (Exception ex)
        {
            _log.Error("跨页传递失败", ex);
            StatusText = $"跨页传递失败: {ex.Message}";
        }
    }
}
