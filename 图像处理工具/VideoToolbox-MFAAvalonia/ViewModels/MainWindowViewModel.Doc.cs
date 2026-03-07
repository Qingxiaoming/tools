using CommunityToolkit.Mvvm.Input;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace VideoToolbox.ViewModels;

public partial class MainWindowViewModel
{
    [RelayCommand]
    private async Task RunDocGenerationAsync()
    {
        const int tab = 3;
        if (IsBusy)
        {
            return;
        }

        var files = ParsePathLines(DocVideoPathsText).Where(File.Exists).ToList();
        if (!files.Any())
        {
            SetTabStatus(tab, "文档生成列表为空");
            return;
        }

        SetTabBusy(tab, true);
        _docGeneratedMdNames.Clear();
        var success = 0;
        var fail = 0;
        try
        {
            foreach (var path in files)
            {
                var name = Path.GetFileName(path);
                var ops = ExtractOperatorList(name);
                var nature = ExtractNature(name);
                var stage = ExtractStageName(name);
                var mdPath = Path.Combine(_paths.DocOutput, $"{stage}.md");
                var opsYaml = string.Join(Environment.NewLine, ops.Select(x => $"  - {x}"));
                var content = $"""
---
属于活动:
  - {DocActivity}
是否完成: true
bv号: {DocBv}
关卡难度:
  - {nature}
备注: 无
参战干员:
{opsYaml}
攻略者: 项泓小时候/
创建时间: {DateTime.Today:yyyy/MM/dd}
---
# 本地视频
![[{name}]]
""";
                await File.WriteAllTextAsync(mdPath, content, Encoding.UTF8);
                _docGeneratedMdNames.Add(Path.GetFileName(mdPath));
                success++;
                LogToTab(tab, $"已生成文档: {Path.GetFileName(mdPath)}");
            }
        }
        catch (Exception ex)
        {
            _log.Error("文档生成异常", ex);
            fail++;
        }

        SetTabBusy(tab, false);
        SetTabStatus(tab, $"文档生成完成: 成功 {success} 个, 失败 {fail} 个");
    }

    [RelayCommand]
    private Task RunDocTransferAsync() => RunDocTransferInternalAsync();

    private async Task RunDocTransferInternalAsync()
    {
        const int tab = 3;
        if (IsBusy)
        {
            return;
        }

        SetTabBusy(tab, true);
        var movedDocs = 0;
        var movedVideos = 0;
        var skipped = 0;
        try
        {
            var mdFiles = Directory.GetFiles(_paths.DocOutput, "*.md")
                .Where(p => _docGeneratedMdNames.Count == 0 || _docGeneratedMdNames.Contains(Path.GetFileName(p)))
                .ToList();
            if (!mdFiles.Any())
            {
                SetTabStatus(tab, "没有本次生成可转运文档");
                SetTabBusy(tab, false);
                return;
            }

            var inputVideos = ParsePathLines(DocVideoPathsText)
                .Select(p => (Name: Path.GetFileName(p), Path: p))
                .Where(x => !string.IsNullOrWhiteSpace(x.Name))
                .ToDictionary(x => x.Name!, x => x.Path, StringComparer.OrdinalIgnoreCase);

            foreach (var md in mdFiles)
            {
                var docName = Path.GetFileName(md);
                var targetMd = Path.Combine(_paths.DocTransferDocDir, docName);
                if (File.Exists(targetMd))
                {
                    skipped++;
                    LogToTab(tab, $"{docName} 跳过: 目标文档已存在");
                    continue;
                }

                var text = await File.ReadAllTextAsync(md, Encoding.UTF8);
                var refs = Regex.Matches(text, @"!\[\[(.+?)\]\]")
                    .Select(m => m.Groups[1].Value.Trim())
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .ToList();

                var resolved = new List<(string RefName, string Source, string Target)>();
                var invalid = false;
                foreach (var r in refs)
                {
                    var source = Path.Combine(_paths.DocOutput, r);
                    if (!File.Exists(source))
                    {
                        if (!inputVideos.TryGetValue(r, out source) || !File.Exists(source))
                        {
                            invalid = true;
                            LogToTab(tab, $"{docName} 跳过: 引用视频缺失 {r}");
                            break;
                        }
                    }

                    var target = Path.Combine(_paths.DocTransferMediaDir, r);
                    if (File.Exists(target))
                    {
                        invalid = true;
                        LogToTab(tab, $"{docName} 跳过: 目标视频已存在 {r}");
                        break;
                    }

                    resolved.Add((r, source, target));
                }

                if (invalid)
                {
                    skipped++;
                    continue;
                }

                var doneMoves = new List<(string Cur, string Rollback)>();
                try
                {
                    File.Move(md, targetMd);
                    doneMoves.Add((targetMd, md));
                    foreach (var item in resolved)
                    {
                        File.Move(item.Source, item.Target);
                        doneMoves.Add((item.Target, item.Source));
                    }

                    movedDocs++;
                    movedVideos += resolved.Count;
                }
                catch (Exception ex)
                {
                    _log.Error($"{docName} 转运失败，执行回滚", ex);
                    foreach (var mv in doneMoves.AsEnumerable().Reverse())
                    {
                        try
                        {
                            if (File.Exists(mv.Cur))
                            {
                                File.Move(mv.Cur, mv.Rollback);
                            }
                        }
                        catch (Exception re)
                        {
                            _log.Error($"回滚失败: {mv.Cur}", re);
                        }
                    }

                    skipped++;
                }
            }
        }
        catch (Exception ex)
        {
            _log.Error("文档转运异常", ex);
            SetTabStatus(tab, $"文档转运失败: {ex.Message}");
            SetTabBusy(tab, false);
            return;
        }

        SetTabBusy(tab, false);
        SetTabStatus(tab, $"文档转运完成: 文档 {movedDocs} 个, 视频 {movedVideos} 个, 跳过 {skipped} 个");
    }
}
