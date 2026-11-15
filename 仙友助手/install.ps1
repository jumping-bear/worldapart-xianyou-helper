$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $here '安装文件'

function Find-GameDir([string]$hint) {
    if ($hint -and (Test-Path (Join-Path $hint 'WorldApart.exe'))) { return $hint }
    $steam = $null
    foreach ($k in @('HKLM:\SOFTWARE\WOW6432Node\Valve\Steam', 'HKCU:\SOFTWARE\Valve\Steam')) {
        try {
            $p = Get-ItemProperty $k -ErrorAction Stop
            if ($p.InstallPath) { $steam = $p.InstallPath }
            elseif ($p.SteamPath) { $steam = $p.SteamPath }
            if ($steam) { break }
        } catch { }
    }
    $libs = @()
    if ($steam) {
        $libs += $steam
        $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
        if (Test-Path $vdf) {
            foreach ($line in Get-Content $vdf) {
                if ($line -match '"path"\s+"([^"]+)"') { $libs += ($matches[1] -replace '\\\\', '\') }
            }
        }
    }
    foreach ($d in @('C:', 'D:', 'E:', 'F:', 'G:')) {
        $libs += "$d\SteamLibrary"
        $libs += "$d\Program Files (x86)\Steam"
    }
    foreach ($l in ($libs | Where-Object { $_ } | Select-Object -Unique)) {
        $g = Join-Path $l 'steamapps\common\A1'
        if (Test-Path (Join-Path $g 'WorldApart.exe')) { return $g }
    }
    return $null
}

Write-Host '=============================================' -ForegroundColor Cyan
Write-Host '  不问凡尘 · 触摸进度查询工具 一键安装' -ForegroundColor Cyan
Write-Host '=============================================' -ForegroundColor Cyan
Write-Host ''

if (Get-Process -Name WorldApart -ErrorAction SilentlyContinue) {
    Write-Host '检测到游戏正在运行，请先退出游戏（任务管理器结束 WorldApart.exe）再安装。' -ForegroundColor Red
    exit 1
}

$game = Find-GameDir($args[0])
while (-not $game) {
    Write-Host '没有自动找到游戏目录。' -ForegroundColor Yellow
    Write-Host '请把游戏文件夹拖到这个窗口里（A1 文件夹），然后回车：'
    $in = Read-Host '路径'
    $in = $in.Trim().Trim('"').Trim("'")
    if ($in -and (Test-Path (Join-Path $in 'WorldApart.exe'))) { $game = $in }
    elseif ($in -and (Test-Path $in) -and (Test-Path (Join-Path (Split-Path $in -Parent) 'WorldApart.exe'))) {
        $game = Split-Path $in -Parent
    }
    else { Write-Host '这个路径里没有 WorldApart.exe，再试一次。' -ForegroundColor Red }
}
Write-Host ('游戏目录：' + $game) -ForegroundColor Green

function Get-MissingParts {
    $need = @(
        'winhttp.dll',
        'doorstop_config.ini',
        '.doorstop_version',
        'dotnet\coreclr.dll',
        'BepInEx\core\BepInEx.Core.dll',
        'BepInEx\core\BepInEx.Unity.IL2CPP.dll'
    )
    $miss = @()
    foreach ($rel in $need) {
        if (-not (Test-Path (Join-Path $game $rel))) { $miss += $rel }
    }
    return $miss
}

# 旧的 Mono 版 core 与 IL2CPP 不兼容，先备份掉
$il2cppCore = Join-Path $game 'BepInEx\core\BepInEx.Unity.IL2CPP.dll'
if (-not (Test-Path $il2cppCore)) {
    $coreDir = Join-Path $game 'BepInEx\core'
    if (Test-Path $coreDir) {
        $bak = Join-Path $game 'BepInEx\core.bak'
        if (Test-Path $bak) { Remove-Item $bak -Recurse -Force -ErrorAction SilentlyContinue }
        try {
            Move-Item $coreDir $bak -Force -ErrorAction Stop
            Write-Host '原 BepInEx\core 已备份为 core.bak（不是 IL2CPP 版，无法用于本游戏）。' -ForegroundColor Yellow
        } catch {
            Write-Host '无法备份旧的 BepInEx\core，请先完全退出游戏再试。' -ForegroundColor Red
            exit 1
        }
    }
}

# 上次生成 IL2CPP 适配文件时如果联网下载 Unity 基础库失败，会留下残缺的 interop 目录，
# 启动时报 “Could not load file or assembly 'UnityEngine.CoreModule'”，插件全部不加载。
$interop = Join-Path $game 'BepInEx\interop'
$coreModule = Join-Path $interop 'UnityEngine.CoreModule.dll'
if ((Test-Path $interop) -and ((-not (Test-Path $coreModule)) -or ((Get-Item $coreModule).Length -lt 1024))) {
    try {
        Remove-Item $interop -Recurse -Force
        Write-Host '检测到上次生成的 IL2CPP 适配文件不完整，已清理，启动游戏时会重新生成。' -ForegroundColor Yellow
    } catch {
        Write-Host '无法清理残缺的 BepInEx\interop，请手动删除 BepInEx\interop 文件夹后再运行本安装。' -ForegroundColor Red
    }
}

$missing = @(Get-MissingParts)
if ($missing.Count -eq 0) {
    Write-Host '运行环境完整，只补装查询插件。' -ForegroundColor Green
}
else {
    Write-Host ('运行环境缺少 ' + $missing.Count + ' 项：' + ($missing -join '、')) -ForegroundColor Yellow
    Write-Host '正在补齐安装包自带的运行环境…'

    $win = Join-Path $game 'winhttp.dll'
    if (Test-Path $win) {
        $oldSize = (Get-Item $win).Length
        $newSize = (Get-Item (Join-Path $src 'winhttp.dll')).Length
        if ($oldSize -ne $newSize) {
            Move-Item $win ($win + '.bak') -Force -ErrorAction SilentlyContinue
            Write-Host '已备份原有的 winhttp.dll（与查询工具不兼容的版本）。' -ForegroundColor Yellow
        }
    }

    Copy-Item (Join-Path $src 'winhttp.dll') $game -Force
    Copy-Item (Join-Path $src 'doorstop_config.ini') $game -Force
    Copy-Item (Join-Path $src '.doorstop_version') $game -Force
    New-Item -ItemType Directory -Path (Join-Path $game 'BepInEx') -Force | Out-Null
    Copy-Item (Join-Path $src 'BepInEx\core') (Join-Path $game 'BepInEx') -Recurse -Force
    if (Test-Path (Join-Path $src 'BepInEx\unity-libs')) {
        Copy-Item (Join-Path $src 'BepInEx\unity-libs') (Join-Path $game 'BepInEx') -Recurse -Force
    }
    Copy-Item (Join-Path $src 'dotnet') $game -Recurse -Force

    $missing = @(Get-MissingParts)
    if ($missing.Count -gt 0) {
        Write-Host ('补齐失败，仍缺少：' + ($missing -join '、')) -ForegroundColor Red
        Write-Host '请确认“安装文件”文件夹完整（应包含 dotnet 和 BepInEx 两个目录），重新解压后再试。' -ForegroundColor Yellow
        exit 1
    }
    Write-Host '运行环境已补齐完成。' -ForegroundColor Green
}

# 老版本安装包不带 unity-libs，这里补上，生成适配文件时就不需要联网下载。
# 注意：BepInEx 下载失败时也会建出空的 unity-libs 目录，不能只判断目录是否存在；
# 只复制缺少的文件，玩家已经下载成功的版本保持原样，不覆盖。
$libsSrc = Join-Path $src 'BepInEx\unity-libs'
$libsDst = Join-Path $game 'BepInEx\unity-libs'
if (Test-Path $libsSrc) {
    New-Item -ItemType Directory -Path $libsDst -Force | Out-Null
    Get-ChildItem $libsSrc -Force | ForEach-Object {
        $target = Join-Path $libsDst $_.Name
        if (-not (Test-Path $target)) {
            Copy-Item $_.FullName $target -Recurse -Force
        }
    }
    Write-Host '已检查 Unity 基础库，缺失的文件已补齐（已有的不覆盖）。' -ForegroundColor Green
}
if (-not (Test-Path (Join-Path $libsDst '*.zip'))) {
    Write-Host '警告：BepInEx\unity-libs 里没有任何 zip。' -ForegroundColor Yellow
    Write-Host '首次启动若卡在生成适配文件，请把安装包里的 unity-libs 整个复制过去。' -ForegroundColor Yellow
}

$pluginDir = Join-Path $game 'BepInEx\plugins\SaveDecryptProbe'
New-Item -ItemType Directory -Path $pluginDir -Force | Out-Null
$sourceDll = Join-Path $src 'BepInEx\plugins\SaveDecryptProbe\SaveDecryptProbe.dll'
$targetDll = Join-Path $pluginDir 'SaveDecryptProbe.dll'
try {
    Copy-Item $sourceDll $targetDll -Force
} catch {
    try {
        $backupDll = $targetDll + '.old'
        if (Test-Path $backupDll) { Remove-Item $backupDll -Force -ErrorAction Stop }
        Move-Item $targetDll $backupDll -Force -ErrorAction Stop
        Copy-Item $sourceDll $targetDll -Force -ErrorAction Stop
    } catch {
        if ((-not (Test-Path $targetDll)) -and (Test-Path $backupDll)) {
            Move-Item $backupDll $targetDll -Force -ErrorAction SilentlyContinue
        }
        Write-Host ''
        Write-Host '插件文件被占用：请先把游戏完全退出，再运行一次本安装程序。' -ForegroundColor Red
        Write-Host '（任务管理器里结束 WorldApart.exe 也可以）' -ForegroundColor DarkGray
        exit 1
    }
}

$configPath = Join-Path $here 'config.json'
$settings = @{
    decrypted_dir = (Join-Path $game 'BepInEx\decrypted')
    game_dir = $game
    modules = @{ bedroom = $true; talent = $true; items = $true; pill = $true; forge = $true }
}
if (Test-Path $configPath) {
    try {
        $old = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($old.modules) {
            foreach ($name in @('bedroom', 'talent', 'items', 'pill', 'forge')) {
                $property = $old.modules.PSObject.Properties[$name]
                if ($null -ne $property) { $settings.modules[$name] = [bool]$property.Value }
            }
        }
    } catch {
        Write-Host '旧配置无法读取，将保留默认模块开关。' -ForegroundColor Yellow
    }
}
$configJson = $settings | ConvertTo-Json -Depth 4 -Compress
[System.IO.File]::WriteAllText($configPath, $configJson, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ''
Write-Host '────────────────── 安装自检清单 ──────────────────' -ForegroundColor Cyan

$checks = @(
    @{ label='winhttp.dll（Doorstop 代理）';        path='winhttp.dll' },
    @{ label='doorstop_config.ini（配置）';          path='doorstop_config.ini' },
    @{ label='dotnet\coreclr.dll（.NET 运行时）';    path='dotnet\coreclr.dll' },
    @{ label='BepInEx\core（运行时核心）';           path='BepInEx\core\BepInEx.Unity.IL2CPP.dll' },
    @{ label='BepInEx\unity-libs（Unity 基础库）';   path='BepInEx\unity-libs\*.zip' },
    @{ label='SaveDecryptProbe.dll（查询插件）';     path='BepInEx\plugins\SaveDecryptProbe\SaveDecryptProbe.dll' },
    @{ label='config.json（查询工具配置）';          path=(Join-Path $here 'config.json') }
)
$allOk = $true
foreach ($c in $checks) {
    $full = if ($c.path.StartsWith('BepInEx') -or $c.path.StartsWith('winhttp') -or $c.path.StartsWith('doorstop') -or $c.path.StartsWith('dotnet') -or $c.path.StartsWith('.doorstop')) { Join-Path $game $c.path } else { $c.path }
    $ok = Test-Path $full
    $mark = if ($ok) { '✓' } else { '✗' }
    $color = if ($ok) { 'Green' } else { 'Red' }
    Write-Host ('  ' + $mark + ' ' + $c.label) -ForegroundColor $color
    if (-not $ok) { $allOk = $false }
}

if (-not $allOk) {
    Write-Host ''
    Write-Host '自检未通过！请把报错截图发给作者。' -ForegroundColor Red
    exit 1
}

Write-Host '───────────────────────────────────────────────────' -ForegroundColor Cyan
Write-Host ''
Write-Host '运行环境已就绪。接下来：' -ForegroundColor Green
Write-Host '  1) 启动游戏，停在主菜单约 20 秒（插件自动导出存档副本）'
Write-Host '  2) 双击 仙友助手.exe 查看进度（会打开一个网页）'
Write-Host ''
Write-Host '首次启动会生成 IL2CPP 适配文件，可能停留 1~3 分钟且窗口看起来没反应，请勿关闭。' -ForegroundColor Yellow
Write-Host '平时每 60 秒自动同步；保存游戏后按 F8 可立即强制刷新。' -ForegroundColor DarkGray
Write-Host '查询工具的黑窗口保持开启，网页会在数据变化时自动更新。' -ForegroundColor DarkGray
Write-Host '可用「功能设置.bat」单独开关各模块。' -ForegroundColor DarkGray
Write-Host '卸载：删掉 BepInEx\plugins\SaveDecryptProbe 文件夹即可。' -ForegroundColor DarkGray


