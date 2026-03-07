using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Shapes;
using Avalonia.Input;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using System;

namespace VideoToolbox.Views.Windows;

public sealed class RoiSelectorWindow : Window
{
    private readonly Canvas _overlay;
    private readonly Rectangle _rect;
    private readonly Bitmap _bitmap;
    private readonly double _scaleX;
    private readonly double _scaleY;
    private Point? _startPoint;

    public RoiSelectorWindow(string previewImagePath, int originalWidth, int originalHeight)
    {
        Title = "框选ROI（拖拽后点确认）";
        Width = 1100;
        Height = 780;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;

        _bitmap = new Bitmap(previewImagePath);
        _scaleX = originalWidth / (double)_bitmap.PixelSize.Width;
        _scaleY = originalHeight / (double)_bitmap.PixelSize.Height;

        var image = new Image
        {
            Source = _bitmap,
            Stretch = Stretch.None,
            HorizontalAlignment = HorizontalAlignment.Left,
            VerticalAlignment = VerticalAlignment.Top
        };

        _rect = new Rectangle
        {
            Stroke = Brushes.Red,
            StrokeThickness = 2,
            Fill = new SolidColorBrush(Color.FromArgb(50, 255, 0, 0)),
            IsVisible = false
        };

        _overlay = new Canvas
        {
            Width = _bitmap.Size.Width,
            Height = _bitmap.Size.Height,
            Background = Brushes.Transparent
        };
        _overlay.Children.Add(_rect);
        _overlay.PointerPressed += OverlayOnPointerPressed;
        _overlay.PointerMoved += OverlayOnPointerMoved;
        _overlay.PointerReleased += OverlayOnPointerReleased;

        var layer = new Grid
        {
            Width = _bitmap.Size.Width,
            Height = _bitmap.Size.Height
        };
        layer.Children.Add(image);
        layer.Children.Add(_overlay);

        var scroll = new ScrollViewer { Content = layer };

        var confirm = new Button { Content = "确认", MinWidth = 100 };
        confirm.Click += (_, _) => ConfirmSelection();
        var cancel = new Button { Content = "取消", MinWidth = 100 };
        cancel.Click += (_, _) => Close(null);
        var tips = new TextBlock
        {
            Text = "提示：拖拽框出保留区域，确认后自动换算为原始分辨率坐标",
            VerticalAlignment = VerticalAlignment.Center
        };

        var actions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
            Children = { tips, confirm, cancel }
        };

        var actionBorder = new Border
        {
            Padding = new Thickness(8),
            BorderBrush = Brushes.Gray,
            BorderThickness = new Thickness(1, 1, 1, 0),
            Child = actions
        };
        Grid.SetRow(actionBorder, 1);

        Content = new Grid
        {
            RowDefinitions = new RowDefinitions("*,Auto"),
            Children = { scroll, actionBorder }
        };

        Closed += (_, _) => _bitmap.Dispose();
    }

    private void OverlayOnPointerPressed(object? sender, PointerPressedEventArgs e)
    {
        var p = e.GetPosition(_overlay);
        _startPoint = p;
        Canvas.SetLeft(_rect, p.X);
        Canvas.SetTop(_rect, p.Y);
        _rect.Width = 0;
        _rect.Height = 0;
        _rect.IsVisible = true;
    }

    private void OverlayOnPointerMoved(object? sender, PointerEventArgs e)
    {
        if (_startPoint is null || !_rect.IsVisible)
        {
            return;
        }

        var p = e.GetPosition(_overlay);
        var x = Math.Min(_startPoint.Value.X, p.X);
        var y = Math.Min(_startPoint.Value.Y, p.Y);
        var w = Math.Abs(p.X - _startPoint.Value.X);
        var h = Math.Abs(p.Y - _startPoint.Value.Y);
        Canvas.SetLeft(_rect, x);
        Canvas.SetTop(_rect, y);
        _rect.Width = w;
        _rect.Height = h;
    }

    private void OverlayOnPointerReleased(object? sender, PointerReleasedEventArgs e)
    {
        // Release is intentionally no-op. Geometry is finalized on confirm.
    }

    private void ConfirmSelection()
    {
        if (!_rect.IsVisible || _rect.Width < 1 || _rect.Height < 1)
        {
            Close(null);
            return;
        }

        var left = Canvas.GetLeft(_rect);
        var top = Canvas.GetTop(_rect);
        var width = _rect.Width;
        var height = _rect.Height;

        // 防止越界导致 ffmpeg crop 参数非法。
        left = Math.Clamp(left, 0, _bitmap.Size.Width - 1);
        top = Math.Clamp(top, 0, _bitmap.Size.Height - 1);
        width = Math.Clamp(width, 1, _bitmap.Size.Width - left);
        height = Math.Clamp(height, 1, _bitmap.Size.Height - top);

        var x = (int)Math.Round(left * _scaleX);
        var y = (int)Math.Round(top * _scaleY);
        var w = (int)Math.Round(width * _scaleX);
        var h = (int)Math.Round(height * _scaleY);

        x = Math.Max(0, x);
        y = Math.Max(0, y);
        w = Math.Max(1, w);
        h = Math.Max(1, h);

        Close((x, y, w, h));
    }
}
