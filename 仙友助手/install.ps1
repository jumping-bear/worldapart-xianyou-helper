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

$isEN = ((Get-UICulture).Name -notlike 'zh*')
Write-Host '=============================================' -ForegroundColor Cyan
if ($isEN) {
    Write-Host '  WorldApart · Xianyou Helper - one-click installer' -ForegroundColor Cyan
} else {
    Write-Host '  不问凡尘 · 仙友助手 一键安装' -ForegroundColor Cyan
}
Write-Host '=============================================' -ForegroundColor Cyan
Write-Host ''
if ($isEN) {
    Write-Host 'After installation (3 steps):' -ForegroundColor Green
    Write-Host '  1) Launch the game and stay on the main menu for about 20 seconds (the plugin exports a save copy).'
    Write-Host '     The first launch builds interop files and may look frozen for 1-3 minutes; this is normal.'
    Write-Host '  2) Press F3 in game to open the panel; press F3 again to hide it. It closes with the game.'
    Write-Host '     You can also double-click 仙友助手.exe to open the browser version.'
    Write-Host '  3) Auto-syncs every 10 seconds. After saving, click "Sync now" on the page to refresh immediately.'
} else {
    Write-Host '装完后这样用（3 步）：' -ForegroundColor Green
    Write-Host '  1) 启动游戏，停在主菜单约 20 秒（插件自动导出存档副本）'
    Write-Host '     首次启动要生成适配文件，可能慢 1~3 分钟且看起来没反应，属正常，别关游戏'
    Write-Host '  2) 游戏里按 F3 呼出查询面板，再按 F3 收起；退出游戏时面板自动关闭'
    Write-Host '     或双击 仙友助手.exe 启用网页版（游戏外查看）'
    Write-Host '  3) 平时不用管：每 10 秒自动同步；游戏里保存后点页面上的「立即同步」即可立刻刷新'
}
Write-Host ''
if ($isEN) { Write-Host 'Installing (about 1 minute)...' -ForegroundColor Cyan }
else { Write-Host '开始安装（约 1 分钟）…' -ForegroundColor Cyan }
Write-Host ''

if (Get-Process -Name WorldApart -ErrorAction SilentlyContinue) {
    Write-Host '检测到游戏正在运行，请先退出游戏（任务管理器结束 WorldApart.exe）再安装。' -ForegroundColor Red
    if ($isEN) { Write-Host 'The game is running. Close WorldApart.exe completely, then run this installer again.' -ForegroundColor Red }
    exit 1
}

$game = Find-GameDir($args[0])
while (-not $game) {
    Write-Host '没有自动找到游戏目录。' -ForegroundColor Yellow
    Write-Host '请把游戏文件夹拖到这个窗口里（A1 文件夹），然后回车：'
    if ($isEN) { Write-Host 'Drag the game folder (the A1 folder containing WorldApart.exe) here and press Enter.' -ForegroundColor Yellow }
    $in = Read-Host '路径 / Path'
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

# 默认关闭 BepInEx 控制台黑窗：日志仍写入 BepInEx\LogOutput.log，排查问题时可改回 true
$cfgDir = Join-Path $game 'BepInEx\config'
New-Item -ItemType Directory -Path $cfgDir -Force | Out-Null
$cfgPath = Join-Path $cfgDir 'BepInEx.cfg'
$srcCfg = Join-Path $src 'BepInEx\config\BepInEx.cfg'
if (-not (Test-Path $cfgPath)) {
    if (Test-Path $srcCfg) {
        Copy-Item $srcCfg $cfgPath -Force
        Write-Host '已关闭游戏内 BepInEx 控制台黑窗（日志见 BepInEx\LogOutput.log）。' -ForegroundColor Green
    }
} else {
    $cfgText = Get-Content $cfgPath -Raw -Encoding UTF8
    if ($cfgText -match '(?ms)\[Logging\.Console\][^\[]*?Enabled\s*=\s*true') {
        # 只改控制台这一个开关，其余配置（含其它 Mod 的设置）原样保留；改前留一份备份
        Copy-Item $cfgPath ($cfgPath + '.bak') -Force
        $cfgText = [regex]::Replace($cfgText, '(?ms)(\[Logging\.Console\][^\[]*?Enabled\s*=\s*)true', '${1}false')
        [System.IO.File]::WriteAllText($cfgPath, $cfgText, (New-Object System.Text.UTF8Encoding($false)))
        Write-Host '已关闭游戏内 BepInEx 控制台黑窗（仅改这一项，原配置备份为 BepInEx.cfg.bak）。' -ForegroundColor Green
    }
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
    overlay_hotkey = 'F3'
    overlay_size = 2
    modules = @{ bedroom = $true; talent = $true; items = $true; pill = $true; forge = $true; event = $true; quest = $true; memoria = $true }
}
if (Test-Path $configPath) {
    try {
        $old = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $hotkey = $old.PSObject.Properties['overlay_hotkey']
        if ($null -ne $hotkey -and $hotkey.Value) { $settings.overlay_hotkey = [string]$hotkey.Value }
        $size = $old.PSObject.Properties['overlay_size']
        if ($null -ne $size -and $null -ne $size.Value) { $settings.overlay_size = [int]$size.Value }
        $pos = $old.PSObject.Properties['overlay_pos']
        if ($null -ne $pos -and $null -ne $pos.Value) { $settings.overlay_pos = $pos.Value }
        # 语言和固定角色也要保留，否则每次重装都会把玩家的设置改回默认。
        foreach ($name in @('ui_lang', 'save_file', 'save_name')) {
            $property = $old.PSObject.Properties[$name]
            if ($null -ne $property -and $property.Value) { $settings[$name] = [string]$property.Value }
        }
        if ($old.modules) {
            foreach ($property in $old.modules.PSObject.Properties) {
                $settings.modules[$property.Name] = [bool]$property.Value
            }
        }
    } catch {
        Write-Host '旧配置无法读取，将保留默认模块开关。' -ForegroundColor Yellow
    }
}
$configJson = $settings | ConvertTo-Json -Depth 4 -Compress
[System.IO.File]::WriteAllText($configPath, $configJson, (New-Object System.Text.UTF8Encoding($false)))

# 覆盖窗口：复制到游戏目录，插件会在游戏启动时自动拉起，玩家按 F3 呼出。
$assistDir = Join-Path $game 'BepInEx\仙友助手'
New-Item -ItemType Directory -Path $assistDir -Force | Out-Null
$assistExe = Join-Path $here '仙友助手.exe'
if (Test-Path $assistExe) {
    try {
        Copy-Item $assistExe (Join-Path $assistDir '仙友助手.exe') -Force
        Copy-Item $configPath (Join-Path $assistDir 'config.json') -Force
        $verFile = Join-Path $here 'version.json'
        if (Test-Path $verFile) { Copy-Item $verFile (Join-Path $assistDir 'version.json') -Force }
        Write-Host '已安装覆盖窗口：游戏启动后按 F3 呼出，退出游戏自动关闭。' -ForegroundColor Green
    } catch {
        Write-Host '覆盖窗口文件被占用（可能正在运行），请关闭后再运行一次安装程序。' -ForegroundColor Yellow
    }
} else {
    Write-Host '警告：安装包里没有 仙友助手.exe，跳过覆盖窗口安装。' -ForegroundColor Yellow
}

Write-Host ''
Write-Host '────────────────── 安装自检 ──────────────────' -ForegroundColor Cyan

$checks = @(
    @{ label='winhttp.dll（Doorstop 代理）';        path='winhttp.dll' },
    @{ label='doorstop_config.ini（配置）';          path='doorstop_config.ini' },
    @{ label='dotnet\coreclr.dll（.NET 运行时）';    path='dotnet\coreclr.dll' },
    @{ label='BepInEx\core（运行时核心）';           path='BepInEx\core\BepInEx.Unity.IL2CPP.dll' },
    @{ label='BepInEx\unity-libs（Unity 基础库）';   path='BepInEx\unity-libs\*.zip' },
    @{ label='SaveDecryptProbe.dll（查询插件）';     path='BepInEx\plugins\SaveDecryptProbe\SaveDecryptProbe.dll' },
    @{ label='仙友助手.exe（覆盖窗口）';             path='BepInEx\仙友助手\仙友助手.exe' },
    @{ label='version.json（自动更新标记）';         path='BepInEx\仙友助手\version.json' },
    @{ label='config.json（查询工具配置）';          path=(Join-Path $here 'config.json') }
)
$failed = @()
foreach ($c in $checks) {
    $full = if ($c.path.StartsWith('BepInEx') -or $c.path.StartsWith('winhttp') -or $c.path.StartsWith('doorstop') -or $c.path.StartsWith('dotnet') -or $c.path.StartsWith('.doorstop')) { Join-Path $game $c.path } else { $c.path }
    if (-not (Test-Path $full)) { $failed += $c.label }
}

if ($failed.Count -gt 0) {
    Write-Host '自检未通过，缺少：' -ForegroundColor Red
    foreach ($label in $failed) { Write-Host ('  ✗ ' + $label) -ForegroundColor Red }
    Write-Host '请确认解压完整后重试；仍失败请把本窗口截图发给作者。' -ForegroundColor Yellow
    if ($isEN) { Write-Host 'Self-check failed. Make sure the archive was fully extracted, then run this installer again.' -ForegroundColor Yellow }
    exit 1
}
Write-Host ('自检通过：' + $checks.Count + '/' + $checks.Count + ' 项就绪') -ForegroundColor Green
Write-Host ''
if ($isEN) {
    Write-Host '------------------ Next 3 steps ------------------' -ForegroundColor Cyan
    Write-Host '  1) Launch the game and stay on the main menu for about 20 seconds so the plugin exports a save copy.' -ForegroundColor Green
    Write-Host '     The first launch builds interop files and may look frozen for 1-3 minutes; please wait.' -ForegroundColor Yellow
    Write-Host '  2) Press F3 in game to open the panel; press F3 again to hide it. You can also double-click 仙友助手.exe.' -ForegroundColor Green
    Write-Host '  3) Auto-syncs every 10 seconds; after saving, click "Sync now" on the page to refresh immediately.' -ForegroundColor Green
    Write-Host ''
    Write-Host '------------------ Future updates ------------------' -ForegroundColor Cyan
    Write-Host '  On v2.3.0 or newer, updates install automatically from the Steam Workshop on the next launch.' -ForegroundColor Green
    Write-Host '  The new 仙友助手.exe replaces itself right away; the plugin DLL swaps in after you exit the game.' -ForegroundColor Green
    Write-Host '  (v2.2.0 and older have no updater: this is the last manual install.)' -ForegroundColor DarkGray
} else {
    Write-Host '────────────────── 接下来 3 步 ──────────────────' -ForegroundColor Cyan
    Write-Host '  1) 启动游戏，停在主菜单约 20 秒，让插件导出存档副本' -ForegroundColor Green
    Write-Host '     首次启动会生成适配文件，可能慢 1~3 分钟且窗口没反应，属正常，请勿关闭' -ForegroundColor Yellow
    Write-Host '  2) 进游戏后按 F3 呼出查询面板，再按 F3 收起；或双击 仙友助手.exe 启用网页版' -ForegroundColor Green
    Write-Host '     面板不抢焦点，游戏声音不会中断；点搜索框打字时才接管键盘' -ForegroundColor Green
    Write-Host '  3) 平时自动同步；保存游戏后点页面上的「立即同步」即可立刻刷新' -ForegroundColor Green
    Write-Host ''
    Write-Host '────────────────── 以后更新 ──────────────────' -ForegroundColor Cyan
    Write-Host '  v2.3.0 起全自动：Steam 更新创意工坊内容后，下次启动游戏会自动同步' -ForegroundColor Green
    Write-Host '  新版 仙友助手.exe 和插件 DLL，不用再运行一键安装。' -ForegroundColor Green
    Write-Host '  （v2.2.0 及更早版本没有更新逻辑，这是最后一次手动安装）' -ForegroundColor DarkGray
}
Write-Host ''
Write-Host '────────────────── 其他说明 ──────────────────' -ForegroundColor DarkGray
Write-Host '游戏内已关闭 BepInEx 控制台黑窗，日志仍写在 BepInEx\LogOutput.log。' -ForegroundColor DarkGray
Write-Host '需要看插件日志时，把 BepInEx\config\BepInEx.cfg 里 [Logging.Console] 的 Enabled 改成 true。' -ForegroundColor DarkGray
Write-Host '可用「功能设置.bat」单独开关各模块；或双击本目录的 仙友助手.exe 启用网页版。' -ForegroundColor DarkGray
Write-Host '卸载：先退出游戏，再删除 游戏目录\BepInEx\plugins\SaveDecryptProbe 和 BepInEx\仙友助手，' -ForegroundColor DarkGray
Write-Host '      取消订阅创意工坊物品；BepInEx\decrypted 与 %LOCALAPPDATA%\WorldApartTouchProgress 可选删除。' -ForegroundColor DarkGray


