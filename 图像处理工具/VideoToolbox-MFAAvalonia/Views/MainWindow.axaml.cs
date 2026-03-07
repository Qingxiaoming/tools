using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Input;
using Avalonia;
using Avalonia.VisualTree;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using VideoToolbox.Services;
using VideoToolbox.ViewModels;

namespace VideoToolbox.Views;

public partial class MainWindow : Window
{
    private const double MinTabWidth = 80;
    private const double MaxTabWidth = 260;
    private const double MinRightPanelWidth = 96;
    private const double MaxRightPanelWidth = 260;
    private bool _dragMoveEnabled;
    private bool _isDraggingLeftSplitter;
    private bool _isDraggingRightSplitter;
    private double _dragStartX;
    private double _startTabWidth;
    private double _startRightPanelWidth;
    private Border? _titleBar;
    private TextBlock? _headerTitleText;
    private MainWindowViewModel? _currentVm;
    private readonly List<Grid> _pageLayoutGrids = new();
    private ColumnDefinition? _navColumn;
    private Grid? _activeRightDragGrid;
    private int _leftMoveLogCounter;
    private int _rightMoveLogCounter;
    private string? _layoutFilePath;
    private WindowLayoutState? _pendingLayout;
    private Timer? _saveDebounce;
    private bool _layoutLoaded;

    public MainWindow()
    {
        InitializeComponent();
        DragDrop.SetAllowDrop(this, true);
        AddHandler(DragDrop.DragOverEvent, OnDragOver);
        AddHandler(DragDrop.DropEvent, OnDrop);
        _titleBar = this.FindControl<Border>("TitleBar");
        _headerTitleText = this.FindControl<TextBlock>("HeaderTitleText");
        if (_titleBar is not null)
        {
            _titleBar.PointerPressed += OnTitleBarPointerPressed;
        }
        if (_headerTitleText is not null)
        {
            _headerTitleText.PointerReleased += OnHeaderTitlePointerReleased;
        }
        _dragMoveEnabled = false;
        DataContextChanged += OnDataContextChanged;
        Activated += OnWindowActivated;
        Opened += OnWindowOpened;
    }

    public MainWindow(MainWindowViewModel vm, AppPaths paths)
        : this()
    {
        _layoutFilePath = paths.LayoutFile;
        DataContext = vm;
        LoadLayoutGeometry();
    }

    /// <summary>
    /// Load position and size from layout.json BEFORE the window is shown.
    /// Column widths are deferred to OnWindowOpened because the visual tree isn't ready yet.
    /// </summary>
    private void LoadLayoutGeometry()
    {
        if (string.IsNullOrWhiteSpace(_layoutFilePath) || !File.Exists(_layoutFilePath))
        {
            return;
        }

        try
        {
            var json = File.ReadAllText(_layoutFilePath);
            var state = JsonSerializer.Deserialize<WindowLayoutState>(json);
            if (state is null)
            {
                return;
            }

            _pendingLayout = state;
            Position = new PixelPoint(state.X, state.Y);
            Width = state.Width;
            Height = state.Height;
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Layout] LoadGeometry failed: {ex.Message}");
        }
    }

    public void SaveLayout()
    {
        if (string.IsNullOrWhiteSpace(_layoutFilePath))
        {
            return;
        }

        try
        {
            var state = new WindowLayoutState
            {
                X = Position.X,
                Y = Position.Y,
                Width = Width,
                Height = Height,
                NavColumnWidth = GetTabWidth(),
                RightPanelWidth = GetRightPanelWidth()
            };
            var json = JsonSerializer.Serialize(state, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(_layoutFilePath, json);
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Layout] Save failed: {ex.Message}");
        }
    }

    private void ScheduleDebouncedSave()
    {
        if (!_layoutLoaded || string.IsNullOrWhiteSpace(_layoutFilePath))
        {
            return;
        }

        _saveDebounce?.Dispose();
        _saveDebounce = new Timer(_ =>
        {
            Avalonia.Threading.Dispatcher.UIThread.Post(SaveLayout);
        }, null, 800, Timeout.Infinite);
    }

    private void OnDataContextChanged(object? sender, System.EventArgs e)
    {
        _currentVm = DataContext as MainWindowViewModel;
    }

    private void OnDragOver(object? sender, DragEventArgs e)
    {
        e.DragEffects = e.DataTransfer.TryGetFiles() is { Length: > 0 }
            ? DragDropEffects.Copy
            : DragDropEffects.None;
        e.Handled = true;
    }

    private void OnDrop(object? sender, DragEventArgs e)
    {
        if (DataContext is not MainWindowViewModel vm)
        {
            return;
        }

        var files = e.DataTransfer.TryGetFiles()?
            .Select(x => x.Path.LocalPath)
            .Where(x => !string.IsNullOrWhiteSpace(x))
            .ToList();

        if (files is { Count: > 0 })
        {
            vm.HandleDroppedFiles(files);
        }
    }

    private void OnTitleBarPointerPressed(object? sender, PointerPressedEventArgs e)
    {
        if (_dragMoveEnabled && e.GetCurrentPoint(this).Properties.IsLeftButtonPressed)
        {
            BeginMoveDrag(e);
        }
    }

    private void OnHeaderTitlePointerReleased(object? sender, PointerReleasedEventArgs e)
    {
        if (DataContext is not MainWindowViewModel vm)
        {
            return;
        }

        vm.OpenConfigFileCommand.Execute(null);
        e.Handled = true;
    }

    private void OnWindowActivated(object? sender, System.EventArgs e)
    {
        if (DataContext is not MainWindowViewModel vm)
        {
            return;
        }

        vm.CheckConfigChangeAndRequestRestart();
    }

    public void SetDragMoveEnabled(bool enabled)
    {
        _dragMoveEnabled = enabled;
        if (enabled)
            Classes.Add("config-mode");
        else
            Classes.Remove("config-mode");
    }

    private void OnEdgePointerPressed(object? sender, PointerPressedEventArgs e)
    {
        if (!_dragMoveEnabled || !e.GetCurrentPoint(this).Properties.IsLeftButtonPressed)
        {
            return;
        }

        var edge = (sender as Control)?.Tag?.ToString() switch
        {
            "N" => WindowEdge.North,
            "S" => WindowEdge.South,
            "W" => WindowEdge.West,
            "E" => WindowEdge.East,
            "NW" => WindowEdge.NorthWest,
            "NE" => WindowEdge.NorthEast,
            "SW" => WindowEdge.SouthWest,
            "SE" => WindowEdge.SouthEast,
            _ => (WindowEdge?)null
        };

        if (edge.HasValue)
        {
            BeginResizeDrag(edge.Value, e);
        }
    }

    private void OnWindowOpened(object? sender, EventArgs e)
    {
        CacheResizableTargets();
        CacheNavColumn();

        if (_pendingLayout is not null)
        {
            ApplyTabWidth(_pendingLayout.NavColumnWidth);
            ApplyRightPanelWidth(_pendingLayout.RightPanelWidth, null);
            _pendingLayout = null;
        }
        else
        {
            ApplyRightPanelWidth(GetRightPanelWidth(), null);
        }

        _layoutLoaded = true;

        PositionChanged += (_, _) => ScheduleDebouncedSave();
        PropertyChanged += (_, args) =>
        {
            if (args.Property == WidthProperty || args.Property == HeightProperty)
            {
                ScheduleDebouncedSave();
            }
        };
    }

    private void OnLeftSplitterPointerPressed(object? sender, PointerPressedEventArgs e)
    {
        if (!_dragMoveEnabled || !e.GetCurrentPoint(this).Properties.IsLeftButtonPressed)
        {
            return;
        }

        _isDraggingLeftSplitter = true;
        _leftMoveLogCounter = 0;
        _dragStartX = e.GetPosition(this).X;
        _startTabWidth = GetTabWidth();
        if (sender is IInputElement element)
        {
            e.Pointer.Capture(element);
        }

        e.Handled = true;
    }

    private void OnLeftSplitterPointerMoved(object? sender, PointerEventArgs e)
    {
        if (!_isDraggingLeftSplitter)
        {
            return;
        }

        var delta = e.GetPosition(this).X - _dragStartX;
        var newWidth = Math.Clamp(_startTabWidth + delta, MinTabWidth, MaxTabWidth);
        ApplyTabWidth(newWidth);
        _leftMoveLogCounter++;
        e.Handled = true;
    }

    private void OnLeftSplitterPointerReleased(object? sender, PointerReleasedEventArgs e)
    {
        if (!_isDraggingLeftSplitter)
        {
            return;
        }

        _isDraggingLeftSplitter = false;
        if (sender is IInputElement)
        {
            e.Pointer.Capture(null);
        }

        ScheduleDebouncedSave();
        e.Handled = true;
    }

    private void OnRightSplitterPointerPressed(object? sender, PointerPressedEventArgs e)
    {
        if (!_dragMoveEnabled || !e.GetCurrentPoint(this).Properties.IsLeftButtonPressed)
        {
            return;
        }

        _isDraggingRightSplitter = true;
        _rightMoveLogCounter = 0;
        _dragStartX = e.GetPosition(this).X;
        _activeRightDragGrid = (sender as Visual)?.FindAncestorOfType<Grid>();
        _startRightPanelWidth = GetRightPanelWidth(_activeRightDragGrid);
        if (sender is IInputElement element)
        {
            e.Pointer.Capture(element);
        }

        e.Handled = true;
    }

    private void OnRightSplitterPointerMoved(object? sender, PointerEventArgs e)
    {
        if (!_isDraggingRightSplitter)
        {
            return;
        }

        var delta = e.GetPosition(this).X - _dragStartX;
        var newWidth = Math.Clamp(_startRightPanelWidth - delta, MinRightPanelWidth, MaxRightPanelWidth);
        ApplyRightPanelWidth(newWidth, _activeRightDragGrid);
        _rightMoveLogCounter++;
        e.Handled = true;
    }

    private void OnRightSplitterPointerReleased(object? sender, PointerReleasedEventArgs e)
    {
        if (!_isDraggingRightSplitter)
        {
            return;
        }

        _isDraggingRightSplitter = false;
        var finalWidth = GetRightPanelWidth(_activeRightDragGrid);
        ApplyRightPanelWidth(finalWidth, null);
        _activeRightDragGrid = null;
        if (sender is IInputElement)
        {
            e.Pointer.Capture(null);
        }

        ScheduleDebouncedSave();
        e.Handled = true;
    }

    private double GetRightPanelWidth(Grid? grid = null)
    {
        if (grid is not null && grid.ColumnDefinitions.Count > 2)
        {
            var targetCol = grid.ColumnDefinitions[2];
            if (targetCol.Width.IsAbsolute)
            {
                return targetCol.Width.Value;
            }
        }

        if (_pageLayoutGrids.Count > 0 && _pageLayoutGrids[0].ColumnDefinitions.Count > 2)
        {
            var col = _pageLayoutGrids[0].ColumnDefinitions[2];
            if (col.Width.IsAbsolute)
            {
                return col.Width.Value;
            }
        }

        if (Resources.TryGetResource("MainRightColumnWidth", null, out var value) &&
            value is GridLength gridLength &&
            gridLength.IsAbsolute)
        {
            return gridLength.Value;
        }

        return 132;
    }

    private double GetTabWidth()
    {
        if (_navColumn is not null && _navColumn.Width.IsAbsolute)
        {
            return _navColumn.Width.Value;
        }

        return 175;
    }

    private void CacheResizableTargets()
    {
        _pageLayoutGrids.Clear();
        AddPageGrid("SegmentLayoutGrid");
        AddPageGrid("CropLayoutGrid");
        AddPageGrid("MergeLayoutGrid");
        AddPageGrid("DocLayoutGrid");
        AddPageGrid("WeeklyLayoutGrid");
    }

    private void AddPageGrid(string name)
    {
        var grid = this.FindControl<Grid>(name);
        if (grid is not null)
        {
            _pageLayoutGrids.Add(grid);
        }
    }

    private void ApplyRightPanelWidth(double width, Grid? targetGrid = null)
    {
        var gridLength = new GridLength(width, GridUnitType.Pixel);
        Resources["MainRightColumnWidth"] = gridLength;
        if (targetGrid is not null)
        {
            if (targetGrid.ColumnDefinitions.Count > 2)
            {
                targetGrid.ColumnDefinitions[2].Width = gridLength;
            }
            return;
        }

        foreach (var grid in _pageLayoutGrids)
        {
            if (grid.ColumnDefinitions.Count > 2)
            {
                grid.ColumnDefinitions[2].Width = gridLength;
            }
        }
    }

    private void CacheNavColumn()
    {
        var grid = this.FindControl<Grid>("NavContentGrid");
        if (grid is not null && grid.ColumnDefinitions.Count > 0)
        {
            _navColumn = grid.ColumnDefinitions[0];
        }
    }

    private void ApplyTabWidth(double width)
    {
        if (_navColumn is not null)
        {
            _navColumn.Width = new GridLength(width, GridUnitType.Pixel);
        }
    }
}
