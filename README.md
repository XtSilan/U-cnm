# U校园CNM😡

一个用于辅助监听 U校园Ai版学习页面“长时间未操作”提示弹窗的小工具（Windows）。

程序基于 `tkinter` 提供界面，使用 `DrissionPage` 控制浏览器并自动点击弹窗中的“确定”按钮。

## 功能

- 图形界面操作（打开浏览器、开始挂机、停止挂机）
- 基于 `timeline.state` 实时监测 SDK 状态（`STATE_READY/CONNECT/START/STOP/ERROR`）
- 自动从当前页面或同源子 frame 检测 `timeline` 实例，提升状态识别稳定性
- `STATE_STOP` 时自动检测并点击提示弹窗“确定”
- `STATE_ERROR` 时自动刷新页面并尝试勾选协议后点击登录恢复
- 自动/手动配置浏览器路径，并保存到本地配置
- 挂机期间尝试防止系统休眠与息屏
- 日志窗口实时显示运行状态与 SDK 状态

## 运行环境

- 操作系统：Windows
- Python：3.8 及以上（推荐 3.10+）
- 浏览器：Microsoft Edge 或 Google Chrome（可执行文件路径可配置）

## 安装依赖

在项目目录执行：

```powershell
pip install DrissionPage
```

## DEMO

![](./demo.gif)

## 使用方法

1. 运行脚本：

```powershell
python "U校园cnm.py"
```
（或者从 [GitHub Release v2.0](https://github.com/XtSilan/U-cnm/releases) 下载打包好的 exe）

2. 点击“打开浏览器”，程序会打开 `https://ucloud.unipus.cn/`。
3. 在浏览器中手动登录并进入课程学习页面（建议学习vocabulary）。
4. 点击“开始挂机”，程序会持续监听“长时间未操作”弹窗并自动点击“确定”。
5. 完成学习后点击“停止挂机”或直接关闭程序。

## SDK 状态说明

- `STATE_READY`：WebSocket 未连接或连接断开
- `STATE_CONNECT`：WebSocket 已连接，尚未进入计时
- `STATE_START`：学习计时进行中
- `STATE_STOP`：已停止计时（通常为超时自动停止后等待确认）
- `STATE_ERROR`：`start/stop` 请求异常（常见于网络波动）
- `UNKNOWN`：当前页面未找到可读取的 `timeline`

## 浏览器路径配置说明

- 程序会先尝试读取已保存路径。
- 若未保存，会尝试以下常见路径：
  - `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
  - `C:\Program Files\Microsoft\Edge\Application\msedge.exe`
  - `C:\Program Files\Google\Chrome\Application\chrome.exe`
  - `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`
- 若仍失败，会弹出文件选择框让你手动选择浏览器 `.exe`。
- 配置文件保存位置：`%APPDATA%\HangUpApp\browser_path.txt`

## 注意事项

- 本工具不处理验证码、人机校验等场景，出现相关验证需手动处理。
- 仅自动点击指定提示弹窗，不保证所有学习场景都适配。
- 请合理使用，遵守所在平台课程与考试相关规定。

## 常见问题

### 1. 点击“打开浏览器”失败

- 检查是否已安装 Edge/Chrome。
- 手动选择正确的浏览器可执行文件（`.exe`）。
- 确认 `DrissionPage` 已安装。

### 2. 程序没有自动点“确定”

- 确认当前页面确实出现了“由于你长时间未操作，请点确定继续使用。”提示。
- 页面结构变更可能导致定位失效，需要更新脚本中的 XPath。

### 3. 防休眠没有生效

- 可能受系统策略、权限或第三方电源管理软件影响。
- 不影响弹窗监听主流程。

### 4. 长时间未弹出确认窗口

- `STATE_STOP` 时脚本会继续监听并自动点击“确定”。
- 若网络波动导致 `stop` 请求失败进入 `STATE_ERROR`，脚本会自动刷新页面并尝试自动登录恢复。
- 可能浏览器处于最小化状态，自动进入节流模式，定时器精度被限制，`timeout` 时间被拉长。
  - 解决办法：尽量将浏览器置于前台。

### 5. SDK 状态一直是 `UNKNOWN`

- 确认当前标签页已进入具体学习内容页（不是课程列表页或空白页）。
- 点击一次课程内容，等待页面 JS 初始化（`window.timeline` 可能延迟创建）。
- 查看日志中的 `timeline 探测结果` 与 `SDK 调试探针`，确认是否检测到 `timeline@window` 或 `timeline@frame[x]`。
- 若页面刚刷新并跳转登录，先完成登录，状态会在进入学习页后恢复为 `STATE_CONNECT/STATE_START`。

## 文件说明

- `U校园cnm.exe`：可从 [GitHub Release v2.0](https://github.com/XtSilan/U-cnm/releases) 下载

- `U校园cnm.py`：主程序文件

## 更新日志

- v1.0: 提交仓库
- v1.1: 增加浏览器保活，改善最小化后台冻结
- v1.2: 新增连接存活检测,修复检测连接逻辑,增加校验连接
- v1.3: 新增`error`状态自动刷新页面
- v2.0: 重构为基于 `timeline.state` 的状态监测；`STATE_STOP` 自动点确定；`STATE_ERROR` 自动刷新并尝试登录恢复；新增 SDK 状态显示
