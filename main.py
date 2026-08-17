"""
压缩解压工具 v2.0 - 增强版
功能：压缩、解压、预览、拖拽、分卷、密码恢复、批量操作、压缩率对比
底层调用 7-Zip / NanaZip 命令行
"""

import os
import sys
import time
import struct
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# 拖拽支持（可选）
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# ==================== 7z 路径检测 ====================
SEVEN_ZIP = None
def find_7z():
    global SEVEN_ZIP
    for name in ["7z.exe", "7z", "NanaZipC.exe", "NanaZipC"]:
        try:
            r = subprocess.run([name, "--version"], capture_output=True, timeout=5)
            if r.returncode == 0 or "7-Zip" in r.stdout.decode("gbk", errors="ignore"):
                SEVEN_ZIP = name
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    for p in [r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files\NanaZip\NanaZipC.exe"]:
        if os.path.exists(p):
            SEVEN_ZIP = p
            return
find_7z()

def run_cmd(cmd, timeout=600):
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        out = result.stdout.decode("gbk", errors="ignore")
        err = result.stderr.decode("gbk", errors="ignore")
        return result.returncode, out, err
    except subprocess.TimeoutExpired:
        return -1, "", "超时"
    except Exception as e:
        return -1, "", str(e)

# ==================== 格式定义 ====================
COMPRESS_FORMATS = [
    {"name": "7z", "ext": ".7z", "cmd_type": "7z"},
    {"name": "zip", "ext": ".zip", "cmd_type": "zip"},
    {"name": "tar.gz", "ext": ".tar.gz", "cmd_type": "tar.gz"},
]
COMPRESS_LEVELS = [str(i) for i in range(10)]
EXTRACT_EXTS = (".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".iso", ".cab", ".lzma", ".zstd", ".tgz")

# ==================== 核心功能函数 ====================
def do_compress(file_list, output_file, fmt_info, level, password=None, volume_size=None, log_cb=None):
    """压缩文件，支持分卷"""
    try:
        if not file_list:
            return False, "没有待压缩文件"
        out_path = Path(output_file)
        cmd_type = fmt_info["cmd_type"]
        seven_zip = SEVEN_ZIP or "7z"
        if log_cb:
            log_cb(f"开始压缩，格式:{fmt_info['name']},等级:{level}")
        if cmd_type == "tar.gz":
            tar_path = str(out_path).replace(".tar.gz", ".tar")
            cmd1 = [seven_zip, "a", "-ttar", "-mmt=on", "-bb1", "-y", tar_path] + [str(f) for f in file_list]
            code1, out1, err1 = run_cmd(cmd1)
            if log_cb:
                for line in (out1 + err1).splitlines():
                    if line.strip(): log_cb(line.strip())
            if code1 != 0: return False, "tar打包失败"
            cmd2 = [seven_zip, "a", "-tgzip", f"-mx{level}", "-mmt=on", "-bb1", "-y", str(out_path), tar_path]
            code2, out2, err2 = run_cmd(cmd2)
            if log_cb:
                for line in (out2 + err2).splitlines():
                    if line.strip(): log_cb(line.strip())
            try: os.remove(tar_path)
            except OSError: pass
            if code2 != 0: return False, "gzip压缩失败"
        else:
            archive_type = "7z" if cmd_type == "7z" else "zip"
            cmd = [seven_zip, "a", f"-t{archive_type}", f"-mx{level}", "-mmt=on", "-bb1", "-y"]
            if archive_type == "7z":
                cmd.append("-m0=LZMA2:d=1m:fb=32")
            if volume_size:
                cmd.append(f"-v{volume_size}")
            if password:
                cmd.append(f"-p{password}")
                if archive_type == "zip":
                    cmd.append("-mem=AES256")
            cmd.append(str(out_path))
            cmd += [str(f) for f in file_list]
            code, out_text, err_text = run_cmd(cmd)
            if log_cb:
                for line in (out_text + err_text).splitlines():
                    if line.strip(): log_cb(line.strip())
            if code != 0: return False, f"压缩失败，返回码 {code}"
        return True, f"压缩完成！\n输出文件：{out_path}"
    except PermissionError:
        return False, "权限不足"
    except Exception as e:
        return False, f"异常：{str(e)}"

def do_extract(archive_path, out_dir, password=None, log_cb=None):
    """解压"""
    try:
        archive = Path(archive_path)
        out = Path(out_dir)
        if not archive.exists(): return False, "压缩包不存在"
        os.makedirs(out, exist_ok=True)
        seven_zip = SEVEN_ZIP or "7z"
        cmd = [seven_zip, "x", "-mmt=on", "-bb1", "-y", f"-o{out}", str(archive)]
        if password:
            cmd.insert(2, f"-p{password}")
        else:
            cmd.insert(2, "-p-")
        code, out_text, err_text = run_cmd(cmd)
        output = out_text + "\n" + err_text
        if log_cb:
            for line in output.splitlines():
                if line.strip(): log_cb(line.strip())
        if code == 0: return True, "解压完成！"
        ol = output.lower()
        if "wrong password" in ol or "data error in encrypted" in ol:
            if password: return False, "密码错误"
            else: return False, "该压缩包已加密，请输入密码"
        return False, f"解压失败，返回码 {code}"
    except Exception as e:
        return False, f"异常：{str(e)}"

def do_preview(archive_path, password=None):
    """预览压缩包内容，返回文件列表"""
    seven_zip = SEVEN_ZIP or "7z"
    cmd = [seven_zip, "l", str(archive_path)]
    if password:
        cmd.append(f"-p{password}")
    code, out, err = run_cmd(cmd)
    if code != 0:
        return None, "无法读取，可能已加密或文件损坏"
    files = []
    lines = out.splitlines()
    in_list = False
    for line in lines:
        if "---" in line and not in_list:
            in_list = True
            continue
        if in_list and "---" in line:
            break
        if in_list and line.strip():
            parts = line.split()
            if len(parts) >= 3:
                try:
                    size = int(parts[0]) if parts[0].isdigit() else 0
                    name = " ".join(parts[2:]) if len(parts) > 2 else ""
                    if name:
                        files.append({"name": name, "size": size})
                except:
                    pass
    return files, None

def do_password_crack(archive_path, dict_path, log_cb=None):
    """字典密码恢复（仅限合法用途）"""
    if not os.path.exists(dict_path):
        return False, "字典文件不存在"
    seven_zip = SEVEN_ZIP or "7z"
    found = None
    count = 0
    with open(dict_path, "r", encoding="utf-8", errors="ignore") as f:
        passwords = [line.strip() for line in f if line.strip()]
    total = len(passwords)
    for pwd in passwords:
        count += 1
        if log_cb and count % 10 == 0:
            log_cb(f"尝试中... {count}/{total} 当前: {pwd}")
        cmd = [seven_zip, "t", f"-p{pwd}", "-y", str(archive_path)]
        code, out, err = run_cmd(cmd, timeout=10)
        if code == 0:
            found = pwd
            break
    if found:
        return True, f"密码找到：{found}"
    else:
        return False, f"尝试了{count}个密码，未找到"

def do_batch_compress(folder, fmt_info, level, log_cb=None):
    """批量压缩文件夹内每个文件/子文件夹"""
    fmt = fmt_info["cmd_type"]
    ext = fmt_info["ext"]
    seven_zip = SEVEN_ZIP or "7z"
    count = 0
    for item in os.listdir(folder):
        src = os.path.join(folder, item)
        if os.path.isdir(src) or os.path.isfile(src):
            out = os.path.join(folder, item + ext)
            if log_cb: log_cb(f"压缩: {item}")
            ok, msg = do_compress([src], out, fmt_info, level, log_cb=log_cb)
            if ok: count += 1
    return True, f"批量压缩完成，成功{count}个"

def do_batch_extract(folder, log_cb=None):
    """批量解压文件夹内所有压缩包"""
    count = 0
    for item in os.listdir(folder):
        src = os.path.join(folder, item)
        if os.path.isfile(src) and item.lower().endswith(EXTRACT_EXTS):
            out = os.path.join(folder, os.path.splitext(item)[0])
            if log_cb: log_cb(f"解压: {item}")
            ok, msg = do_extract(src, out, log_cb=log_cb)
            if ok: count += 1
    return True, f"批量解压完成，成功{count}个"

def do_compare(test_file, log_cb=None):
    """压缩率对比测试"""
    results = []
    seven_zip = SEVEN_ZIP or "7z"
    orig_size = os.path.getsize(test_file)
    formats = [
        ("zip", "1", ".zip"), ("zip", "5", ".zip"), ("zip", "9", ".zip"),
        ("7z", "1", ".7z"), ("7z", "5", ".7z"), ("7z", "9", ".7z"),
    ]
    import tempfile
    tmpdir = tempfile.mkdtemp()
    for fmt, level, ext in formats:
        out = os.path.join(tmpdir, f"test_{fmt}_{level}{ext}")
        t0 = time.time()
        cmd = [seven_zip, "a", f"-t{fmt}", f"-mx{level}", "-mmt=on", "-y", out, test_file]
        if fmt == "7z": cmd.append("-m0=LZMA2:d=1m:fb=32")
        code, o, e = run_cmd(cmd)
        elapsed = time.time() - t0
        if code == 0 and os.path.exists(out):
            csize = os.path.getsize(out)
            ratio = csize / orig_size * 100
            results.append({"format": fmt, "level": level, "size": csize, "ratio": ratio, "time": elapsed})
            if log_cb: log_cb(f"{fmt} L{level}: {csize:,}B ({ratio:.1f}%) {elapsed:.2f}s")
        try: os.remove(out)
        except: pass
    return results, None

# ==================== GUI ====================
class ZipToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("压缩解压工具 v2.0")
        self.root.geometry("820x640")
        self.root.minsize(720, 560)
        self.compress_files = []
        self._build_ui()
        if DND_AVAILABLE:
            self._setup_dragdrop()

    def _build_ui(self):
        style = ttk.Style()
        try: style.theme_use("clam")
        except: pass
        # 顶部标题
        tf = ttk.Frame(self.root, padding=(16, 10, 16, 4))
        tf.pack(fill=tk.X)
        ttk.Label(tf, text="压缩解压工具 v2.0", font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT)
        ttk.Label(tf, text="  预览·拖拽·分卷·密码恢复·批量·对比", foreground="gray").pack(side=tk.LEFT, pady=(6,0))
        # 标签页
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self._build_compress_tab(nb)
        self._build_extract_tab(nb)
        self._build_preview_tab(nb)
        self._build_batch_tab(nb)
        self._build_crack_tab(nb)
        self._build_compare_tab(nb)
        # 底部状态栏
        self.status = tk.StringVar(value="就绪" + (" | 拖拽已启用" if DND_AVAILABLE else " | 拖拽未启用(需tkinterdnd2)"))
        ttk.Label(self.root, textvariable=self.status, foreground="gray", anchor=tk.W).pack(fill=tk.X, padx=12, pady=(0,8))

    def _log(self, widget, msg):
        widget.insert(tk.END, msg + "\n")
        widget.see(tk.END)
        self.root.update_idletasks()

    def _setup_dragdrop(self):
        """设置全局拖拽"""
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self._on_drop)

    def _on_drop(self, event):
        """拖拽文件处理"""
        files = self.root.tk.splitlist(event.data)
        if not files: return
        archives = [f for f in files if f.lower().endswith(EXTRACT_EXTS)]
        others = [f for f in files if not f.lower().endswith(EXTRACT_EXTS)]
        if archives and not others:
            # 全是压缩包，切换到解压页
            self.decomp_path.set(archives[0])
            self.decomp_out.set(os.path.dirname(archives[0]))
            messagebox.showinfo("拖拽", f"已加载{len(archives)}个压缩包到解压页")
        else:
            # 添加到压缩页
            for f in files:
                if f not in self.compress_files:
                    self.compress_files.append(f)
                    self.comp_list.insert(tk.END, f)
            self._update_comp_out()
            messagebox.showinfo("拖拽", f"已添加{len(files)}个文件到压缩页")

    # ---------- 压缩页 ----------
    def _build_compress_tab(self, nb):
        f = ttk.Frame(nb, padding=12); nb.add(f, text="  压缩  ")
        ttk.Label(f, text="待压缩文件（可拖拽到窗口）：").pack(anchor=tk.W)
        br = ttk.Frame(f); br.pack(fill=tk.X, pady=4)
        ttk.Button(br, text="添加文件", command=self._add_files).pack(side=tk.LEFT)
        ttk.Button(br, text="添加文件夹", command=self._add_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(br, text="清空", command=lambda: (self.compress_files.clear(), self.comp_list.delete(0,tk.END))).pack(side=tk.LEFT)
        lf = ttk.Frame(f); lf.pack(fill=tk.BOTH, expand=False, pady=4)
        self.comp_list = tk.Listbox(lf, height=4, bg="#1e1e1e", fg="#d4d4d4")
        self.comp_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(lf, command=self.comp_list.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.comp_list.config(yscrollcommand=sb.set)
        # 选项行
        opt = ttk.Frame(f); opt.pack(fill=tk.X, pady=6)
        ttk.Label(opt, text="格式:").pack(side=tk.LEFT)
        self.fmt_var = tk.StringVar(value="zip")
        ttk.Combobox(opt, textvariable=self.fmt_var, values=[x["name"] for x in COMPRESS_FORMATS], state="readonly", width=8).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text="等级:").pack(side=tk.LEFT, padx=(8,0))
        self.level_var = tk.StringVar(value="1")
        ttk.Combobox(opt, textvariable=self.level_var, values=COMPRESS_LEVELS, state="readonly", width=5).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text="密码:").pack(side=tk.LEFT, padx=(8,0))
        self.pwd_var = tk.StringVar()
        ttk.Entry(opt, textvariable=self.pwd_var, show="*", width=12).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text="分卷(如10m,留空不分卷):").pack(side=tk.LEFT, padx=(8,0))
        self.vol_var = tk.StringVar()
        ttk.Entry(opt, textvariable=self.vol_var, width=8).pack(side=tk.LEFT, padx=4)
        # 输出
        ttk.Label(f, text="输出文件:").pack(anchor=tk.W, pady=(6,0))
        orow = ttk.Frame(f); orow.pack(fill=tk.X, pady=4)
        self.comp_out = tk.StringVar()
        ttk.Entry(orow, textvariable=self.comp_out).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(orow, text="浏览", command=self._pick_comp_out, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(f, text="▶ 开始压缩", command=self._on_compress).pack(pady=8, anchor=tk.W)
        self.comp_prog = ttk.Progressbar(f, mode="determinate"); self.comp_prog.pack(fill=tk.X)
        self.comp_log = tk.Text(f, height=6, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.comp_log.pack(fill=tk.BOTH, expand=True, pady=(6,0))

    def _add_files(self):
        paths = filedialog.askopenfilenames(title="选择文件")
        for p in paths:
            if p not in self.compress_files:
                self.compress_files.append(p); self.comp_list.insert(tk.END, p)
        self._update_comp_out()

    def _add_folder(self):
        p = filedialog.askdirectory(title="选择文件夹")
        if p and p not in self.compress_files:
            self.compress_files.append(p); self.comp_list.insert(tk.END, p)
            self._update_comp_out()

    def _update_comp_out(self):
        if self.compress_files and not self.comp_out.get():
            d = os.path.dirname(self.compress_files[0])
            fmt = [x for x in COMPRESS_FORMATS if x["name"]==self.fmt_var.get()][0]
            self.comp_out.set(os.path.join(d, "output"+fmt["ext"]))

    def _pick_comp_out(self):
        fmt = [x for x in COMPRESS_FORMATS if x["name"]==self.fmt_var.get()][0]
        p = filedialog.asksaveasfilename(defaultextension=fmt["ext"], filetypes=[(fmt["name"], "*"+fmt["ext"])])
        if p: self.comp_out.set(p)

    def _on_compress(self):
        if not self.compress_files: messagebox.showwarning("提示","请添加文件"); return
        if not self.comp_out.get(): messagebox.showwarning("提示","请选择输出路径"); return
        fmt = [x for x in COMPRESS_FORMATS if x["name"]==self.fmt_var.get()][0]
        vol = self.vol_var.get().strip() or None
        self.comp_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_compress, args=(fmt, vol), daemon=True).start()

    def _do_compress(self, fmt, vol):
        def log(m): self.root.after(0, lambda: self._log(self.comp_log, m))
        def prog(p): self.root.after(0, lambda: self.comp_prog.configure(value=p))
        prog(10)
        ok, msg = do_compress(self.compress_files, self.comp_out.get(), fmt,
                              int(self.level_var.get()), self.pwd_var.get() or None, vol, log)
        prog(100)
        self.root.after(0, lambda: messagebox.showinfo("完成" if ok else "失败", msg))

    # ---------- 解压页 ----------
    def _build_extract_tab(self, nb):
        f = ttk.Frame(nb, padding=12); nb.add(f, text="  解压  ")
        ttk.Label(f, text="压缩文件：").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.decomp_path = tk.StringVar()
        ttk.Entry(row, textvariable=self.decomp_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=self._pick_decomp_file, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(f, text="输出目录：").pack(anchor=tk.W, pady=(6,0))
        row2 = ttk.Frame(f); row2.pack(fill=tk.X, pady=6)
        self.decomp_out = tk.StringVar()
        ttk.Entry(row2, textvariable=self.decomp_out).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row2, text="浏览", command=self._pick_decomp_out, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(f, text="密码（加密压缩包）：").pack(anchor=tk.W, pady=(6,0))
        self.decomp_pwd = tk.StringVar()
        ttk.Entry(f, textvariable=self.decomp_pwd, show="*").pack(fill=tk.X, pady=4)
        ttk.Button(f, text="▶ 开始解压", command=self._on_decompress).pack(pady=8, anchor=tk.W)
        self.decomp_prog = ttk.Progressbar(f, mode="determinate"); self.decomp_prog.pack(fill=tk.X)
        self.decomp_log = tk.Text(f, height=8, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.decomp_log.pack(fill=tk.BOTH, expand=True, pady=(6,0))

    def _pick_decomp_file(self):
        p = filedialog.askopenfilename(filetypes=[("压缩文件","*.zip *.7z *.rar *.tar *.gz *.bz2 *.xz *.iso *.cab *.lzma *.zstd *.tgz"),("所有文件","*.*")])
        if p:
            self.decomp_path.set(p)
            self.decomp_out.set(os.path.dirname(p))

    def _pick_decomp_out(self):
        p = filedialog.askdirectory(title="选择输出目录")
        if p: self.decomp_out.set(p)

    def _on_decompress(self):
        if not self.decomp_path.get(): messagebox.showwarning("提示","请选择压缩文件"); return
        self.decomp_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_decompress, daemon=True).start()

    def _do_decompress(self):
        def log(m): self.root.after(0, lambda: self._log(self.decomp_log, m))
        def prog(p): self.root.after(0, lambda: self.decomp_prog.configure(value=p))
        prog(10)
        ok, msg = do_extract(self.decomp_path.get(), self.decomp_out.get() or os.path.dirname(self.decomp_path.get()),
                             self.decomp_pwd.get() or None, log)
        prog(100)
        self.root.after(0, lambda: messagebox.showinfo("完成" if ok else "失败", msg))

    # ---------- 预览页 ----------
    def _build_preview_tab(self, nb):
        f = ttk.Frame(nb, padding=12); nb.add(f, text="  预览  ")
        ttk.Label(f, text="选择压缩包预览内容（不解压）：").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.prev_path = tk.StringVar()
        ttk.Entry(row, textvariable=self.prev_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=self._pick_prev_file, width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(row, text="预览", command=self._on_preview, width=8).pack(side=tk.LEFT, padx=(6,0))
        # 表格
        cols = ("name", "size")
        self.prev_tree = ttk.Treeview(f, columns=cols, show="headings", height=12)
        self.prev_tree.heading("name", text="文件名")
        self.prev_tree.heading("size", text="大小")
        self.prev_tree.column("name", width=500)
        self.prev_tree.column("size", width=120, anchor=tk.E)
        self.prev_tree.pack(fill=tk.BOTH, expand=True, pady=6)
        self.prev_info = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.prev_info, foreground="gray").pack(anchor=tk.W)

    def _pick_prev_file(self):
        p = filedialog.askopenfilename(filetypes=[("压缩文件","*.zip *.7z *.rar *.tar *.gz *.bz2 *.xz *.iso *.cab"),("所有文件","*.*")])
        if p: self.prev_path.set(p)

    def _on_preview(self):
        if not self.prev_path.get(): messagebox.showwarning("提示","请选择压缩包"); return
        self.prev_tree.delete(*self.prev_tree.get_children())
        files, err = do_preview(self.prev_path.get())
        if err:
            messagebox.showerror("错误", err); return
        total = 0
        for f in files:
            self.prev_tree.insert("", tk.END, values=(f["name"], f"{f['size']:,}"))
            total += f["size"]
        self.prev_info.set(f"共 {len(files)} 个文件，总大小 {total:,} 字节")

    # ---------- 批量页 ----------
    def _build_batch_tab(self, nb):
        f = ttk.Frame(nb, padding=12); nb.add(f, text="  批量  ")
        ttk.Label(f, text="选择文件夹，批量压缩或解压里面的所有文件：").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.batch_dir = tk.StringVar()
        ttk.Entry(row, textvariable=self.batch_dir).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=lambda: self.batch_dir.set(filedialog.askdirectory() or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        opt = ttk.Frame(f); opt.pack(fill=tk.X, pady=6)
        ttk.Label(opt, text="压缩格式:").pack(side=tk.LEFT)
        self.batch_fmt = tk.StringVar(value="zip")
        ttk.Combobox(opt, textvariable=self.batch_fmt, values=[x["name"] for x in COMPRESS_FORMATS], state="readonly", width=8).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt, text="等级:").pack(side=tk.LEFT, padx=(8,0))
        self.batch_level = tk.StringVar(value="1")
        ttk.Combobox(opt, textvariable=self.batch_level, values=COMPRESS_LEVELS, state="readonly", width=5).pack(side=tk.LEFT, padx=4)
        btns = ttk.Frame(f); btns.pack(pady=8)
        ttk.Button(btns, text="▶ 批量压缩", command=lambda: self._batch_run("compress")).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="▶ 批量解压", command=lambda: self._batch_run("extract")).pack(side=tk.LEFT, padx=4)
        self.batch_log = tk.Text(f, height=12, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.batch_log.pack(fill=tk.BOTH, expand=True, pady=6)

    def _batch_run(self, mode):
        if not self.batch_dir.get(): messagebox.showwarning("提示","请选择文件夹"); return
        self.batch_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_batch, args=(mode,), daemon=True).start()

    def _do_batch(self, mode):
        def log(m): self.root.after(0, lambda: self._log(self.batch_log, m))
        if mode == "compress":
            fmt = [x for x in COMPRESS_FORMATS if x["name"]==self.batch_fmt.get()][0]
            ok, msg = do_batch_compress(self.batch_dir.get(), fmt, int(self.batch_level.get()), log)
        else:
            ok, msg = do_batch_extract(self.batch_dir.get(), log)
        self.root.after(0, lambda: messagebox.showinfo("完成", msg))

    # ---------- 密码恢复页 ----------
    def _build_crack_tab(self, nb):
        f = ttk.Frame(nb, padding=12); nb.add(f, text="  密码恢复  ")
        ttk.Label(f, text="⚠️ 仅限恢复自己忘记的密码，禁止用于非法用途！", foreground="red").pack(anchor=tk.W)
        ttk.Label(f, text="加密压缩包：").pack(anchor=tk.W, pady=(8,0))
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=4)
        self.crack_arc = tk.StringVar()
        ttk.Entry(row, textvariable=self.crack_arc).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=lambda: self.crack_arc.set(filedialog.askopenfilename(filetypes=[("压缩文件","*.zip *.7z *.rar")]) or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(f, text="密码字典文件（每行一个密码）：").pack(anchor=tk.W, pady=(6,0))
        row2 = ttk.Frame(f); row2.pack(fill=tk.X, pady=4)
        self.crack_dict = tk.StringVar()
        ttk.Entry(row2, textvariable=self.crack_dict).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row2, text="浏览", command=lambda: self.crack_dict.set(filedialog.askopenfilename(filetypes=[("文本文件","*.txt")]) or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(f, text="▶ 开始字典破解", command=self._on_crack).pack(pady=10, anchor=tk.W)
        self.crack_log = tk.Text(f, height=10, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.crack_log.pack(fill=tk.BOTH, expand=True, pady=6)

    def _on_crack(self):
        if not self.crack_arc.get() or not self.crack_dict.get():
            messagebox.showwarning("提示","请选择压缩包和字典文件"); return
        self.crack_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_crack, daemon=True).start()

    def _do_crack(self):
        def log(m): self.root.after(0, lambda: self._log(self.crack_log, m))
        ok, msg = do_password_crack(self.crack_arc.get(), self.crack_dict.get(), log)
        self.root.after(0, lambda: messagebox.showinfo("结果", msg))

    # ---------- 对比测试页 ----------
    def _build_compare_tab(self, nb):
        f = ttk.Frame(nb, padding=12); nb.add(f, text="  压缩率对比  ")
        ttk.Label(f, text="选择一个测试文件，对比不同格式/等级的压缩率和速度：").pack(anchor=tk.W)
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.cmp_file = tk.StringVar()
        ttk.Entry(row, textvariable=self.cmp_file).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=lambda: self.cmp_file.set(filedialog.askopenfilename() or ""), width=8).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(f, text="▶ 开始对比测试", command=self._on_compare).pack(pady=8, anchor=tk.W)
        cols = ("format", "level", "size", "ratio", "time")
        self.cmp_tree = ttk.Treeview(f, columns=cols, show="headings", height=10)
        for c, t, w in [("format","格式",80),("level","等级",60),("size","压缩后大小",140),("ratio","压缩率",100),("time","耗时",100)]:
            self.cmp_tree.heading(c, text=t); self.cmp_tree.column(c, width=w, anchor=tk.CENTER)
        self.cmp_tree.pack(fill=tk.BOTH, expand=True, pady=6)
        self.cmp_log = tk.Text(f, height=4, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas",9))
        self.cmp_log.pack(fill=tk.X, pady=(6,0))

    def _on_compare(self):
        if not self.cmp_file.get(): messagebox.showwarning("提示","请选择测试文件"); return
        self.cmp_tree.delete(*self.cmp_tree.get_children())
        self.cmp_log.delete("1.0", tk.END)
        threading.Thread(target=self._do_compare, daemon=True).start()

    def _do_compare(self):
        def log(m): self.root.after(0, lambda: self._log(self.cmp_log, m))
        results, err = do_compare(self.cmp_file.get(), log)
        if err:
            self.root.after(0, lambda: messagebox.showerror("错误", err)); return
        for r in results:
            self.root.after(0, lambda r=r: self.cmp_tree.insert("", tk.END,
                values=(r["format"], r["level"], f"{r['size']:,}B", f"{r['ratio']:.1f}%", f"{r['time']:.2f}s")))
        self.root.after(0, lambda: messagebox.showinfo("完成", "对比测试完成！"))

def main():
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = ZipToolApp(root)
    # 命令行参数支持（右键菜单）
    if len(sys.argv) >= 3:
        if sys.argv[1] == "--compress":
            app.compress_files = [sys.argv[2]]
            app.comp_list.insert(tk.END, sys.argv[2])
            app._update_comp_out()
        elif sys.argv[1] == "--extract":
            app.decomp_path.set(sys.argv[2])
            app.decomp_out.set(os.path.dirname(sys.argv[2]))
    root.mainloop()

if __name__ == "__main__":
    main()
