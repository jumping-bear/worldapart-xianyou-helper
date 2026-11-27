$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $here '安装文件'

# ── 界面语言 ──────────────────────────────────────────────────────────────
# 中文始终是主语言：不少中文玩家为了兼容性把 Windows 显示语言设成英文，
# 旧版只按系统语言二选一，结果中文玩家看到纯英文界面。现在中文永远先打，
# 非中文系统在其后再附一行英文（暗色），两种玩家都看得懂。
$isZh = ([System.Globalization.CultureInfo]::CurrentUICulture.Name -like 'zh*')
$forceEn = $false
$passArgs = @()
foreach ($a in $args) {
    $text = "$a"
    if ($text -eq '-en' -or $text -eq '--en' -or $text -eq '/en') { $forceEn = $true }
    elseif ($text) { $passArgs += $a }
}
$showEn = (-not $isZh) -or $forceEn

function Say {
    param([string]$Zh = '', [string]$En = '', [string]$Color = 'Gray')
    if ($Zh) { Write-Host $Zh -ForegroundColor $Color }
    if ($showEn -and $En) { Write-Host $En -ForegroundColor DarkGray }
}

function Step([string]$no, [string]$zh, [string]$en) {
    Write-Host ''
    Say ("[$no] " + $zh) ("[$no] " + $en) 'Cyan'
}

function Rule([string]$zh, [string]$en) {
    Write-Host ''
    Say ('────────────── ' + $zh + ' ──────────────') ('-------------- ' + $en + ' --------------') 'Cyan'
}

$version = ''
$verFile = Join-Path $here 'version.json'
if (Test-Path $verFile) {
    try { $version = [string](Get-Content $verFile -Raw -Encoding UTF8 | ConvertFrom-Json).version } catch { }
}
$title = '不问凡尘 · 仙友助手'
if ($version) { $title += '   v' + $version }

# ── 标题 ──────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host '════════════════════════════════════════════════════════' -ForegroundColor Cyan
Write-Host ('   ' + $title) -ForegroundColor Cyan
Say '   一键安装：游戏内 F3 查询面板 + 网页版' '   One-click installer: in-game F3 panel + web version' 'Cyan'
Write-Host '════════════════════════════════════════════════════════' -ForegroundColor Cyan

Say '安装内容：BepInEx 运行环境、存档导出插件、仙友助手.exe' 'Installs: BepInEx runtime, save-export plugin, Xianyou Helper.exe' 'Gray'
Say '不会改动：游戏本体、你的存档、创意工坊订阅' 'Untouched: the game itself, your saves, Workshop subscriptions' 'Gray'

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

# ── 前置检查：游戏是否还在运行 ────────────────────────────────────────────
Step '1/4' '安装前检查' 'Pre-install checks'
if (Get-Process -Name WorldApart -ErrorAction SilentlyContinue) {
    Say '游戏正在运行，请先完全退出游戏再安装。' 'The game is running. Close WorldApart.exe completely, then run this installer again.' 'Red'
    Say '（任务管理器里结束 WorldApart.exe 也可以）' '(Ending WorldApart.exe in Task Manager works too)' 'DarkGray'
    Write-Host ''
    Read-Host '按回车关闭窗口 / Press Enter to close'
    exit 1
}
Say '  游戏未运行，可以安装' '  Game is not running — ready to install' 'Green'

$game = Find-GameDir($passArgs[0])
while (-not $game) {
    Say '  没有自动找到游戏目录' '  Could not locate the game folder automatically' 'Yellow'
    Say '  请把游戏文件夹（A1，里面有 WorldApart.exe）拖到这个窗口，然后回车：' '  Drag the A1 folder (containing WorldApart.exe) into this window and press Enter:' 'Yellow'
    $in = Read-Host '  路径 / Path'
    $in = $in.Trim().Trim('"').Trim("'")
    if ($in -and (Test-Path (Join-Path $in 'WorldApart.exe'))) { $game = $in }
    elseif ($in -and (Test-Path $in) -and (Test-Path (Join-Path (Split-Path $in -Parent) 'WorldApart.exe'))) {
        $game = Split-Path $in -Parent
    }
    else { Say '  这个路径里没有 WorldApart.exe，请再试一次。' '  No WorldApart.exe in that folder. Try again.' 'Red' }
}
Say ('  游戏目录：' + $game) ('  Game folder: ' + $game) 'Green'

# 游戏装在 Program Files 时，非管理员无法写入，直接装会报“文件被占用”，先说明白。
$canWrite = $false
try {
    $probe = Join-Path $game ('.xy_write_test_' + [guid]::NewGuid().ToString('N'))
    [System.IO.File]::WriteAllText($probe, '')
    Remove-Item $probe -Force
    $canWrite = $true
} catch { }
if (-not $canWrite) {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Say '  没有写入游戏目录的权限（可能装在 Program Files）。' '  No write access to the game folder (it may live under Program Files).' 'Red'
        Say '  请关闭本窗口，右键「一键安装.bat」→ 以管理员身份运行。' '  Close this window, then right-click 一键安装.bat and choose "Run as administrator".' 'Yellow'
        Write-Host ''
        Read-Host '按回车关闭窗口 / Press Enter to close'
        exit 1
    }
}

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

# ── 步骤 2：运行环境 ──────────────────────────────────────────────────────
Step '2/4' '检查并补齐运行环境' 'Check and install runtime'

# 旧的 Mono 版 core 与 IL2CPP 不兼容，先备份掉
$il2cppCore = Join-Path $game 'BepInEx\core\BepInEx.Unity.IL2CPP.dll'
if (-not (Test-Path $il2cppCore)) {
    $coreDir = Join-Path $game 'BepInEx\core'
    if (Test-Path $coreDir) {
        $bak = Join-Path $game 'BepInEx\core.bak'
        if (Test-Path $bak) { Remove-Item $bak -Recurse -Force -ErrorAction SilentlyContinue }
        try {
            Move-Item $coreDir $bak -Force -ErrorAction Stop
            Say '  原 BepInEx\core 不是 IL2CPP 版，已备份为 core.bak' '  Old BepInEx\core backed up to core.bak (not the IL2CPP build)' 'Yellow'
        } catch {
            Say '  无法备份旧的 BepInEx\core，请先完全退出游戏再试。' '  Cannot back up the old BepInEx\core. Close the game completely and retry.' 'Red'
            Write-Host ''
            Read-Host '按回车关闭窗口 / Press Enter to close'
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
        Say '  上次生成的适配文件不完整，已清理，启动游戏时会重新生成' '  A broken interop folder was removed; it will be rebuilt on next launch' 'Yellow'
    } catch {
        Say '  无法清理残缺的 BepInEx\interop，请手动删除该文件夹后重试' '  Cannot remove BepInEx\interop. Delete that folder manually and retry.' 'Red'
    }
}

$missing = @(Get-MissingParts)
if ($missing.Count -eq 0) {
    Say '  运行环境已完整，只补装查询插件' '  Runtime already complete — only the plugin will be updated' 'Green'
}
else {
    Say ('  缺少 ' + $missing.Count + ' 项，正在从安装包补齐…') ('  ' + $missing.Count + ' component(s) missing — copying from the package...') 'Yellow'
    Write-Host ('    ' + ($missing -join '、')) -ForegroundColor DarkGray

    $win = Join-Path $game 'winhttp.dll'
    if (Test-Path $win) {
        $oldSize = (Get-Item $win).Length
        $newSize = (Get-Item (Join-Path $src 'winhttp.dll')).Length
        if ($oldSize -ne $newSize) {
            Move-Item $win ($win + '.bak') -Force -ErrorAction SilentlyContinue
            Say '  已备份原有的 winhttp.dll（与查询工具不兼容的版本）' '  Existing winhttp.dll backed up (incompatible version)' 'Yellow'
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
        Say ('  补齐失败，仍缺少：' + ($missing -join '、')) ('  Copy failed, still missing: ' + ($missing -join ', ')) 'Red'
        Say '  请确认「安装文件」文件夹完整（应含 dotnet 和 BepInEx 两个目录），重新解压后再试。' '  Make sure the 安装文件 folder is complete (needs dotnet and BepInEx), re-extract and retry.' 'Yellow'
        Write-Host ''
        Read-Host '按回车关闭窗口 / Press Enter to close'
        exit 1
    }
    Say '  运行环境已补齐' '  Runtime installed' 'Green'
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
    Say '  已检查 Unity 基础库（已有的不覆盖）' '  Unity libraries checked (existing files kept)' 'Green'
}
if (-not (Test-Path (Join-Path $libsDst '*.zip'))) {
    Say '  警告：BepInEx\unity-libs 里没有任何 zip' '  Warning: no zip found in BepInEx\unity-libs' 'Yellow'
    Say '  首次启动若卡在生成适配文件，请把安装包里的 unity-libs 整个复制过去' '  If the first launch stalls, copy the unity-libs folder from the package manually' 'Yellow'
}

# 默认关闭 BepInEx 控制台黑窗：日志仍写入 BepInEx\LogOutput.log，排查问题时可改回 true
$cfgDir = Join-Path $game 'BepInEx\config'
New-Item -ItemType Directory -Path $cfgDir -Force | Out-Null
$cfgPath = Join-Path $cfgDir 'BepInEx.cfg'
$srcCfg = Join-Path $src 'BepInEx\config\BepInEx.cfg'
if (-not (Test-Path $cfgPath)) {
    if (Test-Path $srcCfg) {
        Copy-Item $srcCfg $cfgPath -Force
        Say '  已关闭游戏内 BepInEx 控制台黑窗（日志见 BepInEx\LogOutput.log）' '  BepInEx console window disabled (log: BepInEx\LogOutput.log)' 'Green'
    }
} else {
    $cfgText = Get-Content $cfgPath -Raw -Encoding UTF8
    if ($cfgText -match '(?ms)\[Logging\.Console\][^\[]*?Enabled\s*=\s*true') {
        # 只改控制台这一个开关，其余配置（含其它 Mod 的设置）原样保留；改前留一份备份
        Copy-Item $cfgPath ($cfgPath + '.bak') -Force
        $cfgText = [regex]::Replace($cfgText, '(?ms)(\[Logging\.Console\][^\[]*?Enabled\s*=\s*)true', '${1}false')
        [System.IO.File]::WriteAllText($cfgPath, $cfgText, (New-Object System.Text.UTF8Encoding($false)))
        Say '  已关闭 BepInEx 控制台黑窗（原配置备份为 BepInEx.cfg.bak）' '  BepInEx console disabled (old config saved as BepInEx.cfg.bak)' 'Green'
    }
}

# ── 步骤 3：查询插件 ──────────────────────────────────────────────────────
Step '3/4' '安装查询插件' 'Install the query plugin'

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
        Say '' ''
        Say '  插件文件被占用：请先把游戏完全退出，再运行一次本安装程序。' '  Plugin file is locked. Close the game completely and run the installer again.' 'Red'
        Say '  （任务管理器里结束 WorldApart.exe 也可以）' '  (Ending WorldApart.exe in Task Manager works too)' 'DarkGray'
        Write-Host ''
        Read-Host '按回车关闭窗口 / Press Enter to close'
        exit 1
    }
}
Say '  插件已就位：BepInEx\plugins\SaveDecryptProbe' '  Plugin installed: BepInEx\plugins\SaveDecryptProbe' 'Green'

# ── 步骤 4：配置与覆盖窗口 ────────────────────────────────────────────────
Step '4/4' '生成配置并安装覆盖窗口' 'Write config and install the overlay'

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
        Say '  已沿用上次的设置（快捷键、语言、模块开关）' '  Previous settings kept (hotkey, language, module switches)' 'Green'
    } catch {
        Say '  旧配置无法读取，将使用默认模块开关' '  Old config unreadable — using default module switches' 'Yellow'
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
        $verCopy = Join-Path $here 'version.json'
        if (Test-Path $verCopy) { Copy-Item $verCopy (Join-Path $assistDir 'version.json') -Force }
        Say '  覆盖窗口已安装：游戏启动后按 F3 呼出，退出游戏自动关闭' '  Overlay installed: press F3 in game, it closes with the game' 'Green'
    } catch {
        Say '  覆盖窗口文件被占用（可能正在运行），请关闭后再运行一次安装程序' '  Overlay file is locked (maybe running). Close it and run the installer again.' 'Yellow'
    }
} else {
    Say '  警告：安装包里没有 仙友助手.exe，跳过覆盖窗口安装' '  Warning: 仙友助手.exe not found in the package — overlay install skipped' 'Yellow'
}

# ── 自检 ──────────────────────────────────────────────────────────────────
Rule '安装自检' 'Self-check'

$checks = @(
    @{ label='winhttp.dll（Doorstop 代理）';        en='winhttp.dll (Doorstop proxy)';    path='winhttp.dll' },
    @{ label='doorstop_config.ini（配置）';          en='doorstop_config.ini';            path='doorstop_config.ini' },
    @{ label='dotnet\coreclr.dll（.NET 运行时）';    en='dotnet\coreclr.dll (.NET)';      path='dotnet\coreclr.dll' },
    @{ label='BepInEx\core（运行时核心）';           en='BepInEx\core';                    path='BepInEx\core\BepInEx.Unity.IL2CPP.dll' },
    @{ label='BepInEx\unity-libs（Unity 基础库）';   en='BepInEx\unity-libs';              path='BepInEx\unity-libs\*.zip' },
    @{ label='SaveDecryptProbe.dll（查询插件）';     en='SaveDecryptProbe.dll';            path='BepInEx\plugins\SaveDecryptProbe\SaveDecryptProbe.dll' },
    @{ label='仙友助手.exe（覆盖窗口）';             en='仙友助手.exe (overlay)';          path='BepInEx\仙友助手\仙友助手.exe' },
    @{ label='version.json（自动更新标记）';         en='version.json (update marker)';    path='BepInEx\仙友助手\version.json' },
    @{ label='config.json（查询工具配置）';          en='config.json (tool settings)';     path=(Join-Path $here 'config.json') }
)
$failed = @()
foreach ($c in $checks) {
    $full = if ($c.path.StartsWith('BepInEx') -or $c.path.StartsWith('winhttp') -or $c.path.StartsWith('doorstop') -or $c.path.StartsWith('dotnet') -or $c.path.StartsWith('.doorstop')) { Join-Path $game $c.path } else { $c.path }
    if (Test-Path $full) {
        Write-Host ('  ✓ ' + $c.label) -ForegroundColor Green
        if ($showEn -and $c.en) { Write-Host ('    ' + $c.en) -ForegroundColor DarkGray }
    } else {
        $failed += $c.label
        Write-Host ('  ✗ ' + $c.label) -ForegroundColor Red
    }
}

if ($failed.Count -gt 0) {
    Write-Host ''
    Say ('自检未通过，缺少 ' + $failed.Count + ' 项') ('Self-check failed, ' + $failed.Count + ' item(s) missing') 'Red'
    Say '请确认安装包解压完整后重试；仍失败请把本窗口截图发给作者。' 'Re-extract the package and retry. If it still fails, send a screenshot of this window.' 'Yellow'
    Write-Host ''
    Read-Host '按回车关闭窗口 / Press Enter to close'
    exit 1
}

Write-Host ''
Say ('自检通过：' + $checks.Count + '/' + $checks.Count + ' 项就绪，安装完成') ('Self-check passed: ' + $checks.Count + '/' + $checks.Count + ' ready — installation complete') 'Green'

# ── 下一步 ────────────────────────────────────────────────────────────────
Rule '接下来 3 步' 'Next 3 steps'

Say '  1) 启动游戏，停在主菜单约 20 秒，让插件导出存档副本' '  1) Launch the game and wait about 20 seconds on the main menu so the plugin exports a save copy' 'Green'
Say '     首次启动会生成适配文件，可能慢 1~3 分钟且窗口没反应，属正常，请勿关闭' '     First launch builds interop files and may look frozen for 1-3 minutes. Please wait.' 'Yellow'
Say '  2) 进游戏后按 F3 呼出查询面板，再按 F3 收起' '  2) Press F3 in game to open the panel; press F3 again to hide it' 'Green'
Say '     面板不抢焦点，游戏声音不会中断；点搜索框打字时才接管键盘' '     The panel does not steal focus; it only takes the keyboard when you click the search box' 'DarkGray'
Say '  3) 平时自动同步；保存游戏后点页面上的「立即同步」即可立刻刷新' '  3) Syncs every 10 seconds; after saving, click "Sync now" on the page to refresh at once' 'Green'
Say '     也可以双击本目录的 仙友助手.exe 用网页版（游戏外查看）' '     You can also double-click 仙友助手.exe for the web version outside the game' 'DarkGray'

Rule '以后更新' 'Future updates'
Say '  v2.3.0 起全自动：Steam 更新创意工坊内容后，下次启动游戏会自动同步' '  Since v2.3.0 updates install automatically from the Steam Workshop on next launch' 'Green'
Say '  新版 仙友助手.exe 和插件 DLL，不用再运行一键安装' '  The new exe and plugin DLL replace themselves — no need to re-run this installer' 'Green'
Say '  （v2.2.0 及更早版本没有更新逻辑，这是最后一次手动安装）' '  (v2.2.0 and older have no updater: this is the last manual install)' 'DarkGray'

Rule '其他说明' 'Notes'
Say '  游戏内已关闭 BepInEx 控制台黑窗，日志仍写在 BepInEx\LogOutput.log' '  The BepInEx console is hidden; logs still go to BepInEx\LogOutput.log' 'DarkGray'
Say '  需要看插件日志时，把 BepInEx\config\BepInEx.cfg 里 [Logging.Console] 的 Enabled 改成 true' '  To see logs, set [Logging.Console] Enabled = true in BepInEx\config\BepInEx.cfg' 'DarkGray'
Say '  可用「功能设置.bat」单独开关各模块；或双击本目录的 仙友助手.exe 用网页版' '  Use 功能设置.bat to toggle modules, or double-click 仙友助手.exe for the web version' 'DarkGray'
Say '  卸载：先退出游戏，再删除 游戏目录\BepInEx\plugins\SaveDecryptProbe 和 BepInEx\仙友助手，' '  Uninstall: quit the game, delete BepInEx\plugins\SaveDecryptProbe and BepInEx\仙友助手,' 'DarkGray'
Say '        取消订阅创意工坊物品；BepInEx\decrypted 与 %LOCALAPPDATA%\WorldApartTouchProgress 可选删除。' '        unsubscribe the Workshop item, and optionally delete BepInEx\decrypted and %LOCALAPPDATA%\WorldApartTouchProgress' 'DarkGray'

Write-Host ''
Write-Host '════════════════════════════════════════════════════════' -ForegroundColor Cyan
Say ('   安装完成，祝道友一路顺风。   v' + $version) ('   All done. Enjoy the journey.   v' + $version) 'Cyan'
Write-Host '════════════════════════════════════════════════════════' -ForegroundColor Cyan
Write-Host ''
