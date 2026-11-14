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

$hasBep = Test-Path (Join-Path $game 'BepInEx\core\BepInEx.Core.dll')
if (-not $hasBep) {
    Write-Host '未检测到 BepInEx，正在安装运行环境…'
    $win = Join-Path $game 'winhttp.dll'
    if (Test-Path $win) { Move-Item $win ($win + '.bak') -Force }
    Copy-Item (Join-Path $src 'winhttp.dll') $game -Force
    Copy-Item (Join-Path $src 'doorstop_config.ini') $game -Force
    Copy-Item (Join-Path $src '.doorstop_version') $game -Force
    New-Item -ItemType Directory -Path (Join-Path $game 'BepInEx') -Force | Out-Null
    Copy-Item (Join-Path $src 'BepInEx\core') (Join-Path $game 'BepInEx') -Recurse -Force
    Write-Host '运行环境已安装。' -ForegroundColor Green
}
else {
    Write-Host '检测到已安装 BepInEx，只补装查询插件。' -ForegroundColor Green
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
    modules = @{ bedroom = $true; talent = $true }
}
if (Test-Path $configPath) {
    try {
        $old = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($old.modules) {
            foreach ($name in @('bedroom', 'talent')) {
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
Write-Host '安装完成！接下来：' -ForegroundColor Cyan
Write-Host '  1) 启动游戏，停在主菜单约 20 秒（会自动导出存档副本）'
Write-Host '  2) 双击 仙友助手.exe 查看十八摸或 NPC 天赋（会打开一个网页）'
Write-Host ''
Write-Host '平时每 60 秒自动同步；保存游戏后按 F8 可立即强制刷新。' -ForegroundColor DarkGray
Write-Host '查询工具的黑窗口保持开启，网页会在数据变化时自动更新。' -ForegroundColor DarkGray
Write-Host '可用「功能设置.bat」单独开关十八摸或 NPC 天赋。' -ForegroundColor DarkGray
Write-Host '卸载：删掉 BepInEx\plugins\SaveDecryptProbe 文件夹即可。' -ForegroundColor DarkGray


