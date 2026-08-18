"""
压缩解压工具 v3.1
修复：智能压缩生成多个临时包未清理的bug
新增：操作日志历史记录（本地JSON持久化，历史记录标签页可查看/导出/清空）
底层调用 7-Zip / NanaZip 命令行
"""

import os
import sys
import time
import json
import tempfile
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# ==================== 操作日志系统 ====================
LOG_FILE = os.path.join(os.path.expanduser("~"), ".ziptool_history.json")

def load_history():
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except: pass
    return []

def save_history(records):
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(records[-500:], f, ensure_ascii=False, indent=2)
    except: pass

def add_history(action, source, output="", result="success", detail="", size=0, elapsed=0):
    records = load_history()
    records.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "source": source,
        "output": output,
        "result": result,
        "detail": detail,
        "size": size,
        "elapsed": round(elapsed, 2)
    })
    save_history(records)

# ==================== 7z 路径 ====================
SEVEN_ZIP = None
def find_7z():
    global SEVEN_ZIP
    for name in ["7z.exe", "7z", "NanaZipC.exe", "NanaZipC"]:
        try:
            r = subprocess.run([name, "--version"], capture_output=True, timeout=5)
            if r.returncode == 0 or "7-Zip" in r.stdout.decode("gbk", errors="ignore"):
                SEVEN_ZIP = name; return
        except: pass
    for p in [r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files\NanaZip\NanaZipC.exe"]:
        if os.path.exists(p): SEVEN_ZIP = p; return
find_7z()

def run_cmd(cmd, timeout=600):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("gbk", errors="ignore"), r.stderr.decode("gbk", errors="ignore")
    except subprocess.TimeoutExpired: return -1, "", "Timeout"
    except Exception as e: return -1, "", str(e)

# ==================== 格式定义 ====================
COMPRESS_FORMATS = [
    {"name": "7z", "ext": ".7z"}, {"name": "zip", "ext": ".zip"}, {"name": "tar.gz", "ext": ".tar.gz"},
]
COMPRESS_LEVELS = [str(i) for i in range(10)]
EXTRACT_EXTS = (".zip",".7z",".rar",".tar",".gz",".bz2",".xz",".iso",".cab",".lzma",".zstd",".tgz")

# ==================== 深色主题 ====================
DARK_BG = "#1e1e1e"; DARK_FG = "#d4d4d4"; DARK_ACCENT = "#0078d4"
dark_mode = False

def apply_theme(root, style):
    if dark_mode:
        root.configure(bg=DARK_BG)
        style.configure(".", background=DARK_BG, foreground=DARK_FG, fieldbackground="#2d2d2d")
        style.configure("TFrame", background=DARK_BG)
        style.configure("TLabel", background=DARK_BG, foreground=DARK_FG)
        style.configure("TButton", background="#3c3c3c", foreground=DARK_FG)
        style.configure("TNotebook", background=DARK_BG)
        style.configure("TNotebook.Tab", background="#2d2d2d", foreground=DARK_FG)
        style.map("TNotebook.Tab", background=[("selected", DARK_ACCENT)])
        style.configure("Horizontal.TProgressbar", background=DARK_ACCENT)
        style.configure("Treeview", background="#2d2d2d", foreground=DARK_FG, fieldbackground="#2d2d2d")
    else:
        root.configure(bg="SystemButtonFace")
        style.configure(".", background="SystemButtonFace", foreground="SystemWindowText", fieldbackground="SystemWindow")
        style.configure("TFrame", background="SystemButtonFace")
        style.configure("TLabel", background="SystemButtonFace", foreground="SystemWindowText")

# ==================== 核心功能 ====================
def do_compress(file_list, output_file, fmt, level, password=None, volume=None, log_cb=None):
    t0 = time.time()
    try:
        if not file_list: return False, "No files", 0
        out = Path(output_file); sz = SEVEN_ZIP or "7z"
        if log_cb: log_cb(f"Compressing: {fmt['name']} L{level}")
        if fmt["name"] == "tar.gz":
            tar = str(out).replace(".tar.gz", ".tar")
            c1 = [sz,"a","-ttar","-mmt=on","-y",tar]+[str(f) for f in file_list]
            code,o,e = run_cmd(c1)
            if log_cb: [log_cb(l) for l in (o+e).splitlines() if l.strip()]
            if code != 0: return False, "tar failed", 0
            c2 = [sz,"a","-tgzip",f"-mx{level}","-mmt=on","-y",str(out),tar]
            code,o,e = run_cmd(c2)
            if log_cb: [log_cb(l) for l in (o+e).splitlines() if l.strip()]
            try: os.remove(tar)
            except: pass
            if code != 0: return False, "gzip failed", 0
        else:
            at = "7z" if fmt["name"]=="7z" else "zip"
            cmd = [sz,"a",f"-t{at}",f"-mx{level}","-mmt=on","-bb1","-y"]
            if at=="7z": cmd.append("-m0=LZMA2:d=1m:fb=32")
            if volume: cmd.append(f"-v{volume}")
            if password:
                cmd.append(f"-p{password}")
                if at=="zip": cmd.append("-mem=AES256")
            cmd.append(str(out)); cmd += [str(f) for f in file_list]
            code,o,e = run_cmd(cmd)
            if log_cb: [log_cb(l) for l in (o+e).splitlines() if l.strip()]
            if code != 0: return False, f"Failed code {code}", 0
        sz_out = os.path.getsize(out) if os.path.exists(out) else 0
        return True, f"Done: {out}", sz_out
    except Exception as ex: return False, str(ex), 0
    finally:
        elapsed = time.time() - t0

def do_extract(archive, out_dir, password=None, log_cb=None):
    t0 = time.time()
    try:
        a = Path(archive); out = Path(out_dir)
        if not a.exists(): return False, "Not found", 0
        os.makedirs(out, exist_ok=True)
        sz = SEVEN_ZIP or "7z"
        cmd = [sz,"x","-mmt=on","-bb1","-y",f"-o{out}",str(a)]
        cmd.insert(2, f"-p{password}" if password else "-p-")
        code,o,e = run_cmd(cmd)
        out_text = o+"\n"+e
        if log_cb: [log_cb(l) for l in out_text.splitlines() if l.strip()]
        if code == 0: return True, "Done!", 0
        ol = out_text.lower()
        if "wrong password" in ol or "data error in encrypted" in ol:
            return False, "Wrong password" if password else "Encrypted, need password", 0
        return False, f"Failed code {code}", 0
    except Exception as ex: return False, str(ex), 0
    finally:
        elapsed = time.time() - t0

def do_preview(archive, password=None):
    sz = SEVEN_ZIP or "7z"
    cmd = [sz,"l",str(archive)]
    if password: cmd.append(f"-p{password}")
    code,o,e = run_cmd(cmd)
    if code != 0: return None, "Cannot read"
    files = []; in_list = False
    for line in o.splitlines():
        if "---" in line and not in_list: in_list = True; continue
        if in_list and "---" in line: break
        if in_list and line.strip():
            parts = line.split()
            if len(parts) >= 3:
                try:
                    sz2 = int(parts[0]) if parts[0].isdigit() else 0
                    name = " ".join(parts[2:])
                    if name: files.append({"name":name,"size":sz2})
                except: pass
    return files, None

def do_test(archive, password=None):
    sz = SEVEN_ZIP or "7z"
    cmd = [sz,"t",str(archive)]
    if password: cmd.append(f"-p{password}")
    code,o,e = run_cmd(cmd)
    return code == 0, o+e

def do_repair(archive, output_dir):
    sz = SEVEN_ZIP or "7z"
    cmd = [sz,"r",f"-o{output_dir}",str(archive)]
    code,o,e = run_cmd(cmd)
    return code == 0, o+e

def do_convert(archive, target_fmt, output_dir, log_cb=None):
    t0 = time.time()
    try:
        sz = SEVEN_ZIP or "7z"
        tmpdir = tempfile.mkdtemp()
        if log_cb: log_cb("Step 1: Extracting...")
        ok, msg, _ = do_extract(archive, tmpdir, log_cb=log_cb)
        if not ok: return False, f"Extract failed: {msg}", 0
        base = Path(archive).stem
        out = Path(output_dir) / (base + target_fmt["ext"])
        fmt_info = {"name": target_fmt["name"], "ext": target_fmt["ext"]}
        if log_cb: log_cb(f"Step 2: Compressing to {target_fmt['name']}...")
        files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir)]
        ok, msg, sz_out = do_compress(files, str(out), fmt_info, 5, log_cb=log_cb)
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
        return ok, msg, sz_out
    except Exception as ex: return False, str(ex), 0
    finally:
        elapsed = time.time() - t0

def do_smart_compress(file_list, output_base, log_cb=None):
    """智能压缩：测试多种格式选最小，用try/finally确保临时文件全部清理"""
    t0 = time.time()
    temp_files = []
    best = None
    try:
        results = []
        for fmt in COMPRESS_FORMATS:
            for level in ["1", "5", "9"]:
                out = f"{output_base}_{fmt['name']}_l{level}{fmt['ext']}"
                temp_files.append(out)
                ok, msg, sz_out = do_compress(file_list, out, fmt, int(level), log_cb=lambda m: None)
                if ok and os.path.exists(out):
                    size = os.path.getsize(out)
                    results.append({"fmt":fmt["name"],"level":level,"size":size,"file":out})
                    if log_cb: log_cb(f"{fmt['name']} L{level}: {size:,}B")
        if not results: return None, "All failed", 0
        best = min(results, key=lambda x: x["size"])
        final = f"{output_base}_best{Path(best['file']).suffix}"
        try:
            if os.path.exists(best["file"]):
                os.rename(best["file"], final)
        except:
            import shutil
            shutil.copy2(best["file"], final)
        return best, final, best["size"]
    except Exception as ex:
        return None, str(ex), 0
    finally:
        # 【关键修复】确保所有临时文件被删除，不管成功还是失败
        for f in temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except: pass
        elapsed = time.time() - t0

def do_batch_compress(folder, fmt, level, log_cb=None):
    count = 0
    for item in os.listdir(folder):
        src = os.path.join(folder, item)
        if os.path.isdir(src) or os.path.isfile(src):
            out = os.path.join(folder, item + fmt["ext"])
            if log_cb: log_cb(f"Compress: {item}")
            ok,_,_ = do_compress([src], out, fmt, level, log_cb=log_cb)
            if ok: count += 1
    return True, f"Done: {count}"

def do_batch_extract(folder, log_cb=None):
    count = 0
    for item in os.listdir(folder):
        src = os.path.join(folder, item)
        if os.path.isfile(src) and item.lower().endswith(EXTRACT_EXTS):
            out = os.path.join(folder, os.path.splitext(item)[0])
            if log_cb: log_cb(f"Extract: {item}")
            ok,_,_ = do_extract(src, out, log_cb=log_cb)
            if ok: count += 1
    return True, f"Done: {count}"

def do_crack(archive, dict_path, log_cb=None):
    if not os.path.exists(dict_path): return False, "Dict not found"
    sz = SEVEN_ZIP or "7z"; found = None; count = 0
    with open(dict_path, "r", encoding="utf-8", errors="ignore") as f:
        pwds = [l.strip() for l in f if l.strip()]
    for pwd in pwds:
        count += 1
        if log_cb and count % 10 == 0: log_cb(f"Trying {count}/{len(pwds)}: {pwd}")
        code,_,_ = run_cmd([sz,"t",f"-p{pwd}","-y",str(archive)], timeout=10)
        if code == 0: found = pwd; break
    return (True, f"Found: {found}") if found else (False, f"Tried {count}, not found")

def do_compare(test_file, log_cb=None):
    results = []; sz = SEVEN_ZIP or "7z"; orig = os.path.getsize(test_file)
    tmpdir = tempfile.mkdtemp()
    for fmt,level in [("zip","1"),("zip","5"),("zip","9"),("7z","1"),("7z","5"),("7z","9")]:
        out = os.path.join(tmpdir, f"t_{fmt}_{level}."+fmt)
        t0 = time.time()
        cmd = [sz,"a",f"-t{fmt}",f"-mx{level}","-mmt=on","-y",out,test_file]
        if fmt=="7z": cmd.append("-m0=LZMA2:d=1m:fb=32")
        code,_,_ = run_cmd(cmd)
        el = time.time()-t0
        if code==0 and os.path.exists(out):
            cs = os.path.getsize(out)
            results.append({"format":fmt,"level":level,"size":cs,"ratio":cs/orig*100,"time":el})
            if log_cb: log_cb(f"{fmt} L{level}: {cs:,}B ({cs/orig*100:.1f}%) {el:.2f}s")
    import shutil; shutil.rmtree(tmpdir, ignore_errors=True)
    return results, None

def set_file_association(associate=True):
    import winreg
    exts = [".zip",".7z",".rar",".tar",".gz",".bz2",".xz",".iso",".cab",".lzma",".zstd",".tgz"]
    for ext in exts:
        try:
            if associate:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\{ext}")
                winreg.SetValue(key, "", winreg.REG_SZ, "ZipTool")
                winreg.CloseKey(key)
            else:
                try: winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\{ext}")
                except: pass
        except: pass
    return True

# ==================== GUI ====================
class ZipToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("压缩解压工具 v3.1")
        self.root.geometry("860x680")
        self.root.minsize(760, 600)
        self.compress_files = []
        self.style = ttk.Style()
        try: self.style.theme_use("clam")
        except: pass
        self._build_ui()
        if DND_AVAILABLE: self._setup_dragdrop()

    def _log(self, widget, msg):
        widget.insert(tk.END, msg+"\n"); widget.see(tk.END); self.root.update_idletasks()

    def _setup_dragdrop(self):
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self._on_drop)

    def _on_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        if not files: return
        arcs = [f for f in files if f.lower().endswith(EXTRACT_EXTS)]
        if arcs and not [f for f in files if not f.lower().endswith(EXTRACT_EXTS)]:
            self.decomp_path.set(arcs[0]); self.decomp_out.set(os.path.dirname(arcs[0]))
        else:
            for f in files:
                if f not in self.compress_files:
                    self.compress_files.append(f); self.comp_list.insert(tk.END, f)
            self._update_comp_out()

    def _build_ui(self):
        nb = ttk.Notebook(self.root); nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        self._build_compress_tab(nb)
        self._build_extract_tab(nb)
        self._build_preview_tab(nb)
        self._build_convert_tab(nb)
        self._build_batch_tab(nb)
        self._build_crack_tab(nb)
        self._build_compare_tab(nb)
        self._build_tools_tab(nb)
        self._build_history_tab(nb)
        self._build_settings_tab(nb)
        self.status = tk.StringVar(value="Ready" + (" | Drag enabled" if DND_AVAILABLE else ""))
        ttk.Label(self.root, textvariable=self.status, foreground="gray", anchor=tk.W).pack(fill=tk.X, padx=10, pady=(0,6))

    def _build_compress_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  压缩  ")
        ttk.Label(f, text="添加文件 (可拖拽):").pack(anchor=tk.W)
        br = ttk.Frame(f); br.pack(fill=tk.X, pady=4)
        ttk.Button(br, text="添加文件", command=self._add_files).pack(side=tk.LEFT)
        ttk.Button(br, text="添加文件夹", command=self._add_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(br, text="清空", command=lambda: (self.compress_files.clear(), self.comp_list.delete(0,tk.END))).pack(side=tk.LEFT)
        lf = ttk.Frame(f); lf.pack(fill=tk.BOTH, expand=False, pady=4)
        self.comp_list = tk.Listbox(lf, height=4, bg="#1e1e1e", fg="#d4d4d4")
        self.comp_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(lf, command=self.comp_list.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.comp_list.config(yscrollcommand=sb.set)
        opt = ttk.Frame(f); opt.pack(fill=tk.X, pady=6)
        ttk.Label(opt, text="格式:").pack(side=tk.LEFT)
        self.fmt_var = tk.StringVar(value="zip")
        ttk.Combobox(opt, textvariable=self.fmt_var, values=[x["name"] for x in COMPRESS_FORMATS], state="readonly", width=8).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text="等级:").pack(side=tk.LEFT, padx=(8,0))
        self.level_var = tk.StringVar(value="1")
        ttk.Combobox(opt, textvariable=self.level_var, values=COMPRESS_LEVELS, state="readonly", width=5).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text="密码:").pack(side=tk.LEFT, padx=(8,0))
        self.pwd_var = tk.StringVar()
        ttk.Entry(opt, textvariable=self.pwd_var, show="*", width=10).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text="分卷:").pack(side=tk.LEFT, padx=(8,0))
        self.vol_var = tk.StringVar()
        ttk.Entry(opt, textvariable=self.vol_var, width=6).pack(side=tk.LEFT, padx=4)
        self.smart_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="智能压缩（自动选最优，会生成临时文件后自动清理）", variable=self.smart_var).pack(side=tk.LEFT, padx=(12,0))
        ttk.Label(f, text="输出文件:").pack(anchor=tk.W, pady=(6,0))
        orow = ttk.Frame(f); orow.pack(fill=tk.X, pady=4)
        self.comp_out = tk.StringVar()
        ttk.Entry(orow, textvariable=self.comp_out).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(orow, text="浏览", command=self._pick_comp_out, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(f, text="▶ 开始压缩", command=self._on_compress).pack(pady=8, anchor=tk.W)
        self.comp_prog = ttk.Progressbar(f, mode="determinate"); self.comp_prog.pack(fill=tk.X)
        self.comp_log = tk.Text(f, height=5, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.comp_log.pack(fill=tk.BOTH, expand=True, pady=(6,0))

    def _add_files(self):
        paths = filedialog.askopenfilenames(title="Select files")
        for p in paths:
            if p not in self.compress_files: self.compress_files.append(p); self.comp_list.insert(tk.END, p)
        self._update_comp_out()
    def _add_folder(self):
        p = filedialog.askdirectory(title="Select folder")
        if p and p not in self.compress_files: self.compress_files.append(p); self.comp_list.insert(tk.END, p); self._update_comp_out()
    def _update_comp_out(self):
        if self.compress_files and not self.comp_out.get():
            d = os.path.dirname(self.compress_files[0])
            fmt = [x for x in COMPRESS_FORMATS if x["name"]==self.fmt_var.get()][0]
            self.comp_out.set(os.path.join(d, "output"+fmt["ext"]))
    def _pick_comp_out(self):
        fmt = [x for x in COMPRESS_FORMATS if x["name"]==self.fmt_var.get()][0]
        p = filedialog.asksaveasfilename(defaultextension=fmt["ext"], filetypes=[(fmt["name"],"*"+fmt["ext"])])
        if p: self.comp_out.set(p)
    def _on_compress(self):
        if not self.compress_files: messagebox.showwarning("","Add files"); return
        if not self.comp_out.get(): messagebox.showwarning("","Select output"); return
        self.comp_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_compress, daemon=True).start()
    def _do_compress(self):
        def log(m): self.root.after(0, lambda: self._log(self.comp_log, m))
        def prog(p): self.root.after(0, lambda: self.comp_prog.configure(value=p))
        prog(10); t0 = time.time()
        src = ", ".join([os.path.basename(f) for f in self.compress_files])
        if self.smart_var.get():
            base = os.path.splitext(self.comp_out.get())[0]
            best, final, sz_out = do_smart_compress(self.compress_files, base, log)
            prog(100); elapsed = time.time()-t0
            if best:
                msg = f"Best: {best['fmt']} L{best['level']} = {best['size']:,}B\nOutput: {final}"
                add_history("智能压缩", src, final, "success", f"{best['fmt']} L{best['level']}", best["size"], elapsed)
            else:
                msg = "Failed"; add_history("智能压缩", src, "", "failed", "", 0, elapsed)
            self.root.after(0, lambda: messagebox.showinfo("Smart Compress", msg))
        else:
            fmt = [x for x in COMPRESS_FORMATS if x["name"]==self.fmt_var.get()][0]
            vol = self.vol_var.get().strip() or None
            ok, msg, sz_out = do_compress(self.compress_files, self.comp_out.get(), fmt, int(self.level_var.get()), self.pwd_var.get() or None, vol, log)
            prog(100); elapsed = time.time()-t0
            add_history("压缩", src, self.comp_out.get(), "success" if ok else "failed", f"{fmt['name']} L{self.level_var.get()}", sz_out, elapsed)
            self.root.after(0, lambda: messagebox.showinfo("Done" if ok else "Failed", msg))

    def _build_extract_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  解压  ")
        ttk.Label(f, text="压缩文件:").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.decomp_path = tk.StringVar()
        ttk.Entry(row, textvariable=self.decomp_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=self._pick_decomp_file, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(f, text="输出目录:").pack(anchor=tk.W, pady=(6,0))
        row2 = ttk.Frame(f); row2.pack(fill=tk.X, pady=6)
        self.decomp_out = tk.StringVar()
        ttk.Entry(row2, textvariable=self.decomp_out).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row2, text="浏览", command=self._pick_decomp_out, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(f, text="密码:").pack(anchor=tk.W, pady=(6,0))
        self.decomp_pwd = tk.StringVar()
        ttk.Entry(f, textvariable=self.decomp_pwd, show="*").pack(fill=tk.X, pady=4)
        ttk.Button(f, text="▶ 开始解压", command=self._on_decompress).pack(pady=8, anchor=tk.W)
        self.decomp_prog = ttk.Progressbar(f, mode="determinate"); self.decomp_prog.pack(fill=tk.X)
        self.decomp_log = tk.Text(f, height=8, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.decomp_log.pack(fill=tk.BOTH, expand=True, pady=(6,0))
    def _pick_decomp_file(self):
        p = filedialog.askopenfilename(filetypes=[("Archives","*.zip *.7z *.rar *.tar *.gz *.bz2 *.xz *.iso *.cab *.lzma *.zstd *.tgz"),("All","*.*")])
        if p: self.decomp_path.set(p); self.decomp_out.set(os.path.dirname(p))
    def _pick_decomp_out(self):
        p = filedialog.askdirectory()
        if p: self.decomp_out.set(p)
    def _on_decompress(self):
        if not self.decomp_path.get(): messagebox.showwarning("","Select archive"); return
        self.decomp_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_decompress, daemon=True).start()
    def _do_decompress(self):
        def log(m): self.root.after(0, lambda: self._log(self.decomp_log, m))
        def prog(p): self.root.after(0, lambda: self.decomp_prog.configure(value=p))
        prog(10); t0 = time.time()
        outdir = self.decomp_out.get() or os.path.dirname(self.decomp_path.get())
        ok, msg, _ = do_extract(self.decomp_path.get(), outdir, self.decomp_pwd.get() or None, log)
        prog(100); elapsed = time.time()-t0
        add_history("解压", self.decomp_path.get(), outdir, "success" if ok else "failed", msg, 0, elapsed)
        self.root.after(0, lambda: messagebox.showinfo("Done" if ok else "Failed", msg))

    def _build_preview_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  预览  ")
        ttk.Label(f, text="双击文本文件可查看内容：").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.prev_path = tk.StringVar()
        ttk.Entry(row, textvariable=self.prev_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=self._pick_prev_file, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(row, text="预览", command=self._on_preview, width=8).pack(side=tk.LEFT, padx=(6,0))
        cols = ("name","size")
        self.prev_tree = ttk.Treeview(f, columns=cols, show="headings", height=10)
        self.prev_tree.heading("name", text="Filename"); self.prev_tree.heading("size", text="Size")
        self.prev_tree.column("name", width=500); self.prev_tree.column("size", width=120, anchor=tk.E)
        self.prev_tree.pack(fill=tk.BOTH, expand=True, pady=6)
        self.prev_tree.bind("<Double-1>", self._on_prev_doubleclick)
        self.prev_info = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.prev_info, foreground="gray").pack(anchor=tk.W)
    def _pick_prev_file(self):
        p = filedialog.askopenfilename(filetypes=[("Archives","*.zip *.7z *.rar *.tar *.gz *.bz2 *.xz *.iso *.cab"),("All","*.*")])
        if p: self.prev_path.set(p)
    def _on_preview(self):
        if not self.prev_path.get(): messagebox.showwarning("","Select archive"); return
        self.prev_tree.delete(*self.prev_tree.get_children())
        files, err = do_preview(self.prev_path.get())
        if err: messagebox.showerror("Error", err); return
        total = 0
        for f in files:
            self.prev_tree.insert("", tk.END, values=(f["name"], f"{f['size']:,}")); total += f["size"]
        self.prev_info.set(f"{len(files)} files, {total:,} bytes total")
    def _on_prev_doubleclick(self, event):
        sel = self.prev_tree.selection()
        if not sel: return
        item = self.prev_tree.item(sel[0])
        name = item["values"][0]
        if not name.lower().endswith((".txt",".md",".csv",".log",".ini",".cfg",".py",".json",".xml",".html")):
            messagebox.showinfo("提示", "仅支持查看文本文件（txt/md/csv/log等）"); return
        sz = SEVEN_ZIP or "7z"; tmpdir = tempfile.mkdtemp()
        cmd = [sz,"e","-y",f"-o{tmpdir}",self.prev_path.get(),name]
        code,o,e = run_cmd(cmd)
        if code != 0: messagebox.showerror("Error", "无法提取文件"); return
        filepath = os.path.join(tmpdir, os.path.basename(name))
        if not os.path.exists(filepath):
            for root,dirs,files in os.walk(tmpdir):
                for fn in files:
                    if fn == os.path.basename(name): filepath = os.path.join(root, fn); break
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f: content = f.read()
        except: content = "(无法读取)"
        win = tk.Toplevel(self.root); win.title(f"预览: {name}"); win.geometry("600x400")
        txt = tk.Text(win, wrap=tk.WORD, font=("Consolas",10))
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        txt.insert("1.0", content); txt.config(state=tk.DISABLED)
        import shutil
        win.protocol("WM_DELETE_WINDOW", lambda: (shutil.rmtree(tmpdir, ignore_errors=True), win.destroy()))

    def _build_convert_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  格式转换  ")
        ttk.Label(f, text="源压缩包:").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.cvt_from = tk.StringVar()
        ttk.Entry(row, textvariable=self.cvt_from).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=lambda: self.cvt_from.set(filedialog.askopenfilename(filetypes=[("Archives","*.zip *.7z *.rar *.tar *.gz *.bz2 *.xz")]) or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(f, text="目标格式:").pack(anchor=tk.W, pady=(8,0))
        self.cvt_to = tk.StringVar(value="zip")
        ttk.Combobox(f, textvariable=self.cvt_to, values=[x["name"] for x in COMPRESS_FORMATS], state="readonly", width=10).pack(anchor=tk.W, pady=4)
        ttk.Label(f, text="输出目录:").pack(anchor=tk.W, pady=(8,0))
        self.cvt_out = tk.StringVar()
        row2 = ttk.Frame(f); row2.pack(fill=tk.X, pady=4)
        ttk.Entry(row2, textvariable=self.cvt_out).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row2, text="浏览", command=lambda: self.cvt_out.set(filedialog.askdirectory() or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(f, text="▶ 开始转换", command=self._on_convert).pack(pady=10, anchor=tk.W)
        self.cvt_log = tk.Text(f, height=10, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.cvt_log.pack(fill=tk.BOTH, expand=True, pady=6)
    def _on_convert(self):
        if not self.cvt_from.get(): messagebox.showwarning("","Select source"); return
        if not self.cvt_out.get(): self.cvt_out.set(os.path.dirname(self.cvt_from.get()))
        self.cvt_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_convert, daemon=True).start()
    def _do_convert(self):
        def log(m): self.root.after(0, lambda: self._log(self.cvt_log, m))
        fmt = [x for x in COMPRESS_FORMATS if x["name"]==self.cvt_to.get()][0]
        t0 = time.time()
        ok, msg, sz_out = do_convert(self.cvt_from.get(), fmt, self.cvt_out.get(), log)
        elapsed = time.time()-t0
        add_history("格式转换", self.cvt_from.get(), self.cvt_out.get(), "success" if ok else "failed", f"to {fmt['name']}", sz_out, elapsed)
        self.root.after(0, lambda: messagebox.showinfo("Done" if ok else "Failed", msg))

    def _build_batch_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  批量  ")
        ttk.Label(f, text="选择文件夹：").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.batch_dir = tk.StringVar()
        ttk.Entry(row, textvariable=self.batch_dir).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=lambda: self.batch_dir.set(filedialog.askdirectory() or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        opt = ttk.Frame(f); opt.pack(fill=tk.X, pady=6)
        ttk.Label(opt, text="格式:").pack(side=tk.LEFT)
        self.batch_fmt = tk.StringVar(value="zip")
        ttk.Combobox(opt, textvariable=self.batch_fmt, values=[x["name"] for x in COMPRESS_FORMATS], state="readonly", width=8).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text="等级:").pack(side=tk.LEFT, padx=(8,0))
        self.batch_level = tk.StringVar(value="1")
        ttk.Combobox(opt, textvariable=self.batch_level, values=COMPRESS_LEVELS, state="readonly", width=5).pack(side=tk.LEFT, padx=4)
        btns = ttk.Frame(f); btns.pack(pady=8)
        ttk.Button(btns, text="▶ 批量压缩", command=lambda: self._batch_run("compress")).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="▶ 批量解压", command=lambda: self._batch_run("extract")).pack(side=tk.LEFT, padx=4)
        self.batch_log = tk.Text(f, height=10, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.batch_log.pack(fill=tk.BOTH, expand=True, pady=6)
    def _batch_run(self, mode):
        if not self.batch_dir.get(): messagebox.showwarning("","Select folder"); return
        self.batch_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_batch, args=(mode,), daemon=True).start()
    def _do_batch(self, mode):
        def log(m): self.root.after(0, lambda: self._log(self.batch_log, m))
        t0 = time.time()
        if mode == "compress":
            fmt = [x for x in COMPRESS_FORMATS if x["name"]==self.batch_fmt.get()][0]
            ok, msg = do_batch_compress(self.batch_dir.get(), fmt, int(self.batch_level.get()), log)
            add_history("批量压缩", self.batch_dir.get(), "", "success", msg, 0, time.time()-t0)
        else:
            ok, msg = do_batch_extract(self.batch_dir.get(), log)
            add_history("批量解压", self.batch_dir.get(), "", "success", msg, 0, time.time()-t0)
        self.root.after(0, lambda: messagebox.showinfo("Done", msg))

    def _build_crack_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  密码恢复  ")
        ttk.Label(f, text="⚠️ 仅限恢复自己的密码，禁止非法用途！", foreground="red").pack(anchor=tk.W)
        ttk.Label(f, text="加密压缩包：").pack(anchor=tk.W, pady=(8,0))
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=4)
        self.crack_arc = tk.StringVar()
        ttk.Entry(row, textvariable=self.crack_arc).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=lambda: self.crack_arc.set(filedialog.askopenfilename(filetypes=[("Archives","*.zip *.7z *.rar")]) or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(f, text="密码字典（每行一个）：").pack(anchor=tk.W, pady=(6,0))
        row2 = ttk.Frame(f); row2.pack(fill=tk.X, pady=4)
        self.crack_dict = tk.StringVar()
        ttk.Entry(row2, textvariable=self.crack_dict).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row2, text="浏览", command=lambda: self.crack_dict.set(filedialog.askopenfilename(filetypes=[("Text","*.txt")]) or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(f, text="▶ 开始字典破解", command=self._on_crack).pack(pady=10, anchor=tk.W)
        self.crack_log = tk.Text(f, height=8, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.crack_log.pack(fill=tk.BOTH, expand=True, pady=6)
    def _on_crack(self):
        if not self.crack_arc.get() or not self.crack_dict.get(): messagebox.showwarning("","Select files"); return
        self.crack_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_crack, daemon=True).start()
    def _do_crack(self):
        def log(m): self.root.after(0, lambda: self._log(self.crack_log, m))
        t0 = time.time()
        ok, msg = do_crack(self.crack_arc.get(), self.crack_dict.get(), log)
        add_history("密码恢复", self.crack_arc.get(), "", "success" if ok else "failed", msg, 0, time.time()-t0)
        self.root.after(0, lambda: messagebox.showinfo("Result", msg))

    def _build_compare_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  压缩率对比  ")
        ttk.Label(f, text="选择测试文件：").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.cmp_file = tk.StringVar()
        ttk.Entry(row, textvariable=self.cmp_file).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=lambda: self.cmp_file.set(filedialog.askopenfilename() or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(f, text="▶ 开始对比", command=self._on_compare).pack(pady=8, anchor=tk.W)
        cols = ("format","level","size","ratio","time")
        self.cmp_tree = ttk.Treeview(f, columns=cols, show="headings", height=8)
        for c,t,w in [("format","格式",80),("level","等级",60),("size","压缩后",140),("ratio","压缩率",100),("time","耗时",100)]:
            self.cmp_tree.heading(c, text=t); self.cmp_tree.column(c, width=w, anchor=tk.CENTER)
        self.cmp_tree.pack(fill=tk.BOTH, expand=True, pady=6)
        self.cmp_log = tk.Text(f, height=3, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.cmp_log.pack(fill=tk.X, pady=(6,0))
    def _on_compare(self):
        if not self.cmp_file.get(): messagebox.showwarning("","Select file"); return
        self.cmp_tree.delete(*self.cmp_tree.get_children()); self.cmp_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_compare, daemon=True).start()
    def _do_compare(self):
        def log(m): self.root.after(0, lambda: self._log(self.cmp_log, m))
        results, err = do_compare(self.cmp_file.get(), log)
        if err: self.root.after(0, lambda: messagebox.showerror("Error", err)); return
        for r in results:
            self.root.after(0, lambda r=r: self.cmp_tree.insert("", tk.END, values=(r["format"],r["level"],f"{r['size']:,}B",f"{r['ratio']:.1f}%",f"{r['time']:.2f}s")))
        self.root.after(0, lambda: messagebox.showinfo("Done","对比完成！"))

    def _build_tools_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  工具箱  ")
        ttk.Label(f, text="压缩包：", font=("Segoe UI",10,"bold")).pack(anchor=tk.W, pady=(0,4))
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=4)
        self.tool_arc = tk.StringVar()
        ttk.Entry(row, textvariable=self.tool_arc).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=lambda: self.tool_arc.set(filedialog.askopenfilename(filetypes=[("Archives","*.zip *.7z *.rar *.tar *.gz *.bz2 *.xz")]) or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        btns = ttk.Frame(f); btns.pack(pady=8)
        ttk.Button(btns, text="测试完整性", command=self._on_test).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="修复压缩包", command=self._on_repair).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="查看注释", command=self._on_view_comment).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="添加注释", command=self._on_add_comment).pack(side=tk.LEFT, padx=4)
        self.tool_log = tk.Text(f, height=12, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.tool_log.pack(fill=tk.BOTH, expand=True, pady=6)
    def _on_test(self):
        if not self.tool_arc.get(): messagebox.showwarning("","Select archive"); return
        self.tool_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_test, daemon=True).start()
    def _do_test(self):
        def log(m): self.root.after(0, lambda: self._log(self.tool_log, m))
        t0 = time.time()
        ok, out = do_test(self.tool_arc.get())
        log(out)
        add_history("完整性测试", self.tool_arc.get(), "", "success" if ok else "failed", "", 0, time.time()-t0)
        self.root.after(0, lambda: messagebox.showinfo("Result", "完整性正常！" if ok else "测试失败，文件可能损坏"))
    def _on_repair(self):
        if not self.tool_arc.get(): messagebox.showwarning("","Select archive"); return
        outdir = os.path.dirname(self.tool_arc.get())
        t0 = time.time()
        ok, out = do_repair(self.tool_arc.get(), outdir)
        add_history("修复", self.tool_arc.get(), outdir, "success" if ok else "failed", "", 0, time.time()-t0)
        self.tool_log.delete("1.0", tk.END); self._log(self.tool_log, out)
        messagebox.showinfo("Done", "修复完成" if ok else "修复失败")
    def _on_view_comment(self):
        if not self.tool_arc.get(): messagebox.showwarning("","Select archive"); return
        sz = SEVEN_ZIP or "7z"
        code,o,e = run_cmd([sz,"l",self.tool_arc.get()])
        self.tool_log.delete("1.0", tk.END); self._log(self.tool_log, o+e)
    def _on_add_comment(self):
        if not self.tool_arc.get(): messagebox.showwarning("","Select archive"); return
        comment = simpledialog.askstring("添加注释", "输入注释内容：")
        if not comment: return
        sz = SEVEN_ZIP or "7z"; tmp = tempfile.mktemp(suffix=".txt")
        with open(tmp,"w",encoding="utf-8") as f: f.write(comment)
        code,o,e = run_cmd([sz,"a",self.tool_arc.get(),"-mx0",tmp])
        os.remove(tmp)
        add_history("添加注释", self.tool_arc.get(), "", "success" if code==0 else "failed", comment, 0, 0)
        messagebox.showinfo("Done","注释已添加" if code==0 else "添加失败")

    def _build_history_tab(self, nb):
        """v3.1新增：操作历史记录"""
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  历史记录  ")
        top = ttk.Frame(f); top.pack(fill=tk.X, pady=(0,6))
        ttk.Label(top, text="所有压缩/解压/转换操作都会自动记录到本地：", foreground="gray").pack(side=tk.LEFT)
        btns = ttk.Frame(f); btns.pack(fill=tk.X, pady=4)
        ttk.Button(btns, text="刷新", command=self._refresh_history).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="导出日志", command=self._export_history).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="清空记录", command=self._clear_history).pack(side=tk.LEFT, padx=2)
        ttk.Label(btns, text=f"日志文件: {LOG_FILE}", foreground="gray").pack(side=tk.LEFT, padx=10)
        cols = ("time","action","source","output","result","detail","size","elapsed")
        self.hist_tree = ttk.Treeview(f, columns=cols, show="headings", height=15)
        headers = [("time","时间",140),("action","操作",80),("source","源文件",250),("output","输出",200),("result","结果",60),("detail","详情",150),("size","大小",80),("elapsed","耗时",60)]
        for c,t,w in headers:
            self.hist_tree.heading(c, text=t); self.hist_tree.column(c, width=w, anchor=tk.W)
        self.hist_tree.pack(fill=tk.BOTH, expand=True, pady=6)
        self.hist_tree.bind("<Double-1>", self._on_hist_doubleclick)
        self._refresh_history()
    def _refresh_history(self):
        self.hist_tree.delete(*self.hist_tree.get_children())
        records = load_history()
        for r in reversed(records):
            self.hist_tree.insert("", tk.END, values=(
                r.get("time",""), r.get("action",""), r.get("source","")[:60],
                r.get("output","")[:50], r.get("result",""), r.get("detail","")[:40],
                f"{r.get('size',0):,}B" if r.get('size',0)>0 else "",
                f"{r.get('elapsed',0):.1f}s"
            ))
    def _export_history(self):
        records = load_history()
        if not records: messagebox.showinfo("","暂无记录"); return
        p = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text","*.txt"),("JSON","*.json")])
        if not p: return
        try:
            if p.endswith(".json"):
                with open(p,"w",encoding="utf-8") as f: json.dump(records, f, ensure_ascii=False, indent=2)
            else:
                with open(p,"w",encoding="utf-8") as f:
                    for r in records:
                        f.write(f"[{r['time']}] {r['action']} | {r['source']} -> {r['output']} | {r['result']} | {r['detail']} | {r['size']}B | {r['elapsed']}s\n")
            messagebox.showinfo("Done", f"已导出到: {p}")
        except Exception as e: messagebox.showerror("Error", str(e))
    def _clear_history(self):
        if messagebox.askyesno("确认", "确定要清空所有历史记录吗？"):
            save_history([]); self._refresh_history(); messagebox.showinfo("Done","已清空")
    def _on_hist_doubleclick(self, event):
        sel = self.hist_tree.selection()
        if not sel: return
        item = self.hist_tree.item(sel[0])
        vals = item["values"]
        detail = f"时间: {vals[0]}\n操作: {vals[1]}\n源: {vals[2]}\n输出: {vals[3]}\n结果: {vals[4]}\n详情: {vals[5]}\n大小: {vals[6]}\n耗时: {vals[7]}"
        messagebox.showinfo("操作详情", detail)

    def _build_settings_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  设置  ")
        ttk.Label(f, text="界面：", font=("Segoe UI",10,"bold")).pack(anchor=tk.W, pady=(0,4))
        self.dark_var = tk.BooleanVar(value=dark_mode)
        ttk.Checkbutton(f, text="深色模式", variable=self.dark_var, command=self._toggle_dark).pack(anchor=tk.W, pady=4)
        ttk.Label(f, text="文件关联：", font=("Segoe UI",10,"bold")).pack(anchor=tk.W, pady=(12,4))
        btns = ttk.Frame(f); btns.pack(pady=4)
        ttk.Button(btns, text="关联所有压缩格式", command=lambda: (set_file_association(True), messagebox.showinfo("Done","关联成功"))).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="取消关联", command=lambda: (set_file_association(False), messagebox.showinfo("Done","已取消关联"))).pack(side=tk.LEFT, padx=4)
        ttk.Separator(f).pack(fill=tk.X, pady=16)
        ttk.Label(f, text="压缩解压工具 v3.1\n\n支持格式：ZIP/7Z/RAR/TAR/GZ/BZ2/XZ/ISO/CAB/LZMA/ZSTD\n底层调用 7-Zip / NanaZip\n\nv3.1更新：修复智能压缩临时文件bug + 操作日志历史记录\n\nAI 辅助开发，开源地址：github.com/Blazar118/ZipTool",
                    justify=tk.LEFT, foreground="gray").pack(anchor=tk.W, pady=8)
    def _toggle_dark(self):
        global dark_mode
        dark_mode = self.dark_var.get()
        apply_theme(self.root, self.style)

def main():
    if DND_AVAILABLE: root = TkinterDnD.Tk()
    else: root = tk.Tk()
    app = ZipToolApp(root)
    if len(sys.argv) >= 3:
        if sys.argv[1] == "--compress":
            app.compress_files = [sys.argv[2]]; app.comp_list.insert(tk.END, sys.argv[2]); app._update_comp_out()
        elif sys.argv[1] == "--extract":
            app.decomp_path.set(sys.argv[2]); app.decomp_out.set(os.path.dirname(sys.argv[2]))
    root.mainloop()

if __name__ == "__main__":
    main()
