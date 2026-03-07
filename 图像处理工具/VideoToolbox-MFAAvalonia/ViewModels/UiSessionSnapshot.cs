namespace VideoToolbox.ViewModels;

public sealed class UiSessionSnapshot
{
    public int SelectedTabIndex { get; set; }
    public string SegmentVideoPath { get; set; } = string.Empty;
    public string SegmentBatchText { get; set; } = string.Empty;
    public bool SegmentPreciseCrop { get; set; }

    public string CropVideoPathsText { get; set; } = string.Empty;
    public int CropSelectedIndex { get; set; } = -1;
    public string CropRoiText { get; set; } = string.Empty;

    public string MergeVideoPathsText { get; set; } = string.Empty;
    public int MergeSelectedIndex { get; set; } = -1;
    public string MergeAudioPath { get; set; } = string.Empty;
    public string MergeAudioMode { get; set; } = "保持原音频";
    public string MergeOutputName { get; set; } = "合并视频";
    public string MergeSpeed { get; set; } = "1.0";

    public string DocVideoPathsText { get; set; } = string.Empty;
    public int DocSelectedIndex { get; set; } = -1;
    public string DocActivity { get; set; } = string.Empty;
    public string DocBv { get; set; } = string.Empty;

    public string WeeklyVideoPathsText { get; set; } = string.Empty;
    public int WeeklySelectedIndex { get; set; } = -1;
}
