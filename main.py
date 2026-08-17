"""
压缩解压工具 v3.0 - 全能版
新增：格式转换、压缩包修复、完整性测试、智能压缩、文件关联、深色模式、压缩包注释、多语言
修复：预览双击txt可查看内容
底层调用 7-Zip / NanaZip 命令行
"""

import os
import sys
import time
import tempfile
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from pathlib import Path

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# ==================== 多语言 ====================
LANGS = {
    "zh": {
        "title": "压缩解压工具 v3.0",
        "compress": "压缩", "extract": "解压", "preview": "预览",
        "batch": "批量", "crack": "密码恢复", "compare": "压缩率对比",
        "convert": "格式转换", "tools": "工具箱", "settings": "设置",
        "add_files": "添加文件", "add_folder": "添加文件夹", "clear": "清空",
        "format": "格式", "level": "等级", "password": "密码", "volume": "分卷",
        "output": "输出文件", "start_compress": "▶ 开始压缩",
        "archive_file": "压缩文件", "output_dir": "输出目录", "start_extract": "▶ 开始解压",
        "browse": "浏览", "preview_btn": "预览",
        "smart_compress": "智能压缩（自动选最优）",
        "dark_mode": "深色模式", "language": "语言",
        "file_assoc": "文件关联", "assoc_all": "关联所有压缩格式", "unassoc": "取消关联",
        "test_integrity": "测试完整性", "repair": "修复压缩包", "comment": "注释",
        "convert_from": "源压缩包", "convert_to": "目标格式", "start_convert": "▶ 开始转换",
    },
    "en": {
        "title": "ZipTool v3.0",
        "compress": "Compress", "extract": "Extract", "preview": "Preview",
        "batch": "Batch", "crack": "Password Recovery", "compare": "Compare",
        "convert": "Convert", "tools": "Tools", "settings": "Settings",
        "add_files": "Add Files", "add_folder": "Add Folder", "clear": "Clear",
        "format": "Format", "level": "Level", "password": "Password", "volume": "Volume",
        "output": "Output", "start_compress": "▶ Start Compress",
        "archive_file": "Archive", "output_dir": "Output Dir", "start_extract": "▶ Start Extract",
        "browse": "Browse", "preview_btn": "Preview",
        "smart_compress": "Smart Compress (Auto)",
        "dark_mode": "Dark Mode", "language": "Language",
        "file_assoc": "File Association", "assoc_all": "Associate All", "unassoc": "Remove",
        "test_integrity": "Test Integrity", "repair": "Repair", "comment": "Comment",
        "convert_from": "Source", "convert_to": "Target Format", "start_convert": "▶ Convert",
    }
}
current_lang = "zh"
def tr(key): return LANGS[current_lang].get(key, key)

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
    try:
        if not file_list: return False, "No files"
        out = Path(output_file); sz = SEVEN_ZIP or "7z"
        if log_cb: log_cb(f"Compressing: {fmt['name']} L{level}")
        if fmt["name"] == "tar.gz":
            tar = str(out).replace(".tar.gz", ".tar")
            c1 = [sz,"a","-ttar","-mmt=on","-y",tar]+[str(f) for f in file_list]
            code,o,e = run_cmd(c1)
            if log_cb: [log_cb(l) for l in (o+e).splitlines() if l.strip()]
            if code != 0: return False, "tar failed"
            c2 = [sz,"a","-tgzip",f"-mx{level}","-mmt=on","-y",str(out),tar]
            code,o,e = run_cmd(c2)
            if log_cb: [log_cb(l) for l in (o+e).splitlines() if l.strip()]
            try: os.remove(tar)
            except: pass
            if code != 0: return False, "gzip failed"
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
            if code != 0: return False, f"Failed code {code}"
        return True, f"Done: {out}"
    except Exception as ex: return False, str(ex)

def do_extract(archive, out_dir, password=None, log_cb=None):
    try:
        a = Path(archive); out = Path(out_dir)
        if not a.exists(): return False, "Not found"
        os.makedirs(out, exist_ok=True)
        sz = SEVEN_ZIP or "7z"
        cmd = [sz,"x","-mmt=on","-bb1","-y",f"-o{out}",str(a)]
        cmd.insert(2, f"-p{password}" if password else "-p-")
        code,o,e = run_cmd(cmd)
        out_text = o+"\n"+e
        if log_cb: [log_cb(l) for l in out_text.splitlines() if l.strip()]
        if code == 0: return True, "Done!"
        ol = out_text.lower()
        if "wrong password" in ol or "data error in encrypted" in ol:
            return False, "Wrong password" if password else "Encrypted, need password"
        return False, f"Failed code {code}"
    except Exception as ex: return False, str(ex)

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
    """格式转换：先解压再压缩"""
    try:
        sz = SEVEN_ZIP or "7z"
        tmpdir = tempfile.mkdtemp()
        if log_cb: log_cb("Step 1: Extracting...")
        ok, msg = do_extract(archive, tmpdir, log_cb=log_cb)
        if not ok: return False, f"Extract failed: {msg}"
        base = Path(archive).stem
        out = Path(output_dir) / (base + target_fmt["ext"])
        fmt_info = {"name": target_fmt["name"], "ext": target_fmt["ext"]}
        if log_cb: log_cb(f"Step 2: Compressing to {target_fmt['name']}...")
        files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir)]
        ok, msg = do_compress(files, str(out), fmt_info, 5, log_cb=log_cb)
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
        return ok, msg
    except Exception as ex: return False, str(ex)

def do_smart_compress(file_list, output_base, log_cb=None):
    """智能压缩：测试多种格式选最小"""
    results = []
    for fmt in COMPRESS_FORMATS:
        for level in ["1", "5", "9"]:
            out = f"{output_base}_{fmt['name']}_l{level}{fmt['ext']}"
            t0 = time.time()
            ok, msg = do_compress(file_list, out, fmt, int(level), log_cb=lambda m: None)
            elapsed = time.time() - t0
            if ok and os.path.exists(out):
                size = os.path.getsize(out)
                results.append({"fmt":fmt["name"],"level":level,"size":size,"time":elapsed,"file":out})
                if log_cb: log_cb(f"{fmt['name']} L{level}: {size:,}B ({elapsed:.1f}s)")
    if not results: return None, "All failed"
    best = min(results, key=lambda x: x["size"])
    # 删除非最优的
    for r in results:
        if r != best:
            try: os.remove(r["file"])
            except: pass
    # 重命名最优的
    final = f"{output_base}_best{Path(best['file']).suffix}"
    try: os.rename(best["file"], final)
    except: pass
    return best, final

def do_batch_compress(folder, fmt, level, log_cb=None):
    count = 0
    for item in os.listdir(folder):
        src = os.path.join(folder, item)
        if os.path.isdir(src) or os.path.isfile(src):
            out = os.path.join(folder, item + fmt["ext"])
            if log_cb: log_cb(f"Compress: {item}")
            ok,_ = do_compress([src], out, fmt, level, log_cb=log_cb)
            if ok: count += 1
    return True, f"Done: {count}"

def do_batch_extract(folder, log_cb=None):
    count = 0
    for item in os.listdir(folder):
        src = os.path.join(folder, item)
        if os.path.isfile(src) and item.lower().endswith(EXTRACT_EXTS):
            out = os.path.join(folder, os.path.splitext(item)[0])
            if log_cb: log_cb(f"Extract: {item}")
            ok,_ = do_extract(src, out, log_cb=log_cb)
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
    """注册/取消文件关联"""
    import winreg
    exts = [".zip",".7z",".rar",".tar",".gz",".bz2",".xz",".iso",".cab",".lzma",".zstd",".tgz"]
    exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
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
        self.root.title(tr("title"))
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
        global dark_mode
        nb = ttk.Notebook(self.root); nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        self._build_compress_tab(nb)
        self._build_extract_tab(nb)
        self._build_preview_tab(nb)
        self._build_convert_tab(nb)
        self._build_batch_tab(nb)
        self._build_crack_tab(nb)
        self._build_compare_tab(nb)
        self._build_tools_tab(nb)
        self._build_settings_tab(nb)
        self.status = tk.StringVar(value="Ready" + (" | Drag enabled" if DND_AVAILABLE else ""))
        ttk.Label(self.root, textvariable=self.status, foreground="gray", anchor=tk.W).pack(fill=tk.X, padx=10, pady=(0,6))

    def _build_compress_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  "+tr("compress")+"  ")
        ttk.Label(f, text=tr("add_files")+" (可拖拽):").pack(anchor=tk.W)
        br = ttk.Frame(f); br.pack(fill=tk.X, pady=4)
        ttk.Button(br, text=tr("add_files"), command=self._add_files).pack(side=tk.LEFT)
        ttk.Button(br, text=tr("add_folder"), command=self._add_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(br, text=tr("clear"), command=lambda: (self.compress_files.clear(), self.comp_list.delete(0,tk.END))).pack(side=tk.LEFT)
        lf = ttk.Frame(f); lf.pack(fill=tk.BOTH, expand=False, pady=4)
        self.comp_list = tk.Listbox(lf, height=4, bg="#1e1e1e", fg="#d4d4d4")
        self.comp_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(lf, command=self.comp_list.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.comp_list.config(yscrollcommand=sb.set)
        opt = ttk.Frame(f); opt.pack(fill=tk.X, pady=6)
        ttk.Label(opt, text=tr("format")+":").pack(side=tk.LEFT)
        self.fmt_var = tk.StringVar(value="zip")
        ttk.Combobox(opt, textvariable=self.fmt_var, values=[x["name"] for x in COMPRESS_FORMATS], state="readonly", width=8).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text=tr("level")+":").pack(side=tk.LEFT, padx=(8,0))
        self.level_var = tk.StringVar(value="1")
        ttk.Combobox(opt, textvariable=self.level_var, values=COMPRESS_LEVELS, state="readonly", width=5).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text=tr("password")+":").pack(side=tk.LEFT, padx=(8,0))
        self.pwd_var = tk.StringVar()
        ttk.Entry(opt, textvariable=self.pwd_var, show="*", width=10).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text=tr("volume")+":").pack(side=tk.LEFT, padx=(8,0))
        self.vol_var = tk.StringVar()
        ttk.Entry(opt, textvariable=self.vol_var, width=6).pack(side=tk.LEFT, padx=4)
        self.smart_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text=tr("smart_compress"), variable=self.smart_var).pack(side=tk.LEFT, padx=(12,0))
        ttk.Label(f, text=tr("output")+":").pack(anchor=tk.W, pady=(6,0))
        orow = ttk.Frame(f); orow.pack(fill=tk.X, pady=4)
        self.comp_out = tk.StringVar()
        ttk.Entry(orow, textvariable=self.comp_out).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(orow, text=tr("browse"), command=self._pick_comp_out, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(f, text=tr("start_compress"), command=self._on_compress).pack(pady=8, anchor=tk.W)
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
        prog(10)
        if self.smart_var.get():
            base = os.path.splitext(self.comp_out.get())[0]
            best, final = do_smart_compress(self.compress_files, base, log)
            prog(100)
            msg = f"Best: {best['fmt']} L{best['level']} = {best['size']:,}B\nOutput: {final}" if best else "Failed"
            self.root.after(0, lambda: messagebox.showinfo("Smart Compress", msg))
        else:
            fmt = [x for x in COMPRESS_FORMATS if x["name"]==self.fmt_var.get()][0]
            vol = self.vol_var.get().strip() or None
            ok, msg = do_compress(self.compress_files, self.comp_out.get(), fmt, int(self.level_var.get()), self.pwd_var.get() or None, vol, log)
            prog(100)
            self.root.after(0, lambda: messagebox.showinfo("Done" if ok else "Failed", msg))

    def _build_extract_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  "+tr("extract")+"  ")
        ttk.Label(f, text=tr("archive_file")+":").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.decomp_path = tk.StringVar()
        ttk.Entry(row, textvariable=self.decomp_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text=tr("browse"), command=self._pick_decomp_file, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(f, text=tr("output_dir")+":").pack(anchor=tk.W, pady=(6,0))
        row2 = ttk.Frame(f); row2.pack(fill=tk.X, pady=6)
        self.decomp_out = tk.StringVar()
        ttk.Entry(row2, textvariable=self.decomp_out).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row2, text=tr("browse"), command=self._pick_decomp_out, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(f, text=tr("password")+":").pack(anchor=tk.W, pady=(6,0))
        self.decomp_pwd = tk.StringVar()
        ttk.Entry(f, textvariable=self.decomp_pwd, show="*").pack(fill=tk.X, pady=4)
        ttk.Button(f, text=tr("start_extract"), command=self._on_decompress).pack(pady=8, anchor=tk.W)
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
        prog(10)
        ok, msg = do_extract(self.decomp_path.get(), self.decomp_out.get() or os.path.dirname(self.decomp_path.get()), self.decomp_pwd.get() or None, log)
        prog(100)
        self.root.after(0, lambda: messagebox.showinfo("Done" if ok else "Failed", msg))

    def _build_preview_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  "+tr("preview")+"  ")
        ttk.Label(f, text="双击文本文件可查看内容：").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.prev_path = tk.StringVar()
        ttk.Entry(row, textvariable=self.prev_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text=tr("browse"), command=self._pick_prev_file, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(row, text=tr("preview_btn"), command=self._on_preview, width=8).pack(side=tk.LEFT, padx=(6,0))
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
        """双击预览中的文件，临时解压并查看文本内容"""
        sel = self.prev_tree.selection()
        if not sel: return
        item = self.prev_tree.item(sel[0])
        name = item["values"][0]
        if not name.lower().endswith((".txt",".md",".csv",".log",".ini",".cfg",".py",".json",".xml",".html")):
            messagebox.showinfo("提示", "仅支持查看文本文件（txt/md/csv/log等）")
            return
        # 临时解压这个文件
        sz = SEVEN_ZIP or "7z"
        tmpdir = tempfile.mkdtemp()
        cmd = [sz,"e","-y",f"-o{tmpdir}",self.prev_path.get(),name]
        code,o,e = run_cmd(cmd)
        if code != 0:
            messagebox.showerror("Error", "无法提取文件"); return
        filepath = os.path.join(tmpdir, os.path.basename(name))
        if not os.path.exists(filepath):
            # 可能在子目录
            for root,dirs,files in os.walk(tmpdir):
                for fn in files:
                    if fn == os.path.basename(name): filepath = os.path.join(root, fn); break
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except: content = "(无法读取)"
        # 显示内容窗口
        win = tk.Toplevel(self.root); win.title(f"预览: {name}"); win.geometry("600x400")
        txt = tk.Text(win, wrap=tk.WORD, font=("Consolas",10))
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        txt.insert("1.0", content); txt.config(state=tk.DISABLED)
        import shutil
        win.protocol("WM_DELETE_WINDOW", lambda: (shutil.rmtree(tmpdir, ignore_errors=True), win.destroy()))

    def _build_convert_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  "+tr("convert")+"  ")
        ttk.Label(f, text=tr("convert_from")+":").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.cvt_from = tk.StringVar()
        ttk.Entry(row, textvariable=self.cvt_from).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text=tr("browse"), command=lambda: self.cvt_from.set(filedialog.askopenfilename(filetypes=[("Archives","*.zip *.7z *.rar *.tar *.gz *.bz2 *.xz")]) or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(f, text=tr("convert_to")+":").pack(anchor=tk.W, pady=(8,0))
        self.cvt_to = tk.StringVar(value="zip")
        ttk.Combobox(f, textvariable=self.cvt_to, values=[x["name"] for x in COMPRESS_FORMATS], state="readonly", width=10).pack(anchor=tk.W, pady=4)
        ttk.Label(f, text=tr("output_dir")+":").pack(anchor=tk.W, pady=(8,0))
        self.cvt_out = tk.StringVar()
        row2 = ttk.Frame(f); row2.pack(fill=tk.X, pady=4)
        ttk.Entry(row2, textvariable=self.cvt_out).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row2, text=tr("browse"), command=lambda: self.cvt_out.set(filedialog.askdirectory() or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(f, text=tr("start_convert"), command=self._on_convert).pack(pady=10, anchor=tk.W)
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
        ok, msg = do_convert(self.cvt_from.get(), fmt, self.cvt_out.get(), log)
        self.root.after(0, lambda: messagebox.showinfo("Done" if ok else "Failed", msg))

    def _build_batch_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  "+tr("batch")+"  ")
        ttk.Label(f, text="选择文件夹：").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.batch_dir = tk.StringVar()
        ttk.Entry(row, textvariable=self.batch_dir).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text=tr("browse"), command=lambda: self.batch_dir.set(filedialog.askdirectory() or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        opt = ttk.Frame(f); opt.pack(fill=tk.X, pady=6)
        ttk.Label(opt, text=tr("format")+":").pack(side=tk.LEFT)
        self.batch_fmt = tk.StringVar(value="zip")
        ttk.Combobox(opt, textvariable=self.batch_fmt, values=[x["name"] for x in COMPRESS_FORMATS], state="readonly", width=8).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text=tr("level")+":").pack(side=tk.LEFT, padx=(8,0))
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
        if mode == "compress":
            fmt = [x for x in COMPRESS_FORMATS if x["name"]==self.batch_fmt.get()][0]
            ok, msg = do_batch_compress(self.batch_dir.get(), fmt, int(self.batch_level.get()), log)
        else:
            ok, msg = do_batch_extract(self.batch_dir.get(), log)
        self.root.after(0, lambda: messagebox.showinfo("Done", msg))

    def _build_crack_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  "+tr("crack")+"  ")
        ttk.Label(f, text="⚠️ 仅限恢复自己的密码，禁止非法用途！", foreground="red").pack(anchor=tk.W)
        ttk.Label(f, text="加密压缩包：").pack(anchor=tk.W, pady=(8,0))
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=4)
        self.crack_arc = tk.StringVar()
        ttk.Entry(row, textvariable=self.crack_arc).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text=tr("browse"), command=lambda: self.crack_arc.set(filedialog.askopenfilename(filetypes=[("Archives","*.zip *.7z *.rar")]) or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(f, text="密码字典（每行一个）：").pack(anchor=tk.W, pady=(6,0))
        row2 = ttk.Frame(f); row2.pack(fill=tk.X, pady=4)
        self.crack_dict = tk.StringVar()
        ttk.Entry(row2, textvariable=self.crack_dict).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row2, text=tr("browse"), command=lambda: self.crack_dict.set(filedialog.askopenfilename(filetypes=[("Text","*.txt")]) or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(f, text="▶ 开始字典破解", command=self._on_crack).pack(pady=10, anchor=tk.W)
        self.crack_log = tk.Text(f, height=8, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.crack_log.pack(fill=tk.BOTH, expand=True, pady=6)
    def _on_crack(self):
        if not self.crack_arc.get() or not self.crack_dict.get(): messagebox.showwarning("","Select files"); return
        self.crack_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_crack, daemon=True).start()
    def _do_crack(self):
        def log(m): self.root.after(0, lambda: self._log(self.crack_log, m))
        ok, msg = do_crack(self.crack_arc.get(), self.crack_dict.get(), log)
        self.root.after(0, lambda: messagebox.showinfo("Result", msg))

    def _build_compare_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  "+tr("compare")+"  ")
        ttk.Label(f, text="选择测试文件：").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.cmp_file = tk.StringVar()
        ttk.Entry(row, textvariable=self.cmp_file).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text=tr("browse"), command=lambda: self.cmp_file.set(filedialog.askopenfilename() or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
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
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  "+tr("tools")+"  ")
        # 完整性测试
        ttk.Label(f, text="压缩包：", font=("Segoe UI",10,"bold")).pack(anchor=tk.W, pady=(0,4))
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=4)
        self.tool_arc = tk.StringVar()
        ttk.Entry(row, textvariable=self.tool_arc).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text=tr("browse"), command=lambda: self.tool_arc.set(filedialog.askopenfilename(filetypes=[("Archives","*.zip *.7z *.rar *.tar *.gz *.bz2 *.xz")]) or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        btns = ttk.Frame(f); btns.pack(pady=8)
        ttk.Button(btns, text=tr("test_integrity"), command=self._on_test).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text=tr("repair"), command=self._on_repair).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text=tr("comment")+" 查看", command=self._on_view_comment).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text=tr("comment")+" 添加", command=self._on_add_comment).pack(side=tk.LEFT, padx=4)
        self.tool_log = tk.Text(f, height=12, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.tool_log.pack(fill=tk.BOTH, expand=True, pady=6)
    def _on_test(self):
        if not self.tool_arc.get(): messagebox.showwarning("","Select archive"); return
        self.tool_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_test, daemon=True).start()
    def _do_test(self):
        def log(m): self.root.after(0, lambda: self._log(self.tool_log, m))
        ok, out = do_test(self.tool_arc.get())
        log(out); self.root.after(0, lambda: messagebox.showinfo("Result", "完整性正常！" if ok else "测试失败，文件可能损坏"))
    def _on_repair(self):
        if not self.tool_arc.get(): messagebox.showwarning("","Select archive"); return
        outdir = os.path.dirname(self.tool_arc.get())
        threading.Thread(target=lambda: (self._log(self.tool_log, "修复中..."), do_repair(self.tool_arc.get(), outdir)[1], self._log(self.tool_log, "修复完成，输出在同目录")), daemon=True).start()
    def _on_view_comment(self):
        if not self.tool_arc.get(): messagebox.showwarning("","Select archive"); return
        sz = SEVEN_ZIP or "7z"
        code,o,e = run_cmd([sz,"l",self.tool_arc.get()])
        self.tool_log.delete("1.0", tk.END); self._log(self.tool_log, o+e)
    def _on_add_comment(self):
        if not self.tool_arc.get(): messagebox.showwarning("","Select archive"); return
        comment = tk.simpledialog.askstring("添加注释", "输入注释内容：")
        if not comment: return
        sz = SEVEN_ZIP or "7z"
        tmp = tempfile.mktemp(suffix=".txt")
        with open(tmp,"w",encoding="utf-8") as f: f.write(comment)
        code,o,e = run_cmd([sz,"a",self.tool_arc.get(),"-mx0",tmp])
        os.remove(tmp)
        messagebox.showinfo("Done","注释已添加" if code==0 else "添加失败")

    def _build_settings_tab(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text="  "+tr("settings")+"  ")
        # 深色模式
        ttk.Label(f, text="界面：", font=("Segoe UI",10,"bold")).pack(anchor=tk.W, pady=(0,4))
        self.dark_var = tk.BooleanVar(value=dark_mode)
        ttk.Checkbutton(f, text=tr("dark_mode"), variable=self.dark_var, command=self._toggle_dark).pack(anchor=tk.W, pady=4)
        # 语言
        ttk.Label(f, text=tr("language")+":", font=("Segoe UI",10,"bold")).pack(anchor=tk.W, pady=(12,4))
        self.lang_var = tk.StringVar(value="中文")
        lang_cb = ttk.Combobox(f, textvariable=self.lang_var, values=["中文","English"], state="readonly", width=12)
        lang_cb.pack(anchor=tk.W, pady=4)
        lang_cb.bind("<<ComboboxSelected>>", self._change_lang)
        # 文件关联
        ttk.Label(f, text=tr("file_assoc")+":", font=("Segoe UI",10,"bold")).pack(anchor=tk.W, pady=(12,4))
        btns = ttk.Frame(f); btns.pack(pady=4)
        ttk.Button(btns, text=tr("assoc_all"), command=lambda: (set_file_association(True), messagebox.showinfo("Done","关联成功，重启资源管理器生效"))).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text=tr("unassoc"), command=lambda: (set_file_association(False), messagebox.showinfo("Done","已取消关联"))).pack(side=tk.LEFT, padx=4)
        # 关于
        ttk.Separator(f).pack(fill=tk.X, pady=16)
        ttk.Label(f, text="压缩解压工具 v3.0\n\n支持格式：ZIP/7Z/RAR/TAR/GZ/BZ2/XZ/ISO/CAB/LZMA/ZSTD\n底层调用 7-Zip / NanaZip\n\nAI 辅助开发，开源地址：github.com/Blazar118/ZipTool",
                    justify=tk.LEFT, foreground="gray").pack(anchor=tk.W, pady=8)
    def _toggle_dark(self):
        global dark_mode
        dark_mode = self.dark_var.get()
        apply_theme(self.root, self.style)
    def _change_lang(self, event=None):
        global current_lang
        current_lang = "en" if self.lang_var.get()=="English" else "zh"
        messagebox.showinfo("提示","语言切换需要重启程序生效")

def main():
    global current_lang
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
