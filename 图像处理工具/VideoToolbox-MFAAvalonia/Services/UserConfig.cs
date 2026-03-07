namespace VideoToolbox.Services;

public sealed class UserConfig
{
    public string ThemeMode { get; set; } = "跟随系统";

    // "overwrite" or "append"
    public string CrossTabTransferMode { get; set; } = "overwrite";
}
