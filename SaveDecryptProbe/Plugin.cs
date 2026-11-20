using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using BepInEx;
using BepInEx.Logging;
using BepInEx.Unity.IL2CPP;
using Il2CppInterop.Runtime.InteropTypes.Arrays;
using UnityEngine;

namespace SaveDecryptProbe
{
    [BepInPlugin("a1.save.decryptprobe", "SaveDecryptProbe", "1.4.0")]
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
            Log.LogInfo("SaveDecryptProbe loaded (F8 = 立即刷新存档副本)");
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
                    Plugin.L.LogInfo("[update] 已是最新 v" + local);
                    return;
                }
                Plugin.L.LogInfo("[update] 发现新版 v" + remote + "（本地 " + (local ?? "未知") + "），开始同步");
                SyncExe(source, localDir);
                SyncPluginDll(source);
            }
            catch (Exception e)
            {
                Plugin.L.LogWarning("[update] 自动更新失败：" + e.GetType().Name + " " + e.Message);
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
        private static readonly Dictionary<string, long> Seen = new Dictionary<string, long>();
        private float _next;
        private int _f8Check;

        private static bool Hotkey()
        {
            try { if (Input.GetKeyDown(KeyCode.F8)) return true; } catch { }
            try
            {
                var asm = AppDomain.CurrentDomain.GetAssemblies()
                    .FirstOrDefault(a => a.GetName().Name == "Unity.InputSystem");
                var kb = asm?.GetType("UnityEngine.InputSystem.Keyboard");
                var cur = kb?.GetProperty("current", BindingFlags.Public | BindingFlags.Static)?.GetValue(null);
                if (cur == null) return false;
                var key = cur.GetType().GetProperty("f8Key")?.GetValue(cur);
                if (key == null) return false;
                return (bool)(key.GetType().GetProperty("wasPressedThisFrame")?.GetValue(key) ?? false);
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

            bool hot = Hotkey();
            var now = Time.unscaledTime;
            if (!hot && now < _next) return;
            if (now < 5f) return;
            _next = hot ? now + 5f : now + 60f;
            if (hot)
            {
                Seen.Clear();
                Plugin.L.LogInfo("[f8] 强制刷新存档副本");
            }
            Work();
        }

        private void Work()
        {
            try
            {
                var asm = AppDomain.CurrentDomain.GetAssemblies()
                    .FirstOrDefault(a => a.GetName().Name == "SimpleSave.Runtime");
                var t = asm?.GetTypes().FirstOrDefault(x => x != null && x.Name == "SaveFileEnvelope");
                if (t == null) return;

                var m = t.GetMethods().FirstOrDefault(x => x.Name == "DecryptOrPassThrough");
                if (m == null) { Plugin.L.LogError("[err] DecryptOrPassThrough missing"); enabled = false; return; }

                var root = Path.Combine(Application.persistentDataPath, "StorageV1", "1.0");
                if (!Directory.Exists(root)) return;

                int ok = 0, skip = 0;
                foreach (var f in FindTargets(root))
                {
                    long stamp;
                    try { stamp = File.GetLastWriteTimeUtc(f).Ticks ^ new FileInfo(f).Length; } catch { continue; }
                    if (Seen.TryGetValue(f, out var old) && old == stamp) { skip++; continue; }

                    var data = File.ReadAllBytes(f);
                    var res = Decrypt(m, data);
                    if (res == null) continue;
                    var rel = f.Substring(root.Length + 1).Replace('\\', '_').Replace('/', '_');
                    File.WriteAllBytes(Path.Combine(Plugin.OutDir, rel + ".bin"), res);
                    Seen[f] = stamp;
                    ok++;
                }
                if (ok > 0) Plugin.L.LogInfo("[done] 更新 " + ok + " 份存档副本（跳过未变化 " + skip + "）");
                try
                {
                    File.WriteAllText(Path.Combine(Plugin.OutDir, "_status.txt"),
                        "lastSync=" + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
                        + "  updated=" + ok + "  unchanged=" + skip
                        + "  （按 F8 可强制刷新）");
                }
                catch { }
            }
            catch (Exception e)
            {
                Plugin.L.LogError("[err] " + e.GetType().Name + " " + e.Message);
            }
        }

        private static byte[] Decrypt(MethodInfo m, byte[] data)
        {
            var arr = new Il2CppStructArray<byte>(data.Length);
            for (int i = 0; i < data.Length; i++) arr[i] = data[i];
            object r;
            try { r = m.Invoke(null, new object[] { arr }); }
            catch (Exception e) { Plugin.L.LogWarning("[skip] " + e.GetType().Name + " " + (e.InnerException?.Message ?? e.Message)); return null; }
            if (r is Il2CppStructArray<byte> outArr) return outArr.ToArray();
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
