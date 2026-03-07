using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Controls;
using Avalonia.Data.Core;
using Avalonia.Data.Core.Plugins;
using System;
using System.Linq;
using Avalonia.Markup.Xaml;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using Microsoft.Extensions.DependencyInjection;
using VideoToolbox.ViewModels;
using VideoToolbox.Views;
using VideoToolbox.Services;

namespace VideoToolbox;

public partial class App : Application
{
    public static IServiceProvider Services { get; private set; } = default!;
    private IClassicDesktopStyleApplicationLifetime? _desktop;
    private TrayIcon? _trayIcon;
    private bool _allowRealClose;
    private readonly Stopwatch _trayClickWatch = new();

    public override void Initialize()
    {
        AvaloniaXamlLoader.Load(this);
    }

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            _desktop = desktop;
            DisableAvaloniaDataAnnotationValidation();
            var services = new ServiceCollection();
            ConfigureServices(services);
            Services = services.BuildServiceProvider();
            var vm = Services.GetRequiredService<MainWindowViewModel>();
            TryRestoreSession(vm, TryGetArgValue(desktop.Args, "--session"));
            vm.RequestRestartForConfigChange += RestartWithSessionSnapshot;
            var mainWindow = Services.GetRequiredService<MainWindow>();
            mainWindow.Closing += MainWindowOnClosing;
            mainWindow.PropertyChanged += (_, args) =>
            {
                if (args.Property == Window.WindowStateProperty && mainWindow.WindowState == WindowState.Minimized)
                {
                    HideToTray();
                }
            };
            desktop.MainWindow = mainWindow;
            SetupTrayIcon();
        }

        base.OnFrameworkInitializationCompleted();
    }

    private static void ConfigureServices(ServiceCollection services)
    {
        services.AddSingleton<AppPaths>();
        services.AddSingleton<ILogService, FileLogService>();
        services.AddSingleton<ProcessService>();
        services.AddSingleton<UserConfigService>();
        services.AddSingleton<MainWindowViewModel>();
        services.AddSingleton<MainWindow>();
    }

    private void DisableAvaloniaDataAnnotationValidation()
    {
        var dataValidationPluginsToRemove =
            BindingPlugins.DataValidators.OfType<DataAnnotationsValidationPlugin>().ToArray();

        foreach (var plugin in dataValidationPluginsToRemove)
        {
            BindingPlugins.DataValidators.Remove(plugin);
        }
    }

    private void SetupTrayIcon()
    {
        if (_desktop?.MainWindow is null)
        {
            return;
        }

        var showItem = new NativeMenuItem("显示主窗口");
        showItem.Click += (_, _) => ShowMainWindow();

        var minimizeItem = new NativeMenuItem("最小化到托盘");
        minimizeItem.Click += (_, _) => HideToTray();

        var dragMoveItem = new NativeMenuItem("配置模式")
        {
            ToggleType = NativeMenuItemToggleType.CheckBox,
            IsChecked = false
        };
        dragMoveItem.Click += (_, _) =>
        {
            if (_desktop?.MainWindow is MainWindow win)
            {
                win.SetDragMoveEnabled(dragMoveItem.IsChecked);
            }
        };

        var exitItem = new NativeMenuItem("退出");
        exitItem.Click += (_, _) => ExitFromTray();

        var menu = new NativeMenu();
        menu.Items.Add(showItem);
        menu.Items.Add(minimizeItem);
        menu.Items.Add(dragMoveItem);
        menu.Items.Add(new NativeMenuItemSeparator());
        menu.Items.Add(exitItem);

        _trayIcon = new TrayIcon
        {
            ToolTipText = "VideoToolbox",
            Menu = menu,
            IsVisible = true,
            Icon = _desktop.MainWindow.Icon
        };
        if (_desktop.MainWindow is MainWindow mainWindow)
        {
            mainWindow.SetDragMoveEnabled(false);
        }
        _trayIcon.Clicked += (_, _) =>
        {
            // Avalonia TrayIcon on Windows has no dedicated double-click event.
            // Use timing window to detect double click and toggle window visibility.
            if (_trayClickWatch.IsRunning && _trayClickWatch.ElapsedMilliseconds <= 400)
            {
                _trayClickWatch.Reset();
                ToggleMainWindowVisibility();
                return;
            }

            _trayClickWatch.Restart();
        };
    }

    private void MainWindowOnClosing(object? sender, WindowClosingEventArgs e)
    {
        if (_allowRealClose)
        {
            return;
        }

        e.Cancel = true;
        HideToTray();
    }

    private void HideToTray()
    {
        if (_desktop?.MainWindow is not { } mainWindow)
        {
            return;
        }

        if (mainWindow is MainWindow mw)
        {
            mw.SaveLayout();
        }
        mainWindow.ShowInTaskbar = false;
        mainWindow.Hide();
    }

    private void ShowMainWindow()
    {
        if (_desktop?.MainWindow is not { } mainWindow)
        {
            return;
        }

        mainWindow.ShowInTaskbar = true;
        mainWindow.Show();
        mainWindow.WindowState = WindowState.Normal;
        mainWindow.Activate();
    }

    private void ToggleMainWindowVisibility()
    {
        if (_desktop?.MainWindow is not { } mainWindow)
        {
            return;
        }

        if (!mainWindow.IsVisible || !mainWindow.ShowInTaskbar)
        {
            ShowMainWindow();
        }
        else
        {
            HideToTray();
        }
    }

    private void ExitFromTray()
    {
        _allowRealClose = true;
        if (_desktop?.MainWindow is MainWindow mw)
        {
            mw.SaveLayout();
        }
        _trayIcon?.Dispose();
        _trayIcon = null;

        if (_desktop?.MainWindow is { } mainWindow)
        {
            mainWindow.Close();
        }

        _desktop?.Shutdown();
    }

    private void RestartWithSessionSnapshot()
    {
        try
        {
            if (_desktop?.MainWindow is MainWindow mw)
            {
                mw.SaveLayout();
            }

            if (_desktop?.MainWindow?.DataContext is not MainWindowViewModel vm)
            {
                return;
            }

            var snapshot = vm.CaptureSessionSnapshot();
            var sessionPath = Path.Combine(Path.GetTempPath(), $"videotoolbox-session-{Guid.NewGuid():N}.json");
            File.WriteAllText(sessionPath, JsonSerializer.Serialize(snapshot));

            var exePath = Environment.ProcessPath;
            if (string.IsNullOrWhiteSpace(exePath))
            {
                return;
            }

            Process.Start(new ProcessStartInfo(exePath, $"--session \"{sessionPath}\"") { UseShellExecute = true });
            ExitFromTray();
        }
        catch
        {
            // ignore restart failure to avoid blocking current run
        }
    }

    private static void TryRestoreSession(MainWindowViewModel vm, string? sessionPath)
    {
        if (string.IsNullOrWhiteSpace(sessionPath) || !File.Exists(sessionPath))
        {
            return;
        }

        try
        {
            var text = File.ReadAllText(sessionPath);
            var snapshot = JsonSerializer.Deserialize<UiSessionSnapshot>(text);
            vm.RestoreSessionSnapshot(snapshot);
        }
        catch
        {
            // ignore invalid snapshot
        }
        finally
        {
            try
            {
                File.Delete(sessionPath);
            }
            catch
            {
                // ignore
            }
        }
    }

    private static string? TryGetArgValue(string[]? args, string key)
    {
        if (args is null || args.Length == 0)
        {
            return null;
        }

        for (var i = 0; i < args.Length; i++)
        {
            if (!string.Equals(args[i], key, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (i + 1 < args.Length)
            {
                return args[i + 1];
            }
        }

        return null;
    }
}