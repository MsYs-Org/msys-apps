# MSYS Everyday Apps

## 0.1.11 Notes input-method lifecycle

Notes addresses only the replaceable `role:input-method`. Focus and real text
touches request `show`, explicit Save/`Ctrl+S`/`Ctrl+Enter`, focus loss, and
window close request `hide`. Requests are coalesced off the Tk thread, while a
new touch can reassert `show` after the provider dismissed itself. The cold
show deadline includes the provider's bounded on-demand Tk startup. This is a
thin package-local adapter because the current SDK has no Tk input-method
binding helper; it is intentionally shaped for later extraction into the SDK.

## 0.1.10 responsive application surfaces

Release builds vendor the immutable `msys_sdk` source into `files/app/msys_sdk`.
The application remains isolated without relying on a host `PYTHONPATH`, while
localized UI and mIPC contracts remain available.

Device Info prefers the inherited private component channel for all RPCs. Its
single reader dispatches lifecycle/events and concurrent replies, so Core can
enforce the permissions declared by `org.msys.apps:device-info`. The public
control socket is retained only as a standalone-development fallback.

`org.msys.apps` 是一个真实可安装的普通应用包，不是系统服务集合。包内三个 Tk
component 与 Qt、Electron、C/C++ 应用一样遵守 `msys.manifest.v1`、mIPC 生命周期和
X11 稳定身份；它们不成为 PID 1，也不依赖 systemd、D-Bus、logind、polkit、目标机
包管理器或 `PYTHONPATH`。

## 应用

| Component | 功能 | 数据/系统边界 |
| --- | --- | --- |
| `org.msys.apps:notes` | 自动保存的单页 Notes | 只写 `MSYS_APP_STATE_DIR/notes/note.txt` |
| `org.msys.apps:calculator` | 四则、整除、取模和幂运算 | 纯本地有界解析，不调用 `eval`/`exec` |
| `org.msys.apps:device-info` | Core、Role、Isolation 与 HAL inventory | 只调用 `msys.core` 和 `interface:org.msys.hal.manager.v1` |

三个窗口都为 320×480 触摸屏设计：大按钮、自动换行标题、可滚动内容和紧凑状态栏；
480×320 横屏会压缩 Calculator 的显示区和按键间距，Device Info 自动切换双列卡片；
Notes 编辑器和信息卡均支持带阈值的手指拖动，点击仍保留原本行为。窗口标题栏与桌面都使用同一份 component PPM
图标，配色与 Settings 的轻量 Material 风格一致。manifest 对每个 component 都声明：

- `runtime: tk`、`lifecycle: manual`、`restart: never`；
- `readiness.mode: mipc-ready`；
- `isolation: baseline`；
- `windowing.display: inherit`，由选中的 display-output session 注入真实 `DISPLAY`；
- 独立 `app_id`、WM_CLASS、WM instance 和标题；
- `activation.launchable: true`。

package icon 与三个 component 的 `icons` 都是包内 32×32 P6 PPM 真图片，可由目标机
Tk `PhotoImage` 直接读取。包级图标
是通用 fallback，component 级标准图标分别用于 Notes、Calculator 与 Device Info；
它们只影响展示，不会绕过 `activation.launchable`。

每个 Tk 窗口都会调用 SDK 的 canonical identity helper，在原生窗口首次映射前写入
小写 WM_CLASS、`_MSYS_APP_ID` 与 `_MSYS_COMPONENT_ID`，避免 Tk 将
`org.msys.*` 自动改为 `Org.msys.*` 后丢失 component 归属。窗口可见标题由应用依据
当前 locale 生成，manifest 的英文标题只保留为窗口策略的兼容 fallback。

## 安全与失败行为

### Notes

Notes 对 UTF-8 内容设置 512 KiB 上限。每次保存都在同一目录以 `O_EXCL` 创建 0600
临时文件，完整写入后 `fsync`，再用 `os.replace` 原子切换并同步父目录。失败时旧文件
保持不变，临时文件会清理；读取使用 `O_NOFOLLOW`，不会跟随伪造的 note symlink。
编辑停止 900 ms 后自动保存，关闭窗口前也会保存，`Ctrl+S` 和触摸 Save 都可用。

### Calculator

Calculator 使用手写 tokenizer 和递归下降 parser，只识别：

```text
数字  ( )  +  -  *  /  //  %  **
```

没有 Python 名称、属性、调用、容器或语句通道。表达式限制为 256 字符/128 token，
数值、结果和指数也有上限；除零、非实数、非有限数和超大幂均返回用户可读错误。

### Device Info

Device Info 不读取 `/proc`、`/sys`、`os-release`，也不运行 `uname` 或子进程。所有内容
通过已认证的 component channel 查询（独立预览才回退到 public control socket）；每次
调用都有 deadline、request-id 校验和 256 KiB 包上限。Core 的三个 section 与 HAL
独立降级，并以可换行、可触摸滚动的信息卡展示；例如 HAL 未安装时会将同一错误对象
呈现为“不可用”卡片，而不是把整页 raw JSON 直接塞给用户。

这不会关闭 Device Info，也不会影响 Notes 或 Calculator。

## 本地验证

界面文字统一来自 `files/share/i18n/catalog.json`，使用
`msys.i18n.catalog.v1` 与 `msys_sdk.Translator`。当前提供 `zh-CN`、通用
`zh` 父级和 `en-US`；因此 `zh-Hans-CN` 等规范 locale 不会意外掉回英文。
语言选择遵循 `MSYS_LOCALE`、`LC_ALL`、`LC_MESSAGES`、`LANG`，
不需要 i18n 服务或 D-Bus。Tk/Qt 共用的字体 family、像素字号策略也来自
`msys_sdk.ui_fonts`。包构建时把 SDK 作为不可变源码 overlay 放进
`files/app/msys_sdk`：

从 `G:\Code\MsYs` 执行：

```powershell
wsl env PYTHONPATH=/mnt/g/Code/MsYs/msys-apps/files/app:/mnt/g/Code/MsYs/msys-sdk `
  python3 -m unittest discover -s /mnt/g/Code/MsYs/msys-apps/tests -v

wsl env `
  PYTHONPATH=/mnt/g/Code/MsYs/msys-tools:/mnt/g/Code/MsYs/msys-install:/mnt/g/Code/MsYs/msys-sdk `
  python3 -m msys_tools.dev package validate /mnt/g/Code/MsYs/msys-apps
```

第一条 `PYTHONPATH` 只用于从源码目录运行测试；安装包入口直接位于
`files/app/*.py`，Python 会从脚本目录发现随包模块，目标机运行时无需该变量。

## 构建、安装与启动

```powershell
wsl env PYTHONPATH=/mnt/g/Code/MsYs/msys-tools:/mnt/g/Code/MsYs/msys-install:/mnt/g/Code/MsYs/msys-sdk `
  python3 -m msys_tools.dev package build /mnt/g/Code/MsYs/msys-apps `
  --output /mnt/g/Code/MsYs/dist --force `
  --overlay /mnt/g/Code/MsYs/msys-sdk/msys_sdk=files/app/msys_sdk

# 使用 build 输出的 archive；install-agent 会校验 hashes 并原子安装
wsl env PYTHONPATH=/mnt/g/Code/MsYs/msys-tools `
  python3 -m msys_tools.dev install-archive /mnt/g/Code/MsYs/dist/<archive>.tar.gz

wsl env PYTHONPATH=/mnt/g/Code/MsYs/msys-tools `
  python3 -m msys_tools.dev start-component org.msys.apps:notes
wsl env PYTHONPATH=/mnt/g/Code/MsYs/msys-tools `
  python3 -m msys_tools.dev start-component org.msys.apps:calculator
wsl env PYTHONPATH=/mnt/g/Code/MsYs/msys-tools `
  python3 -m msys_tools.dev start-component org.msys.apps:device-info
```

安装和启动流程不会调用 apt、pip 或其他目标包管理器。本任务只完成本地包，不执行
远端安装。

## 目录

```text
manifest.json                         统一安装、窗口与生命周期声明
files/app/*.py                        无 PYTHONPATH 的三个安装入口
files/app/msys_apps/calculator.py     安全表达式 parser
files/app/msys_apps/storage.py        Notes 原子存储
files/app/msys_apps/ipc.py            公共 RPC 与 component 生命周期
files/app/msys_apps/device_info.py    纯 mIPC 查询/降级模型
files/app/msys_apps/*_app.py          三个 320×480 Tk 前端
files/share/icons/*.ppm               套件与 component PPM 图标
tests/                                parser、存储、IPC、模型、manifest 分层测试
```
