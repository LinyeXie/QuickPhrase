# QuickPhrase

<p align="center">
  <strong>A lightweight, Fluent-style quick phrase manager for Windows.</strong><br>
  快速召唤、自动粘贴、隐藏内容保护、系统托盘与 Windows 原生体验。
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-v1.8.3-6C63FF">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows-0078D4">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB">
  <img alt="GUI" src="https://img.shields.io/badge/GUI-PySide6-41CD52">
  <img alt="Status" src="https://img.shields.io/badge/status-Stable-success">
</p>

---

## 简介

**QuickPhrase** 是一款面向 Windows 的轻量级常用语管理工具。

它可以通过全局快捷键快速召唤常用语窗口，将常用文本一键复制或自动粘贴到当前输入光标位置，同时提供隐藏常用语、Windows PIN / Hello 验证、软件密码保护、拖动排序、系统托盘、开机自启动以及完整的安装/更新/降级检测机制。

QuickPhrase 的设计目标是：

- **快**：尽可能减少重复输入与窗口切换；
- **轻**：单文件 Python 主程序，依赖精简；
- **稳**：针对 Windows 焦点、托盘、DPI、多显示器与窗口层级进行适配；
- **安全**：隐藏内容使用 Windows DPAPI 加密，并支持 Windows PIN / Hello 或软件密码验证；
- **原生**：界面遵循 Windows 11 Fluent 风格，并读取 Windows Accent Color。

---

## 核心功能

| 功能 | 说明 |
| --- | --- |
| 全局快捷键 | 默认 `Ctrl + Alt + Space`，可在偏好设置中修改 |
| 快捷常用语窗口 | 快速召唤、置顶显示、支持拖动与位置记忆 |
| 单击 / 双击触发 | 可选择单击或双击使用常用语，默认单击 |
| 自动粘贴 | 自动返回原输入窗口，并粘贴到当前光标位置 |
| 仅复制 | 可选择只复制到剪贴板，不自动粘贴 |
| 隐藏常用语 | 列表只显示名称与 `••••••` |
| Windows PIN / Hello | 支持 Windows Security 原生身份验证 |
| 软件密码 | 无 PIN / Hello 时可使用本地软件密码 |
| 软件密码管理 | 支持设置、修改、删除；修改/删除均需原密码 |
| DPAPI 加密 | 隐藏常用语正文使用 Windows DPAPI 保护 |
| 拖动排序 | 主界面进入编辑模式后可拖动调整常用语顺序 |
| 搜索 | 支持快速检索常用语，隐藏正文不参与搜索 |
| 系统托盘 | 后台驻留、快速召唤、退出程序 |
| 托盘双击动作 | 可配置打开主界面 / 常用语窗口 / 偏好设置 |
| 开机自启动 | 登录 Windows 后启动到托盘，不弹出主界面 |
| 主题 | 跟随系统 / 浅色 / 深色 |
| Windows 强调色 | 按钮、选中状态等读取 Windows Accent Color |
| 多显示器 / DPI | 支持不同分辨率和 Windows 缩放比例 |
| 安装器 | 支持首次安装、更新、重装、降级检测 |

---

## 界面设计

QuickPhrase 使用 PySide6 构建，整体遵循 Windows 11 Fluent 风格：

- 原生 Windows 标题栏；
- Windows Accent Color；
- Light / Dark / System 三种主题；
- 紧凑、低视觉噪声布局；
- Fluent Toggle；
- Segmented Control；
- 圆角卡片与轻量列表；
- 自适应 DPI 与多显示器工作区。

主窗口用于管理常用语，快捷窗口用于快速调用。

### 主窗口

主要功能包括：

- 添加常用语；
- 编辑常用语；
- 删除常用语；
- 拖动调整顺序；
- 搜索；
- 打开偏好设置。

排序编辑模式下，点击顶部铅笔按钮后：

1. 常用语左侧显示拖动把手；
2. 按住常用语即可上下拖动；
3. 顺序自动写入 `phrases.json`；
4. 点击主题色 `✓` 退出排序模式。

### 快捷常用语窗口

快捷窗口默认：

- 首次显示在当前屏幕中心；
- 用户拖动后记忆位置；
- 屏幕分辨率或显示器变化后自动限制到可见区域；
- 不默认选中第一条常用语；
- 显示格式为：

```text
粗体名称：常用语内容
```

隐藏常用语显示：

```text
粗体名称：••••••
```

---

## 隐藏常用语与安全机制

QuickPhrase 对普通常用语和隐藏常用语采用不同处理方式。

### DPAPI 加密

隐藏常用语正文不会以明文形式直接写入 `phrases.json`。

正文通过 Windows DPAPI 保护，并保存为加密数据。

这意味着隐藏内容依赖当前 Windows 用户的安全上下文进行解密。

> QuickPhrase 不是跨平台、跨设备密码管理器。隐藏常用语功能主要用于降低本机明文暴露风险。

### 验证方式

在：

```text
偏好设置 → 软件设置 → 隐藏内容验证方式
```

可以选择：

- `Windows PIN`
- `软件密码`

默认优先使用 **Windows PIN / Hello**。

QuickPhrase 会检查 Windows `UserConsentVerifier` 的可用状态。

当 Windows PIN / Hello 不可用时：

- Windows PIN 选项自动灰色；
- 只能选择软件密码；
- 第一次创建隐藏常用语时会提示设置软件密码。

以下操作都会触发身份验证：

- 复制隐藏常用语；
- 自动粘贴隐藏常用语；
- 编辑隐藏常用语；
- 删除隐藏常用语。

---

## 软件密码

软件密码用于在 Windows PIN / Hello 不可用或用户主动选择软件密码时保护隐藏常用语操作。

### 存储方式

QuickPhrase **不会保存软件密码明文**。

保存内容包括：

- 随机盐；
- PBKDF2-HMAC-SHA256 派生摘要；
- 迭代次数。

当前默认：

```text
PBKDF2-HMAC-SHA256
Iterations: 350,000
Salt: 16 bytes
Derived key: 32 bytes
```

验证时使用 `hmac.compare_digest` 进行恒定时间比较。

### 修改软件密码

软件密码可以修改，但必须提供：

1. 当前原密码；
2. 新密码；
3. 再次输入新密码。

验证原密码成功后，会重新生成随机盐和密码摘要。

### 删除软件密码

软件密码可以删除，但同样必须先验证当前原密码。

删除后：

- 如果 Windows PIN / Hello 可用，则自动切换到 Windows PIN；
- 如果 PIN / Hello 不可用，则下一次需要隐藏内容保护时重新要求设置软件密码。

### 忘记软件密码

QuickPhrase **不提供绕过原密码的密码找回或重置机制**。

如果忘记原软件密码，只能卸载 QuickPhrase 后重新安装。

> 真正卸载 QuickPhrase 会永久删除全部 QuickPhrase 用户数据。

---

## 安装

### 方法一：使用安装包

推荐普通用户直接使用 Inno Setup 生成的安装程序。

安装器支持：

- 首次安装；
- 新版本更新；
- 相同版本重新安装；
- 旧版本降级；
- 创建桌面快捷方式；
- 开机自启动。

首次安装时：

```text
☑ 创建桌面快捷方式
☑ 开机自启动
```

默认全部勾选。

---

## 从源码运行

### 环境要求

- Windows 10 / Windows 11
- Python 3.10+
- PySide6 6.7+
- keyboard 0.13.5+

> 当前 Windows PIN / Hello 桌面验证实现要求 Windows 11 Build 22000+。  
> 不满足条件时仍可使用软件密码保护隐藏常用语。

### 克隆项目

```bash
git clone <YOUR_REPOSITORY_URL>
cd QuickPhrase
```

### 创建虚拟环境

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
```

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动

```bash
python quickphrase.py
```

---

## 默认设置

| 设置 | 默认值 |
| --- | --- |
| 全局召唤快捷键 | `Ctrl + Alt + Space` |
| 常用语触发方式 | 单击 |
| 使用常用语 | 自动粘贴 |
| 粘贴后清除剪贴板 | 关闭 |
| 应用主题 | 跟随 Windows |
| 隐藏内容验证方式 | Windows PIN |
| 托盘双击动作 | 打开主界面 |
| 主窗口关闭行为 | 每次询问 |
| 开机自启动 | 取决于安装选项 |

---

## 数据存储

### 常用语数据

```text
%APPDATA%\QuickPhrase\phrases.json
```

通常对应：

```text
C:\Users\<用户名>\AppData\Roaming\QuickPhrase\phrases.json
```

其中：

- 普通常用语正文可直接保存在数据文件中；
- 隐藏常用语正文使用 Windows DPAPI 加密；
- 常用语顺序也保存在该文件中。

### 应用设置

QuickPhrase 使用 `QSettings` 保存偏好设置。

Windows 下对应注册表：

```text
HKEY_CURRENT_USER\Software\LinyeXie\QuickPhrase
```

包括：

- 主题；
- 全局快捷键；
- 窗口位置；
- 单击 / 双击触发方式；
- 自动粘贴 / 复制模式；
- 软件密码盐和哈希；
- 其他应用偏好。

### 开机自启动

开机自启动使用：

```text
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
```

值名：

```text
QuickPhrase
```

启动参数：

```text
QuickPhrase.exe --startup
```

`--startup` 模式只启动系统托盘与后台功能，不弹出主界面。

---

## 卸载行为

更新、重新安装或降级时，QuickPhrase 会保留用户数据。

但是**真正卸载 QuickPhrase 会永久删除全部用户数据**。

包括：

```text
%APPDATA%\QuickPhrase
```

以及：

```text
HKEY_CURRENT_USER\Software\LinyeXie\QuickPhrase
```

同时清理：

- 所有常用语；
- 隐藏常用语；
- 软件密码验证数据；
- 快捷键设置；
- 窗口位置；
- 主题与其他偏好；
- 开机自启动项。

安装器在卸载前会再次显示不可恢复警告。

---

## PyInstaller 打包

项目提供：

```text
pyinstaller_build.txt
```

当前单行构建命令：

```bash
pyinstaller --noconfirm --clean --onefile --windowed --noupx --name QuickPhrase --icon QP.ico --add-data "QP.ico;ico" quickphrase.py
```

打包前确保项目目录中存在：

```text
QP.ico
```

打包完成后：

```text
dist\
└── QuickPhrase.exe
```

---

## Inno Setup 安装包

项目提供：

```text
QuickPhrase.iss
```

使用 **Inno Setup 6.x** 编译。

安装器会从 `quickphrase.py` 自动读取：

```python
APP_VERSION = "1.8.3"
```

生成类似：

```text
QuickPhrase_Setup_v1.8.3.exe
```

### 版本检测

安装器会检测已安装版本，并区分：

```text
首次安装
版本更新
相同版本重新安装
版本降级
```

为了兼容不同 Windows 安装模式，版本检测会检查：

- HKCU 32-bit；
- HKCU 64-bit；
- HKLM 32-bit；
- HKLM 64-bit。

并在固定 AppId 查询失败时扫描 Windows Uninstall 项中的 `DisplayName` / `DisplayVersion`。

---

## 项目结构

```text
QuickPhrase/
├── quickphrase.py
├── requirements.txt
├── QP.ico
├── QuickPhrase.iss
├── pyinstaller_build.txt
└── README.md
```

### 文件说明

| 文件 | 用途 |
| --- | --- |
| `quickphrase.py` | QuickPhrase 主程序 |
| `requirements.txt` | Python 依赖 |
| `QP.ico` | 软件 / EXE / 安装器统一图标 |
| `QuickPhrase.iss` | Inno Setup 安装脚本 |
| `pyinstaller_build.txt` | PyInstaller 单行打包命令 |
| `README.md` | GitHub 项目说明 |

---

## 主要技术栈

- **Python**
- **PySide6 / Qt**
- **keyboard**
- **Windows API / ctypes**
- **Windows Runtime / UserConsentVerifier**
- **Windows DPAPI**
- **QSettings**
- **PyInstaller**
- **Inno Setup**

QuickPhrase 中涉及 Windows 原生行为的部分包括：

- 前台窗口与焦点恢复；
- No-Activate 快捷窗口；
- TopMost 层级；
- 系统强调色；
- DPAPI；
- Windows Security / Hello；
- Windows Run 自启动；
- 注册表版本检测。

---

## 性能与稳定性设计

QuickPhrase 针对桌面常驻应用做了一些专门优化：

- 搜索输入防抖；
- 列表刷新期间暂停重绘；
- 快捷窗口未显示时避免无意义重建；
- 隐藏内容加密数据复用；
- 纯 Qt 鼠标排序，避免 Windows 原生 Drag & Drop 辅助窗口；
- 快捷窗口位置自动限制到当前显示器可见工作区；
- 多显示器和不同 DPI 缩放适配；
- Windows Hello 返回后减少不必要的 Z-order 重绘；
- 托盘单击/双击动作分离。

---

## 常见问题

### 为什么找不到 `phrases.json`？

按：

```text
Win + R
```

输入：

```text
%APPDATA%\QuickPhrase
```

即可直接打开数据目录。

---

### 为什么 Windows PIN 是灰色的？

QuickPhrase 没有检测到当前用户可使用的 Windows PIN / Hello 验证器。

可能原因包括：

- Windows Hello 未配置；
- 当前设备没有对应安全设备；
- 系统策略禁止；
- 当前 Windows 版本不支持该桌面验证接口。

此时可以使用 **软件密码**。

---

### 软件密码忘了怎么办？

软件密码无法从保存的哈希中恢复。

QuickPhrase 不提供绕过原密码的重置入口。

唯一恢复方式是：

1. 卸载 QuickPhrase；
2. 卸载器删除全部 QuickPhrase 数据；
3. 重新安装并重新配置。

---

### 修改软件密码会导致隐藏常用语失效吗？

不会。

软件密码用于**操作验证**，隐藏常用语正文仍由 Windows DPAPI 保护。

修改软件密码只会更新本地软件密码验证器。

---

### 更新版本会删除常用语吗？

不会。

安装器区分：

- 更新；
- 重装；
- 降级；
- 真正卸载。

前三种保留数据。

只有真正卸载才永久删除用户数据。

---

## 开发说明

如果你准备修改 QuickPhrase，建议遵循以下原则：

1. 不把 Windows Accent Color 写死为固定颜色；
2. 不在隐藏正文上保存明文副本；
3. 不绕过 DPAPI / Windows Security / 软件密码验证；
4. 不使用原生 `QDrag` 恢复排序功能；
5. Windows 焦点与 Z-order 修改应尽量幂等；
6. UI 尺寸优先使用 Qt logical pixels，避免硬编码物理像素；
7. 新增用户设置优先通过 `QSettings`；
8. 修改 `APP_VERSION` 后再构建安装包。

---

## Contributing

欢迎提交：

- Bug Report
- Feature Request
- Pull Request
- Windows 兼容性测试结果
- UI / UX 改进建议

提交 Bug 时建议附带：

```text
Windows 版本
系统缩放比例
显示器数量
Python / EXE 运行方式
QuickPhrase 版本
复现步骤
截图或错误信息
```

这样更容易定位 Windows 焦点、DPI、托盘或安装器相关问题。

---

## License

当前仓库如果尚未包含 `LICENSE` 文件，则默认**不代表已授予开源许可证**。

如果计划公开分发或接受第三方贡献，建议在发布 GitHub 仓库前明确选择并添加许可证，例如：

- MIT
- Apache-2.0
- GPL-3.0

---

## Acknowledgements

QuickPhrase 基于：

- Qt / PySide6
- Python
- PyInstaller
- Inno Setup
- Windows Runtime APIs
- Windows Data Protection API

感谢这些项目和平台提供的基础能力。

---

<p align="center">
  <strong>QuickPhrase</strong><br>
  Less typing. Faster input.
</p>
