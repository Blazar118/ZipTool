# 压缩解压工具 (ZipTool)

一个基于 Python + tkinter 的本地图形化压缩解压一体工具，调用 7-Zip 命令行实现全格式支持。

> 🤖 **关于本项目**：本项目由 AI 辅助开发完成。作者为编程初学者，通过与 AI 对话完成全部代码编写、调试和打包，希望这个项目能帮助到同样在学习编程的朋友。

## 功能特性

### 解压模块
- 支持格式：ZIP、RAR、7Z、TAR、GZ、BZ2、XZ、ISO、CAB、LZMA、ZSTD
- 选择源压缩文件、选择输出目录
- 解压完成弹窗提示，实时日志输出
- 支持加密压缩包（自动提示输入密码）

### 压缩模块
- 支持多文件/文件夹打包压缩
- 输出格式：ZIP、7Z、TAR.GZ
- 可设置压缩等级（1-9）
- 支持密码加密（ZIP / 7Z）
- 实时日志输出

### 额外功能
- 右键菜单集成：右键文件夹可直接压缩，右键压缩包可直接解压
- Inno Setup 安装包，一键安装
- 中文路径完整支持
- 异常处理：文件损坏、密码错误、权限不足等友好提示

## 系统要求

- Windows 7/8/10/11
- 已安装 7-Zip 或 NanaZip（`7z` 命令需在 PATH 中）
- Python 3.8+（仅从源码运行时需要）

## 快速开始

### 方式一：直接运行 EXE
下载安装包，双击安装即可使用。

### 方式二：从源码运行
```bash
pip install -r requirements.txt
python main.py
```

## 注册右键菜单

以管理员身份运行：
```bash
install_menu.bat
```

卸载右键菜单：
```bash
uninstall_menu.bat
```

## 构建安装包

1. 安装 PyInstaller：`pip install pyinstaller`
2. 打包：`pyinstaller -F -w --name "压缩解压工具" main.py`
3. 用 Inno Setup 6 编译 `installer.iss` 生成安装包

## 格式兼容说明

| 格式 | 解压 | 压缩 | 说明 |
|------|------|------|------|
| ZIP | ✅ | ✅ | 支持密码加密 |
| 7Z | ✅ | ✅ | 支持密码加密 |
| RAR | ✅ | ❌ | RAR 格式闭源，无法生成 |
| TAR | ✅ | ✅ | |
| GZ | ✅ | ✅ | |
| BZ2 | ✅ | ❌ | |
| XZ | ✅ | ❌ | |
| ISO | ✅ | ❌ | |
| CAB | ✅ | ❌ | |
| LZMA | ✅ | ❌ | |
| ZSTD | ✅ | ❌ | |

## 依赖

- Python 标准库（tkinter、os、sys、subprocess、threading）
- 7-Zip / NanaZip（外部命令行工具）

## License

MIT License
