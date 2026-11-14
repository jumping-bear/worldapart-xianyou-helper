using System;
using System.Collections.Generic;
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
    [BepInPlugin("a1.save.decryptprobe", "SaveDecryptProbe", "1.2.0")]
    public class Plugin : BasePlugin
    {
        internal static ManualLogSource L;
        internal static string OutDir;

        public override void Load()
        {
            L = Log;
            OutDir = Path.Combine(BepInEx.Paths.BepInExRootPath, "decrypted");
            try { Directory.CreateDirectory(OutDir); } catch { }
            AddComponent<Boot>();
            Log.LogInfo("SaveDecryptProbe loaded (F8 = 立即刷新存档副本)");
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

        private void Update()
        {
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
