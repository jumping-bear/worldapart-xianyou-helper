using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using BepInEx;
using BepInEx.Logging;
using BepInEx.Unity.IL2CPP;
using Il2CppInterop.Runtime.InteropTypes.Arrays;
using UnityEngine;

namespace SaveDecryptProbe
{
    [BepInPlugin("a1.save.decryptprobe", "SaveDecryptProbe", "1.5.0")]
    public class Plugin : BasePlugin
    {
        internal static ManualLogSource L;
        internal static string OutDir;
        internal static Process Assistant;

        public override void Load()
        {
            L = Log;
            OutDir = Path.Combine(BepInEx.Paths.BepInExRootPath, "decrypted");
            try { Directory.CreateDirectory(OutDir); } catch { }
            AddComponent<Boot>();
            Log.LogInfo("SaveDecryptProbe loaded (页面「立即同步」= 立即刷新存档副本)");
            // 浮窗抢焦点会让游戏失焦；后台继续运行可避免游戏暂停或静音。
            try { Application.runInBackground = true; } catch { }
            // 创意工坊只更新工坊目录，不会覆盖游戏目录里的副本，这里负责把新版同步过来。
            Updater.Run();
            StartAssistant();
        }

        /// <summary>随游戏启动覆盖窗口，玩家按 F3 呼出。</summary>
        private static void StartAssistant()
        {
            try
            {
                var exe = FindAssistant();
                if (exe == null)
                {
                    L.LogInfo("[assistant] 未找到仙友助手.exe，跳过自动启动");
                    return;
                }
                var info = new ProcessStartInfo(exe)
                {
                    Arguments = "--overlay --silent --parent-pid " + Process.GetCurrentProcess().Id,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WorkingDirectory = Path.GetDirectoryName(exe),
                };
                Assistant = Process.Start(info);
                L.LogInfo("[assistant] 已启动覆盖窗口：" + exe);
            }
            catch (Exception e)
            {
                L.LogWarning("[assistant] 启动失败：" + e.Message);
            }
        }

        private static string FindAssistant()
        {
            const string name = "仙友助手.exe";
            var candidates = new[]
            {
                Path.Combine(BepInEx.Paths.BepInExRootPath, "仙友助手", name),
                Path.Combine(BepInEx.Paths.GameRootPath, "仙友助手", name),
                Path.Combine(BepInEx.Paths.GameRootPath, name),
            };
            foreach (var path in candidates)
                if (File.Exists(path)) return path;
            return null;
        }

        internal static void StopAssistant()
        {
            try
            {
                if (Assistant != null && !Assistant.HasExited)
                {
                    Assistant.Kill();
                    L.LogInfo("[assistant] 已随游戏退出关闭覆盖窗口");
                }
            }
            catch { }
        }
    }

    /// <summary>
    /// 自动更新：Steam 只会刷新创意工坊目录，游戏目录里的副本不会变。
    /// 每次启动游戏时比对工坊目录与本地的 version.json：
    /// 工坊更新则结束旧助手进程、替换 EXE；插件 DLL 运行中被锁，
    /// 先落成 .pending，等游戏退出后由临时脚本替换。
    /// </summary>
    internal static class Updater
    {
        private const string AppId = "4209920";
        private const string ExeName = "仙友助手.exe";
        private const string VersionFile = "version.json";
        private const string PendingDll = "SaveDecryptProbe.dll.pending";
        private const string DllRelative = @"安装文件\BepInEx\plugins\SaveDecryptProbe\SaveDecryptProbe.dll";

        internal static void Run()
        {
            try
            {
                var localDir = Path.Combine(BepInEx.Paths.BepInExRootPath, "仙友助手");
                var source = FindWorkshopDir();
                if (source == null)
                {
                    Plugin.L.LogInfo("[update] 未找到创意工坊目录，跳过自动更新");
                    return;
                }
                var remote = ReadVersion(Path.Combine(source, VersionFile));
                if (string.IsNullOrEmpty(remote))
                {
                    Plugin.L.LogInfo("[update] 工坊目录缺少 version.json，跳过自动更新");
                    return;
                }
                var local = ReadVersion(Path.Combine(localDir, VersionFile));
                if (Compare(local, remote) >= 0)
                {
                    // 版本号相同也要检查本地 EXE：上一次更新可能被旧插件复制成了半个文件。
                    if (!ExeMatches(Path.Combine(localDir, ExeName),
                                    Path.Combine(localDir, VersionFile)))
                    {
                        if (SourceReady(source))
                        {
                            Plugin.L.LogWarning("[update] 本地 EXE 校验失败，从工坊重新复制");
                            SyncExe(source, localDir);
                            ClearUpdateError(Plugin.OutDir);
                        }
                        else
                        {
                            var broken = "本地程序校验失败，且工坊文件也不完整。请在 Steam 里验证文件完整性，"
                                + "或取消订阅后重新订阅。";
                            Plugin.L.LogWarning("[update] " + broken);
                            WriteUpdateError(Plugin.OutDir, broken);
                        }
                        return;
                    }
                    Plugin.L.LogInfo("[update] 已是最新 v" + local);
                    ClearUpdateError(Plugin.OutDir);
                    return;
                }
                Plugin.L.LogInfo("[update] 发现新版 v" + remote + "（本地 " + (local ?? "未知") + "），开始同步");
                // Steam 下载可能不完整：先按 version.json 里的大小与 SHA-256 校验工坊里的 EXE，
                // 校验失败就保留旧版，避免把截断的 EXE 复制过来后整个工具打不开。
                if (!SourceReady(source))
                {
                    var reason = "工坊文件未下载完整（v" + remote + "），已保留本地 "
                        + (local ?? "旧版") + "。请退出游戏后在 Steam 里验证文件完整性，或取消订阅后重新订阅。";
                    Plugin.L.LogWarning("[update] " + reason);
                    WriteUpdateError(Plugin.OutDir, reason);
                    return;
                }
                SyncExe(source, localDir);
                SyncPluginDll(source);
                ClearUpdateError(Plugin.OutDir);
            }
            catch (Exception e)
            {
                Plugin.L.LogWarning("[update] 自动更新失败：" + e.GetType().Name + " " + e.Message);
                WriteUpdateError(Plugin.OutDir,
                    "自动更新失败，已保留旧版，可继续使用。请完全退出游戏后让 Steam 重新更新；"
                    + "仍失败可在 Steam 里验证文件完整性或重新订阅。错误：" + e.Message);
            }
        }

        /// <summary>替换查询程序；先结束可能残留的旧助手进程。</summary>
        private static void SyncExe(string source, string localDir)
        {
            Directory.CreateDirectory(localDir);
            foreach (var process in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(ExeName)))
            {
                try { process.Kill(); process.WaitForExit(3000); } catch { }
            }
            CopyWithRetry(Path.Combine(source, ExeName), Path.Combine(localDir, ExeName));
            CopyWithRetry(Path.Combine(source, VersionFile), Path.Combine(localDir, VersionFile));
            Plugin.L.LogInfo("[update] 查询程序已更新");
        }

        /// <summary>插件 DLL 当前被游戏加载，先放到 .pending，退出后替换。</summary>
        private static void SyncPluginDll(string source)
        {
            var src = Path.Combine(source, DllRelative);
            if (!File.Exists(src)) return;
            var dst = Path.Combine(BepInEx.Paths.PluginPath, "SaveDecryptProbe", "SaveDecryptProbe.dll");
            if (SameFile(src, dst)) return;
            Directory.CreateDirectory(Path.GetDirectoryName(dst));
            CopyWithRetry(src, Path.Combine(Path.GetDirectoryName(dst), PendingDll));
            try
            {
                ScheduleSwap(dst);
                Plugin.L.LogInfo("[update] 插件已就绪，退出游戏后自动替换");
            }
            catch (Exception e)
            {
                Plugin.L.LogWarning("[update] 插件替换脚本创建失败：" + e.Message);
            }
        }

        /// <summary>游戏退出后由 cmd 脚本把 .pending 覆盖到 DLL 上（脚本内容全 ASCII）。</summary>
        private static void ScheduleSwap(string dllPath)
        {
            var folder = Path.GetDirectoryName(dllPath);
            var pid = Process.GetCurrentProcess().Id;
            var script = Path.Combine(folder, "_update.cmd");
            var text = string.Join("\r\n", new[]
            {
                "@echo off",
                "cd /d \"%~dp0\"",
                ":wait",
                "tasklist /FI \"PID eq " + pid + "\" 2>nul | find /I \"WorldApart.exe\" >nul",
                "if not errorlevel 1 (",
                "  ping -n 2 127.0.0.1 >nul",
                "  goto wait",
                ")",
                "copy /Y \"" + PendingDll + "\" \"SaveDecryptProbe.dll\" >nul",
                "del \"" + PendingDll + "\" >nul 2>nul",
                "del \"%~f0\" >nul 2>nul",
            }) + "\r\n";
            File.WriteAllText(script, text, new System.Text.UTF8Encoding(false));
            var info = new ProcessStartInfo("cmd.exe", "/c \"" + script + "\"")
            {
                CreateNoWindow = true,
                UseShellExecute = false,
                WorkingDirectory = folder,
                WindowStyle = ProcessWindowStyle.Hidden,
            };
            Process.Start(info);
        }

        /// <summary>工坊内容目录：steamapps\workshop\content\&lt;appid&gt;\&lt;itemid&gt;，取版本最高的一个。</summary>
        private static string FindWorkshopDir()
        {
            string best = null, bestVersion = null;
            foreach (var root in LibraryRoots())
            {
                var content = Path.Combine(root, "steamapps", "workshop", "content", AppId);
                if (!Directory.Exists(content)) continue;
                foreach (var item in Directory.GetDirectories(content))
                {
                    if (!File.Exists(Path.Combine(item, ExeName))) continue;
                    var version = ReadVersion(Path.Combine(item, VersionFile));
                    if (best == null || Compare(version, bestVersion) > 0)
                    {
                        best = item;
                        bestVersion = version;
                    }
                }
            }
            return best;
        }

        /// <summary>游戏所在 Steam 库及 libraryfolders.vdf 里登记的所有库。</summary>
        private static List<string> LibraryRoots()
        {
            var roots = new List<string>();
            var dir = new DirectoryInfo(BepInEx.Paths.GameRootPath);
            while (dir != null)
            {
                if (string.Equals(dir.Name, "steamapps", StringComparison.OrdinalIgnoreCase))
                {
                    if (dir.Parent != null) AddRoot(roots, dir.Parent.FullName);
                    break;
                }
                dir = dir.Parent;
            }
            foreach (var root in roots.ToArray())
            {
                foreach (var path in ReadLibraryPaths(Path.Combine(root, "steamapps", "libraryfolders.vdf")))
                    AddRoot(roots, path);
            }
            return roots;
        }

        private static void AddRoot(List<string> roots, string path)
        {
            try
            {
                if (string.IsNullOrEmpty(path) || !Directory.Exists(path)) return;
                foreach (var existing in roots)
                    if (string.Equals(existing, path, StringComparison.OrdinalIgnoreCase)) return;
                roots.Add(Path.GetFullPath(path));
            }
            catch { }
        }

        /// <summary>从 VDF 里取 "path" "X:\\SteamLibrary" 的路径。</summary>
        private static List<string> ReadLibraryPaths(string vdf)
        {
            var list = new List<string>();
            try
            {
                if (!File.Exists(vdf)) return list;
                foreach (var line in File.ReadAllLines(vdf))
                {
                    var key = line.IndexOf("\"path\"", StringComparison.OrdinalIgnoreCase);
                    if (key < 0) continue;
                    var start = line.IndexOf('"', key + 6);
                    if (start < 0) continue;
                    var end = line.IndexOf('"', start + 1);
                    if (end < 0) continue;
                    var path = line.Substring(start + 1, end - start - 1).Replace("\\\\", "\\");
                    if (path.Length > 0) list.Add(path);
                }
            }
            catch { }
            return list;
        }

        /// <summary>读自己生成的 version.json；不引入 JSON 依赖。</summary>
        private static string ReadVersion(string path)
        {
            try
            {
                if (!File.Exists(path)) return null;
                var text = File.ReadAllText(path);
                var key = text.IndexOf("\"version\"", StringComparison.OrdinalIgnoreCase);
                if (key < 0) return null;
                var start = text.IndexOf('"', key + 9);
                if (start < 0) return null;
                var end = text.IndexOf('"', start + 1);
                if (end < 0) return null;
                var value = text.Substring(start + 1, end - start - 1).Trim();
                return value.Length > 0 ? value : null;
            }
            catch { return null; }
        }

        /// <summary>从 version.json 里读一个字符串字段（不引入 JSON 依赖）。</summary>
        private static string ReadField(string path, string field)
        {
            try
            {
                if (!File.Exists(path)) return null;
                var text = File.ReadAllText(path);
                var key = text.IndexOf("\"" + field + "\"", StringComparison.OrdinalIgnoreCase);
                if (key < 0) return null;
                var start = text.IndexOf('"', key + field.Length + 2);
                if (start < 0) return null;
                var end = text.IndexOf('"', start + 1);
                if (end < 0) return null;
                return text.Substring(start + 1, end - start - 1).Trim();
            }
            catch { return null; }
        }

        /// <summary>校验工坊里的 EXE 是否完整；旧版工坊没有校验字段时按可用处理。</summary>
        private static bool SourceReady(string source)
        {
            return ExeMatches(Path.Combine(source, ExeName),
                              Path.Combine(source, VersionFile));
        }

        /// <summary>按 version.json 里的大小与 SHA-256 校验指定 EXE。</summary>
        private static bool ExeMatches(string exe, string versionFile)
        {
            if (!File.Exists(exe)) return false;
            long size;
            if (!long.TryParse(ReadField(versionFile, "exe_size"), out size) || size <= 0) return true;
            if (new FileInfo(exe).Length != size)
            {
                Plugin.L.LogWarning("[update] EXE 大小不符：" + new FileInfo(exe).Length + " / " + size);
                return false;
            }
            var expected = ReadField(versionFile, "exe_sha256");
            if (string.IsNullOrEmpty(expected)) return true;
            try
            {
                using (var sha = SHA256.Create())
                using (var stream = File.OpenRead(exe))
                {
                    var actual = BitConverter.ToString(sha.ComputeHash(stream))
                        .Replace("-", "").ToLowerInvariant();
                    if (!string.Equals(actual, expected.Trim(), StringComparison.OrdinalIgnoreCase))
                    {
                        Plugin.L.LogWarning("[update] EXE 校验值不符，工坊文件可能未下载完整");
                        return false;
                    }
                }
                return true;
            }
            catch (Exception e)
            {
                Plugin.L.LogWarning("[update] 校验 EXE 失败：" + e.Message);
                return false;
            }
        }

        private const string UpdateErrorFile = "_update_error.txt";

        private static void WriteUpdateError(string localDir, string message)
        {
            try
            {
                Directory.CreateDirectory(localDir);
                File.WriteAllText(Path.Combine(localDir, UpdateErrorFile), message,
                    new System.Text.UTF8Encoding(false));
            }
            catch { }
        }

        private static void ClearUpdateError(string localDir)
        {
            try
            {
                var path = Path.Combine(localDir, UpdateErrorFile);
                if (File.Exists(path)) File.Delete(path);
            }
            catch { }
        }

        private static int Compare(string left, string right)
        {
            var a = Split(left);
            var b = Split(right);
            var count = Math.Max(a.Length, b.Length);
            for (int i = 0; i < count; i++)
            {
                var x = i < a.Length ? a[i] : 0;
                var y = i < b.Length ? b[i] : 0;
                if (x != y) return x < y ? -1 : 1;
            }
            return 0;
        }

        private static int[] Split(string version)
        {
            if (string.IsNullOrEmpty(version)) return new int[0];
            var parts = version.Split('.');
            var list = new List<int>(parts.Length);
            foreach (var part in parts)
            {
                int value;
                if (!int.TryParse(part, out value)) value = 0;
                list.Add(value);
            }
            return list.ToArray();
        }

        private static bool SameFile(string left, string right)
        {
            try
            {
                var a = new FileInfo(left);
                var b = new FileInfo(right);
                if (!a.Exists || !b.Exists) return false;
                return a.Length == b.Length
                       && Math.Abs((a.LastWriteTimeUtc - b.LastWriteTimeUtc).TotalSeconds) < 2;
            }
            catch { return false; }
        }

        /// <summary>刚结束的进程可能还没释放文件句柄，短暂重试。</summary>
        private static void CopyWithRetry(string source, string target)
        {
            Exception last = null;
            for (int i = 0; i < 10; i++)
            {
                try
                {
                    File.Copy(source, target, true);
                    return;
                }
                catch (Exception e)
                {
                    last = e;
                    System.Threading.Thread.Sleep(200);
                }
            }
            if (last != null) throw last;
        }
    }

    public class Boot : MonoBehaviour
    {
        private float _next;
        private float _nextProbe;
        private float _lastForced;
        // 浮窗「立即同步」按钮写这个文件，插件发现后立刻导出一次，不用等下一轮轮询。
        private const string RefreshFlag = "_refresh.flag";

        private static bool Requested()
        {
            try
            {
                var flag = Path.Combine(Plugin.OutDir, RefreshFlag);
                if (!File.Exists(flag)) return false;
                try { File.Delete(flag); } catch { }
                return true;
            }
            catch { return false; }
        }

        private void OnApplicationQuit()
        {
            Plugin.StopAssistant();
        }

        private bool _lastFocus = true;
        private bool _lastPause;
        private float _lastVolume = -1f;
        private float _nextAudioLog;
        private bool _audioProbed;

        /// <summary>记录失焦前后的音频状态，用来定位游戏实际的静音方式。</summary>
        private void ProbeAudio()
        {
            if (!_audioProbed)
            {
                _audioProbed = true;
                foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    var name = asm.GetName().Name ?? "";
                    if (name.IndexOf("Wwise", StringComparison.OrdinalIgnoreCase) >= 0
                        || name.IndexOf("AkSoundEngine", StringComparison.OrdinalIgnoreCase) >= 0
                        || name.IndexOf("FMOD", StringComparison.OrdinalIgnoreCase) >= 0
                        || name.IndexOf("CriWare", StringComparison.OrdinalIgnoreCase) >= 0)
                        Plugin.L.LogInfo("[audio] 音频中间件程序集：" + name);
                }
            }
            var now = Time.unscaledTime;
            if (now < _nextAudioLog) return;
            _nextAudioLog = now + 1f;
            bool focus = Application.isFocused;
            bool pause = AudioListener.pause;
            float volume = AudioListener.volume;
            if (focus != _lastFocus || pause != _lastPause || Mathf.Abs(volume - _lastVolume) > 0.01f)
            {
                Plugin.L.LogInfo("[audio] focus=" + focus + " pause=" + pause
                    + " volume=" + volume.ToString("0.00")
                    + " timeScale=" + Time.timeScale.ToString("0.00"));
                _lastFocus = focus;
                _lastPause = pause;
                _lastVolume = volume;
            }
        }

        private bool _wakeTried;

        /// <summary>游戏用 Wwise，失焦时会 Suspend 音频引擎；浮窗在跑时把它唤醒回来。</summary>
        private void KeepAudioAlive()
        {
            if (Application.isFocused) { _wakeTried = false; return; }
            if (_wakeTried) return;
            _wakeTried = true;
            try
            {
                var result = AkSoundEngine.WakeupFromSuspend();
                Plugin.L.LogInfo("[audio] 失焦后已唤醒 Wwise：" + result);
            }
            catch (Exception e)
            {
                Plugin.L.LogWarning("[audio] 唤醒 Wwise 失败：" + e.GetType().Name + " " + e.Message);
            }
        }

        private void Update()
        {
            if (Plugin.Assistant != null)
            {
                ProbeAudio();
                KeepAudioAlive();
            }
            // 浮窗抢走焦点后游戏会静音；浮窗在运行期间把音频恢复，关掉工具后恢复原状。
            if (Plugin.Assistant != null && !Application.isFocused && AudioListener.pause)
                AudioListener.pause = false;

            string why = null;
            var now = Time.unscaledTime;
            // 进游戏头 5 秒先不扫，等存档目录就绪，也避免启动瞬间和加载抢 IO。
            if (now < 5f) return;
            // 外部同步请求每 0.25 秒探一次；File.Exists 很轻，比每帧检查更省。
            if (now >= _nextProbe)
            {
                _nextProbe = now + 0.25f;
                if (Requested()) why = "sync";
            }
            if (why != null && now - _lastForced < 1f) why = null;
            if (why == null && now < _next) return;
            if (why != null) { Plugin.L.LogInfo("[" + why + "] 立即检查存档更新"); _lastForced = now; }
            // 平时 5 秒扫一轮：只对存档做文件 stat，不读内容；需要即时刷新时点浮窗「立即同步」。
            _next = now + (why != null ? 1f : 5f);
            Work();
        }

        /// <summary>导出所有变更过的存档副本；返回 true 表示有文件正在写入，需要稍后重试。</summary>
        private bool Work()
        {
            try
            {
                var asm = AppDomain.CurrentDomain.GetAssemblies()
                    .FirstOrDefault(a => a.GetName().Name == "SimpleSave.Runtime");
                var t = asm?.GetTypes().FirstOrDefault(x => x != null && x.Name == "SaveFileEnvelope");
                if (t == null) return false;

                var m = t.GetMethods().FirstOrDefault(x => x.Name == "DecryptOrPassThrough");
                if (m == null) { Plugin.L.LogError("[err] DecryptOrPassThrough missing"); enabled = false; return false; }

                var root = Path.Combine(Application.persistentDataPath, "StorageV1", "1.0");
                if (!Directory.Exists(root)) return false;

                int ok = 0, skip = 0, busy = 0, done = 0;
                // 单次最多解密 1 份，把主线程占用压到最短，剩下的下一轮接着做。
                const int limit = 1;
                foreach (var f in FindTargets(root))
                {
                    DateTime written;
                    try { written = File.GetLastWriteTimeUtc(f); } catch { continue; }
                    var rel = f.Substring(root.Length + 1).Replace('\\', '_').Replace('/', '_');
                    var dst = Path.Combine(Plugin.OutDir, rel + ".bin");
                    // 已导出的副本不早于源文件，说明上次已经处理过，直接跳过（跨重启也有效）。
                    try
                    {
                        var di = new FileInfo(dst);
                        if (di.Exists && di.Length > 0 && di.LastWriteTimeUtc >= written) { skip++; continue; }
                    }
                    catch { }
                    if (done >= limit) { busy++; continue; }

                    // 游戏写盘时会以独占方式打开文件；能独占打开说明已经落盘，读不到就下一轮再取。
                    byte[] data;
                    try
                    {
                        using (var fs = new FileStream(f, FileMode.Open, FileAccess.Read, FileShare.Read))
                        {
                            long len = fs.Length;
                            if (len <= 0 || len > 512L * 1024 * 1024) { busy++; continue; }
                            data = new byte[(int)len];
                            int off = 0;
                            while (off < data.Length)
                            {
                                int n = fs.Read(data, off, data.Length - off);
                                if (n <= 0) break;
                                off += n;
                            }
                            if (off != data.Length) { busy++; continue; }
                        }
                    }
                    catch (IOException) { busy++; continue; }
                    catch (UnauthorizedAccessException) { busy++; continue; }
                    if (DateTime.UtcNow - written < TimeSpan.FromSeconds(1)) { busy++; continue; }

                    var res = Decrypt(m, data);
                    if (res == null) continue;
                    // 先写 .tmp 再原子替换：助手端永远读不到写了一半的副本。
                    var tmp = dst + ".tmp";
                    File.WriteAllBytes(tmp, res);
                    File.Move(tmp, dst, true);
                    ok++;
                    done++;
                }
                if (ok > 0) Plugin.L.LogInfo("[done] 更新 " + ok + " 份存档副本（跳过未变化 " + skip + "）");
                try
                {
                    File.WriteAllText(Path.Combine(Plugin.OutDir, "_status.txt"),
                        "lastSync=" + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
                        + "  updated=" + ok + "  unchanged=" + skip
                        + "  （点浮窗「立即同步」可强制刷新）");
                }
                catch { }
                return busy > 0;
            }
            catch (Exception e)
            {
                Plugin.L.LogError("[err] " + e.GetType().Name + " " + e.Message);
                return false;
            }
        }

        private static byte[] Decrypt(MethodInfo m, byte[] data)
        {
            var arr = new Il2CppStructArray<byte>(data.Length);
            for (int i = 0; i < data.Length; i++) arr[i] = data[i];
            object r;
            try { r = m.Invoke(null, new object[] { arr }); }
            catch (Exception e) { Plugin.L.LogWarning("[skip] " + e.GetType().Name + " " + (e.InnerException?.Message ?? e.Message)); return null; }
            if (r is Il2CppStructArray<byte> outArr)
            {
                long len = outArr.Length;
                // 正常存档解密后与原文件同量级；长度异常说明传入数据不完整或调用失败，
                // 直接丢弃，避免把垃圾数据写成副本。
                if (len <= 0 || len > data.Length * 8L) return null;
                var result = new byte[(int)len];
                for (int i = 0; i < result.Length; i++) result[i] = outArr[i];
                return result;
            }
            return null;
        }

        private static List<string> FindTargets(string root)
        {
            var list = new List<string>();
            try
            {
                foreach (var storage in Directory.GetDirectories(root))
                {
                    var slotRoot = Path.Combine(storage, "slots");
                    if (!Directory.Exists(slotRoot)) continue;
                    foreach (var slot in Directory.GetDirectories(slotRoot))
                    {
                        var gw = Path.Combine(slot, "gameworld.msgpack");
                        if (File.Exists(gw)) list.Add(gw);
                    }
                }
            }
            catch (Exception e) { Plugin.L.LogWarning("[scan] " + e.Message); }
            return list;
        }
    }
}
