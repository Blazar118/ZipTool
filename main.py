import os
import sys
import traceback
import subprocess
import threading
import argparse
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# -------------------------- 便携7z兼容：优先读取当前目录7z/NanaZip --------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = script_dir + os.pathsep + os.environ.get("PATH", "")

# -------------------------- 配置常量 --------------------------
COMPRESS_FORMATS = [
    {"name": "7z", "ext": ".7z", "cmd_type": "7z"},
    {"name": "zip", "ext": ".zip", "cmd_type": "zip"},
    {"name": "tar.gz", "ext": ".tar.gz", "cmd_type": "tar.gz"},
]
COMPRESS_LEVELS = [str(i) for i in range(10)]


def run_cmd(cmd, timeout=300):
    result = subprocess.run(cmd, capture_output=True, timeout=timeout)
    stdout = stderr = ""
    if result.stdout:
        try:
            stdout = result.stdout.decode("gbk", errors="replace")
        except Exception:
            stdout = result.stdout.decode("utf-8", errors="replace")
    if result.stderr:
        try:
            stderr = result.stderr.decode("gbk", errors="replace")
        except Exception:
            stderr = result.stderr.decode("utf-8", errors="replace")
    return result.returncode, stdout, stderr


def find_7z():
    for name in ["7z.exe", "7z", "NanaZipC.exe", "NanaZipC"]:
        try:
            code, out, err = run_cmd([name, "--version"], timeout=5)
            if code == 0 or "7-Zip" in out or "NanaZip" in out:
                return name
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


SEVEN_ZIP = find_7z()


def do_extract_work(archive_path, out_dir, password, log_callback=None):
    """执行解压，返回(success, message)"""
    try:
        archive = Path(archive_path)
        out = Path(out_dir)
        if not archive.exists():
            return False, "压缩包不存在"
        os.makedirs(out, exist_ok=True)
        if log_callback:
            log_callback(f"开始解压 {archive.name} -> {out}")
        seven_zip = SEVEN_ZIP or "7z"
        cmd = [seven_zip, "x", "-mmt=on", "-bb1", "-y", f"-o{out}", str(archive)]
        if password:
            cmd.insert(2, f"-p{password}")
        else:
            cmd.insert(2, "-p-")
        code, out_text, err_text = run_cmd(cmd, timeout=300)
        output = out_text + "\n" + err_text
        if log_callback:
            for line in output.splitlines():
                if line.strip():
                    log_callback(line.strip())
        if code == 0:
            return True, "解压完成！"
        output_lower = output.lower()
        if "wrong password" in output_lower or "data error in encrypted" in output_lower:
            if password:
                return False, "密码错误，请重新输入！"
            else:
                return False, "该压缩包已加密，请输入密码！"
        return False, f"解压失败，返回码 {code}"
    except PermissionError:
        return False, "权限不足，无法写入输出目录"
    except Exception as e:
        return False, f"异常：{str(e)}"


def do_compress_work(file_list, output_file, fmt_info, level, password, log_callback=None):
    """执行压缩，返回(success, message)"""
    try:
        files = [Path(p) for p in file_list if Path(p).exists()]
        if len(files) == 0:
            return False, "没有有效待压缩文件"
        out_path = Path(output_file)
        cmd_type = fmt_info["cmd_type"]
        if log_callback:
            log_callback(f"开始压缩，格式:{fmt_info['name']},等级:{level}")
        seven_zip = SEVEN_ZIP or "7z"
        if cmd_type == "tar.gz":
            tar_path = str(out_path).replace(".tar.gz", ".tar")
            cmd1 = [seven_zip, "a", "-ttar", "-y", tar_path] + [str(f) for f in files]
            code1, out1, err1 = run_cmd(cmd1, timeout=300)
            if log_callback:
                for line in (out1 + err1).splitlines():
                    if line.strip():
                        log_callback(line.strip())
            if code1 != 0:
                return False, "tar打包失败"
            cmd2 = [seven_zip, "a", "-tgzip", f"-mx{level}", "-mmt=on", "-bb1", "-y", str(out_path), tar_path]
            code2, out2, err2 = run_cmd(cmd2, timeout=300)
            if log_callback:
                for line in (out2 + err2).splitlines():
                    if line.strip():
                        log_callback(line.strip())
            try:
                os.remove(tar_path)
            except OSError:
                pass
            if code2 != 0:
                return False, "gzip压缩失败"
        else:
            archive_type = "7z" if cmd_type == "7z" else "zip"
            cmd = [seven_zip, "a", f"-t{archive_type}", f"-mx{level}", "-mmt=on", "-bb1", "-y"]
            if password:
                cmd.append(f"-p{password}")
                if archive_type == "zip":
                    cmd.append("-mem=AES256")
            cmd.append(str(out_path))
            cmd += [str(f) for f in files]
            code, out_text, err_text = run_cmd(cmd, timeout=300)
            if log_callback:
                for line in (out_text + err_text).splitlines():
                    if line.strip():
                        log_callback(line.strip())
            if code != 0:
                return False, f"压缩失败，返回码 {code}"
        return True, f"压缩完成！\n输出文件：{out_path}"
    except PermissionError:
        return False, "权限不足，无法写入输出文件"
    except Exception as e:
        return False, f"异常：{str(e)}"


# ===================== 快速操作窗口（右键调用） =====================
class QuickExtractDialog:
    def __init__(self, parent, archive_path):
        self.archive_path = archive_path
        self.result = None
        self.win = tk.Toplevel(parent)
        self.win.title("解压 - " + os.path.basename(archive_path))
        self.win.geometry("480x280")
        self.win.resizable(False, False)
        self.win.grab_set()
        self._build()

    def _build(self):
        frame = ttk.Frame(self.win, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=f"压缩包：{os.path.basename(self.archive_path)}", wraplength=440).pack(anchor=tk.W, pady=(0,8))
        ttk.Label(frame, text="输出目录：").pack(anchor=tk.W)
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=4)
        default_out = os.path.splitext(self.archive_path)[0]
        self.outdir_var = tk.StringVar(value=default_out)
        ttk.Entry(row, textvariable=self.outdir_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览...", command=self._browse).pack(side=tk.LEFT, padx=(4,0))
        ttk.Label(frame, text="密码（加密包必填）：").pack(anchor=tk.W, pady=(8,0))
        self.pwd_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.pwd_var, show="*").pack(fill=tk.X, pady=4)
        btn_row = ttk.Frame(frame)
        btn_row.pack(pady=12)
        ttk.Button(btn_row, text="开始解压", command=self._ok, width=14).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="取消", command=self._cancel, width=14).pack(side=tk.LEFT, padx=4)

    def _browse(self):
        d = filedialog.askdirectory(title="选择输出目录", initialdir=os.path.dirname(self.archive_path))
        if d:
            self.outdir_var.set(d)

    def _ok(self):
        self.result = {"outdir": self.outdir_var.get(), "password": self.pwd_var.get().strip()}
        self.win.destroy()

    def _cancel(self):
        self.win.destroy()


class QuickCompressDialog:
    def __init__(self, parent, source_path):
        self.source_path = source_path
        self.result = None
        self.win = tk.Toplevel(parent)
        self.win.title("压缩 - " + os.path.basename(source_path))
        self.win.geometry("480x340")
        self.win.resizable(False, False)
        self.win.grab_set()
        self._build()

    def _build(self):
        frame = ttk.Frame(self.win, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=f"源：{os.path.basename(self.source_path)}", wraplength=440).pack(anchor=tk.W, pady=(0,8))
        ttk.Label(frame, text="输出目录：").pack(anchor=tk.W)
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=4)
        default_out = os.path.dirname(self.source_path) if os.path.dirname(self.source_path) else os.getcwd()
        self.outdir_var = tk.StringVar(value=default_out)
        ttk.Entry(row, textvariable=self.outdir_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览...", command=self._browse).pack(side=tk.LEFT, padx=(4,0))
        opt_row = ttk.Frame(frame)
        opt_row.pack(fill=tk.X, pady=8)
        ttk.Label(opt_row, text="格式：").pack(side=tk.LEFT)
        self.fmt_var = tk.StringVar(value="7z")
        ttk.Combobox(opt_row, textvariable=self.fmt_var, values=[f["name"] for f in COMPRESS_FORMATS], state="readonly", width=8).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt_row, text="等级：").pack(side=tk.LEFT, padx=(12,0))
        self.level_var = tk.StringVar(value="3")
        ttk.Combobox(opt_row, textvariable=self.level_var, values=COMPRESS_LEVELS, state="readonly", width=6).pack(side=tk.LEFT, padx=4)
        ttk.Label(frame, text="密码（仅7z/zip，留空不加密）：").pack(anchor=tk.W)
        self.pwd_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.pwd_var, show="*").pack(fill=tk.X, pady=4)
        btn_row = ttk.Frame(frame)
        btn_row.pack(pady=12)
        ttk.Button(btn_row, text="开始压缩", command=self._ok, width=14).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="取消", command=self._cancel, width=14).pack(side=tk.LEFT, padx=4)

    def _browse(self):
        d = filedialog.askdirectory(title="选择输出目录", initialdir=self.outdir_var.get())
        if d:
            self.outdir_var.set(d)

    def _ok(self):
        self.result = {
            "outdir": self.outdir_var.get(),
            "format": self.fmt_var.get(),
            "level": int(self.level_var.get()),
            "password": self.pwd_var.get().strip()
        }
        self.win.destroy()

    def _cancel(self):
        self.win.destroy()


class ProgressWindow:
    def __init__(self, parent, title):
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.geometry("560x360")
        self.win.grab_set()
        self.log = tk.Text(self.win, wrap=tk.WORD, bg="#1e1e1e", fg="#d4d4d4")
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def log_msg(self, msg):
        def append():
            self.log.insert(tk.END, msg + "\n")
            self.log.see(tk.END)
        self.win.after(0, append)

    def close(self):
        self.win.destroy()


# ===================== 主程序界面 =====================
class CompressToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("本地压缩解压工具")
        self.root.geometry("820x660")
        self.root.minsize(700, 500)
        self.selected_compress_files = []
        self._build_ui()
        if not SEVEN_ZIP:
            self.root.after(500, lambda: messagebox.showwarning("警告", "未检测到7-Zip/NanaZip，部分格式可能无法解压。"))

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ef = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(ef, text="解压")
        self._build_extract_tab(ef)
        cf = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(cf, text="压缩")
        self._build_compress_tab(cf)

    def _build_extract_tab(self, parent):
        r1 = ttk.Frame(parent); r1.pack(fill=tk.X, pady=4)
        ttk.Button(r1, text="选择压缩包", command=self._pick_archive).pack(side=tk.LEFT)
        self.archive_var = tk.StringVar(value="未选择压缩包")
        ttk.Label(r1, textvariable=self.archive_var, foreground="gray").pack(side=tk.LEFT, padx=8)
        r2 = ttk.Frame(parent); r2.pack(fill=tk.X, pady=4)
        ttk.Button(r2, text="选择输出文件夹", command=self._pick_outdir).pack(side=tk.LEFT)
        self.outdir_var = tk.StringVar(value="未选择输出目录")
        ttk.Label(r2, textvariable=self.outdir_var, foreground="gray").pack(side=tk.LEFT, padx=8)
        r3 = ttk.Frame(parent); r3.pack(fill=tk.X, pady=4)
        ttk.Label(r3, text="解压密码（加密包必填）：").pack(side=tk.LEFT)
        self.extract_pwd_var = tk.StringVar()
        ttk.Entry(r3, textvariable=self.extract_pwd_var, show="*", width=30).pack(side=tk.LEFT, padx=8)
        ttk.Button(parent, text="▶ 开始解压", command=self._on_extract).pack(pady=8, anchor=tk.W)
        ttk.Separator(parent).pack(fill=tk.X, pady=6)
        ttk.Label(parent, text="运行日志：").pack(anchor=tk.W)
        lf = ttk.Frame(parent); lf.pack(fill=tk.BOTH, expand=True, pady=4)
        self.extract_log = tk.Text(lf, wrap=tk.WORD, height=15, bg="#1e1e1e", fg="#d4d4d4")
        self.extract_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(lf, command=self.extract_log.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.extract_log.config(yscrollcommand=sb.set)

    def _pick_archive(self):
        p = filedialog.askopenfilename(filetypes=[("压缩文件","*.zip *.7z *.rar *.tar *.gz *.bz2 *.xz *.iso *.cab *.lzma *.zstd *.tgz"),("所有文件","*.*")])
        if p: self.archive_var.set(p)

    def _pick_outdir(self):
        p = filedialog.askdirectory(title="选择输出文件夹")
        if p: self.outdir_var.set(p)

    def _on_extract(self):
        arch = self.archive_var.get()
        outd = self.outdir_var.get()
        if arch == "未选择压缩包" or not arch:
            messagebox.showwarning("提示","请选择压缩包！"); return
        if outd == "未选择输出目录" or not outd:
            messagebox.showwarning("提示","请选择输出目录！"); return
        self.extract_log.delete("1.0", tk.END)
        pwd = self.extract_pwd_var.get().strip()
        def worker():
            ok, msg = do_extract_work(arch, outd, pwd, lambda m: self._log(self.extract_log, m))
            self.root.after(0, lambda: messagebox.showinfo("完成" if ok else "错误", msg))
        threading.Thread(target=worker, daemon=True).start()

    def _build_compress_tab(self, parent):
        br = ttk.Frame(parent); br.pack(fill=tk.X, pady=4)
        ttk.Button(br, text="添加文件", command=self._add_files).pack(side=tk.LEFT)
        ttk.Button(br, text="添加文件夹", command=self._add_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(br, text="清空", command=self._clear_files).pack(side=tk.LEFT, padx=4)
        ttk.Label(parent, text="待压缩列表：").pack(anchor=tk.W)
        lf = ttk.Frame(parent); lf.pack(fill=tk.BOTH, expand=False, pady=4)
        self.listbox = tk.Listbox(lf, height=5, bg="#1e1e1e", fg="#d4d4d4")
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lsb = ttk.Scrollbar(lf, command=self.listbox.yview); lsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=lsb.set)
        orow = ttk.Frame(parent); orow.pack(fill=tk.X, pady=4)
        ttk.Button(orow, text="选择输出目录", command=self._pick_compress_out).pack(side=tk.LEFT)
        self.compress_out_var = tk.StringVar(value="未选择输出位置")
        ttk.Label(orow, textvariable=self.compress_out_var, foreground="gray").pack(side=tk.LEFT, padx=8)
        orow2 = ttk.Frame(parent); orow2.pack(fill=tk.X, pady=4)
        ttk.Label(orow2, text="格式：").pack(side=tk.LEFT)
        self.fmt_var = tk.StringVar(value="7z")
        ttk.Combobox(orow2, textvariable=self.fmt_var, values=[f["name"] for f in COMPRESS_FORMATS], state="readonly", width=8).pack(side=tk.LEFT, padx=4)
        ttk.Label(orow2, text="等级：").pack(side=tk.LEFT, padx=(12,0))
        self.level_var = tk.StringVar(value="6")
        ttk.Combobox(orow2, textvariable=self.level_var, values=COMPRESS_LEVELS, state="readonly", width=6).pack(side=tk.LEFT, padx=4)
        prow = ttk.Frame(parent); prow.pack(fill=tk.X, pady=4)
        ttk.Label(prow, text="密码（仅7z/zip）：").pack(side=tk.LEFT)
        self.compress_pwd_var = tk.StringVar()
        ttk.Entry(prow, textvariable=self.compress_pwd_var, show="*", width=30).pack(side=tk.LEFT, padx=8)
        ttk.Button(parent, text="▶ 开始压缩", command=self._on_compress).pack(pady=8, anchor=tk.W)
        ttk.Separator(parent).pack(fill=tk.X, pady=6)
        ttk.Label(parent, text="运行日志：").pack(anchor=tk.W)
        clf = ttk.Frame(parent); clf.pack(fill=tk.BOTH, expand=True, pady=4)
        self.compress_log = tk.Text(clf, wrap=tk.WORD, height=10, bg="#1e1e1e", fg="#d4d4d4")
        self.compress_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        csb = ttk.Scrollbar(clf, command=self.compress_log.yview); csb.pack(side=tk.RIGHT, fill=tk.Y)
        self.compress_log.config(yscrollcommand=csb.set)

    def _add_files(self):
        for p in filedialog.askopenfilenames(title="选择待压缩文件"):
            if p not in self.selected_compress_files:
                self.selected_compress_files.append(p)
        self._refresh_list()

    def _add_folder(self):
        p = filedialog.askdirectory(title="选择待压缩文件夹")
        if p and p not in self.selected_compress_files:
            self.selected_compress_files.append(p)
            self._refresh_list()

    def _clear_files(self):
        self.selected_compress_files.clear()
        self._refresh_list()

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for p in self.selected_compress_files:
            self.listbox.insert(tk.END, p)

    def _pick_compress_out(self):
        p = filedialog.askdirectory(title="选择输出目录")
        if p: self.compress_out_var.set(p)

    def _on_compress(self):
        out_base = self.compress_out_var.get()
        if out_base == "未选择输出位置" or not out_base:
            messagebox.showwarning("提示","请选择输出目录！"); return
        if not self.selected_compress_files:
            messagebox.showwarning("提示","请添加待压缩文件！"); return
        fmt = [f for f in COMPRESS_FORMATS if f["name"] == self.fmt_var.get()][0]
        output = os.path.join(out_base, f"output{fmt['ext']}")
        level = int(self.level_var.get())
        pwd = self.compress_pwd_var.get().strip()
        self.compress_log.delete("1.0", tk.END)
        def worker():
            ok, msg = do_compress_work(self.selected_compress_files, output, fmt, level, pwd, lambda m: self._log(self.compress_log, m))
            self.root.after(0, lambda: messagebox.showinfo("完成" if ok else "错误", msg))
        threading.Thread(target=worker, daemon=True).start()

    def _log(self, widget, msg):
        def append():
            widget.insert(tk.END, msg + "\n")
            widget.see(tk.END)
        self.root.after(0, append)


def run_quick_extract(root, archive_path):
    dlg = QuickExtractDialog(root, archive_path)
    root.wait_window(dlg.win)
    if not dlg.result:
        return
    pw = ProgressWindow(root, "解压中...")
    def worker():
        ok, msg = do_extract_work(archive_path, dlg.result["outdir"], dlg.result["password"], pw.log_msg)
        root.after(0, lambda: (pw.close(), messagebox.showinfo("完成" if ok else "错误", msg)))
    threading.Thread(target=worker, daemon=True).start()


def run_quick_compress(root, source_path):
    dlg = QuickCompressDialog(root, source_path)
    root.wait_window(dlg.win)
    if not dlg.result:
        return
    fmt = [f for f in COMPRESS_FORMATS if f["name"] == dlg.result["format"]][0]
    base_name = os.path.splitext(os.path.basename(source_path))[0]
    output = os.path.join(dlg.result["outdir"], f"{base_name}{fmt['ext']}")
    pw = ProgressWindow(root, "压缩中...")
    def worker():
        ok, msg = do_compress_work([source_path], output, fmt, dlg.result["level"], dlg.result["password"], pw.log_msg)
        root.after(0, lambda: (pw.close(), messagebox.showinfo("完成" if ok else "错误", msg)))
    threading.Thread(target=worker, daemon=True).start()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extract", metavar="PATH")
    parser.add_argument("--compress", metavar="PATH")
    args = parser.parse_args()

    root = tk.Tk()
    root.withdraw()  # 先隐藏主窗口

    if args.extract and os.path.exists(args.extract):
        run_quick_extract(root, args.extract)
        root.mainloop()
        return
    if args.compress and os.path.exists(args.compress):
        run_quick_compress(root, args.compress)
        root.mainloop()
        return

    # 正常模式：显示主窗口
    root.deiconify()
    app = CompressToolApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
