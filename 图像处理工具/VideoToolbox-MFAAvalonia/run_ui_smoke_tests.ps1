Param(
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$TestProject = Join-Path $ProjectRoot "tests\VideoToolbox.SmokeTests\VideoToolbox.SmokeTests.csproj"

if (-not (Test-Path $TestProject)) {
    throw "测试工程不存在: $TestProject"
}

Write-Host "==> 运行 UI 自动化冒烟回归 ($Configuration)"
dotnet test "$TestProject" -c $Configuration --nologo --verbosity minimal
