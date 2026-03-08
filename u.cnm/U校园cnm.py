import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import ctypes

from DrissionPage import ChromiumOptions, ChromiumPage


def hide_console_window():
    """在 Windows 下隐藏当前控制台窗口（如果有）。"""
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        # 隐藏失败不影响主功能
        pass


class HangUpApp:
    def __init__(self):
        self.target_url = "https://ucloud.unipus.cn/"
        self.root = tk.Tk()
        self.root.title("U校园CNM(v2.0)")
        self.root.geometry("560x360")

        self.page = None
        self.monitoring = False
        self.monitor_thread = None
        self.browser_cfg_file = self._get_browser_cfg_file()
        self.sleep_prevented = False

        # Windows 电源管理标志：防睡眠/防息屏，以及恢复连续状态。
        self.ES_CONTINUOUS = 0x80000000
        self.ES_SYSTEM_REQUIRED = 0x00000001
        self.ES_DISPLAY_REQUIRED = 0x00000002

        # 弹窗中“确定”按钮会动态 id，这里用文本 + 结构来定位。
        self.confirm_btn_xpath = (
            "xpath://div[.//p[contains(.,'由于你长时间未操作，请点确定继续使用。')]]"
            "//button[normalize-space()='确定']"
        )
        # STATE_STOP 持续过久通常意味着会话异常（例如登录态丢失）。
        self.stop_stuck_timeout_seconds = 30 #判定登陆丢失时间
        self.stop_recover_cooldown_seconds = 60 #自动恢复冷却时间

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _get_browser_cfg_file(self):
        base_dir = os.getenv("APPDATA") or os.path.expanduser("~")
        cfg_dir = os.path.join(base_dir, "HangUpApp")
        os.makedirs(cfg_dir, exist_ok=True)
        return os.path.join(cfg_dir, "browser_path.txt")

    def _load_saved_browser_path(self):
        if not os.path.exists(self.browser_cfg_file):
            return None
        try:
            path = open(self.browser_cfg_file, "r", encoding="utf-8").read().strip()
            if path and os.path.exists(path):
                return path
        except Exception as e:
            self.log(f"读取浏览器配置失败：{e}")
        return None

    def _save_browser_path(self, path):
        try:
            with open(self.browser_cfg_file, "w", encoding="utf-8") as f:
                f.write(path)
            self.log(f"已保存浏览器路径配置：{self.browser_cfg_file}")
            return True
        except Exception as e:
            self.log(f"保存浏览器配置失败：{e}")
            return False

    def _build_options(self, browser_path=None):
        options = ChromiumOptions()
        if browser_path:
            options.set_browser_path(browser_path)
        # 尽量降低浏览器在最小化/后台时的节流与挂起概率，提升挂机稳定性。
        options.set_argument("--disable-background-timer-throttling")
        options.set_argument("--disable-backgrounding-occluded-windows")
        options.set_argument("--disable-renderer-backgrounding")
        options.set_argument("--disable-features=CalculateNativeWinOcclusion")
        return options

    def _prevent_sleep(self):
        if self.sleep_prevented:
            return True
        try:
            flags = self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED | self.ES_DISPLAY_REQUIRED
            result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
            if result == 0:
                self.log("防休眠设置失败（系统调用返回 0）。")
                return False
            self.sleep_prevented = True
            self.log("已启用防休眠/防息屏。")
            return True
        except Exception as e:
            self.log(f"防休眠设置异常：{e}")
            return False

    def _restore_power_policy(self):
        if not self.sleep_prevented:
            return True
        try:
            result = ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
            if result == 0:
                self.log("恢复电源策略失败（系统调用返回 0）。")
                return False
            self.sleep_prevented = False
            self.log("已恢复系统默认电源策略。")
            return True
        except Exception as e:
            self.log(f"恢复电源策略异常：{e}")
            return False

    def _configure_browser_path(self):
        """
        选择并保存浏览器可执行文件路径。
        先尝试常见安装路径，失败后让用户手动选择。
        """
        saved_path = self._load_saved_browser_path()
        if saved_path:
            self.log(f"检测到已保存浏览器路径：{saved_path}")
            return True

        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]

        for path in candidates:
            if os.path.exists(path):
                if self._save_browser_path(path):
                    self.log(f"已自动设置浏览器路径：{path}")
                    return True

        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="请选择浏览器可执行文件",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")],
        )
        if not file_path:
            self.log("未选择浏览器可执行文件。")
            return False

        if self._save_browser_path(file_path):
            self.log(f"已设置浏览器路径：{file_path}")
            return True
        return False

    def _build_ui(self):
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=12, pady=12)

        tk.Button(top, text="打开浏览器", width=14, command=self.open_browser).pack(
            side="left", padx=4
        )
        tk.Button(top, text="开始挂机", width=14, command=self.start_monitor).pack(
            side="left", padx=4
        )
        tk.Button(top, text="停止挂机", width=14, command=self.stop_monitor).pack(
            side="left", padx=4
        )

        status_frame = tk.Frame(self.root)
        status_frame.pack(fill="x", padx=12)
        tk.Label(status_frame, text="状态：", anchor="w").pack(side="left")
        self.status_var = tk.StringVar(value="未连接浏览器")
        self.status_label = tk.Label(
            status_frame, textvariable=self.status_var, anchor="w", fg="red"
        )
        self.status_label.pack(side="left")
        tk.Label(status_frame, text="  SDK状态：", anchor="w").pack(side="left")
        self.sdk_state_var = tk.StringVar(value="UNKNOWN")
        self.sdk_state_label = tk.Label(
            status_frame, textvariable=self.sdk_state_var, anchor="w", fg="black"
        )
        self.sdk_state_label.pack(side="left")

        tips = (
            "使用步骤：\n"
            "1. 点“打开浏览器”后，会自动打开 U校园Ai 页面，请手动登录并进入课程学习。\n"
            "2. 点“开始挂机”，程序会持续监听是否出现“长时间未操作”弹窗。\n"
            "3. 发现弹窗后会自动点击“确定”，然后继续监听。\n"
            "4. 请在刷完后将学习页面下一个/下一步点完再关闭浏览器，否则可能会被判定为未完成学习。\n"
            "注意：此脚本没有做人机验证处理，如果弹出验证码请手动操作。"
        )
        tk.Label(self.root, text=tips, justify="left", anchor="w").pack(
            fill="x", padx=12, pady=(8, 6)
        )

        self.log_text = tk.Text(self.root, height=11)
        self.log_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _set_status(self, text):
        self.status_var.set(text)
        color_map = {
            "未连接浏览器": "red",
            "浏览器已连接，等待开始挂机": "#B8860B",
            "已停止挂机": "#B8860B",
            "挂机中（监听弹窗）": "green",
        }
        self.status_label.config(fg=color_map.get(text, "black"))

    def _set_sdk_state(self, sdk_state):
        self.sdk_state_var.set(sdk_state)
        color_map = {
            "STATE_READY": "#B8860B",
            "STATE_CONNECT": "#B8860B",
            "STATE_START": "green",
            "STATE_STOP": "red",
            "STATE_ERROR": "red",
            "UNKNOWN": "black",
        }
        self.sdk_state_label.config(fg=color_map.get(sdk_state, "black"))

    def log(self, msg):
        now = time.strftime("%H:%M:%S")
        line = f"[{now}] {msg}\n"
        self.log_text.insert("end", line)
        self.log_text.see("end")

    def _page_connected(self):
        if self.page is None:
            return False
        try:
            self.page.run_js("void 0;")
            return True
        except Exception:
            return False

    def _is_disconnect_error(self, err):
        text = str(err)
        tokens = ["连接已断开", "disconnected", "Target page, context or browser has been closed"]
        return any(t in text for t in tokens)

    def _get_sdk_state(self):
        script = """
        return (() => {
            try {
                const states = ["STATE_READY", "STATE_CONNECT", "STATE_START", "STATE_STOP", "STATE_ERROR"];
                const normalizeState = (value) => {
                    if (value === undefined || value === null) return null;
                    const text = String(value);
                    return states.includes(text) ? text : null;
                };

                // 1) 当前页面直接查
                if (window.timeline) {
                    const state = normalizeState(window.timeline.state);
                    if (state) return state;
                }

                // 1.1) 全局属性兜底：找具有 start/stop/on/off/state 的 timeline 实例
                for (const key in window) {
                    try {
                        const obj = window[key];
                        if (!obj || typeof obj !== "object") continue;
                        if (typeof obj.start !== "function") continue;
                        if (typeof obj.stop !== "function") continue;
                        if (typeof obj.on !== "function") continue;
                        if (typeof obj.off !== "function") continue;
                        const state = normalizeState(obj.state);
                        if (state) {
                            if (!window.timeline) window.timeline = obj;
                            return state;
                        }
                    } catch (e) {
                        // ignore
                    }
                }

                // 2) 同源子 frame 里查（学习页面常见嵌套）
                for (let i = 0; i < window.frames.length; i++) {
                    try {
                        const frameWin = window.frames[i];
                        if (!frameWin || !frameWin.timeline) continue;
                        const state = normalizeState(frameWin.timeline.state);
                        if (state) return state;
                    } catch (e) {
                        // 跨域 frame 会抛错，忽略继续
                    }
                }

                return "UNKNOWN";
            } catch (e) {
                return "UNKNOWN";
            }
        })();
        """
        state = self.page.run_js(script)
        return str(state) if state else "UNKNOWN"

    def _debug_sdk_probe(self):
        script = """
        return (() => {
            try {
                const out = {
                    href: window.location.href || "",
                    hasTimeline: !!window.timeline,
                    timelineStateRaw: null,
                    timelineStateType: null,
                    candidateKey: null,
                    candidateStateRaw: null,
                    frameCount: window.frames.length || 0
                };

                if (window.timeline) {
                    out.timelineStateRaw = String(window.timeline.state);
                    out.timelineStateType = typeof window.timeline.state;
                }

                for (const key in window) {
                    try {
                        const obj = window[key];
                        if (!obj || typeof obj !== "object") continue;
                        if (typeof obj.start !== "function" || typeof obj.stop !== "function") continue;
                        if (typeof obj.on !== "function" || typeof obj.off !== "function") continue;
                        out.candidateKey = key;
                        out.candidateStateRaw = String(obj.state);
                        break;
                    } catch (e) {}
                }
                return JSON.stringify(out);
            } catch (e) {
                return "probe_error:" + String(e);
            }
        })();
        """
        try:
            result = self.page.run_js(script)
            return str(result) if result else "probe_empty"
        except Exception as e:
            return f"probe_exception:{e}"

    def _recover_from_state_error(self):
        self.log("检测到 STATE_ERROR，准备刷新页面尝试恢复。")
        self.page.refresh()
        self.log("页面刷新完成，尝试自动执行登录。")
        time.sleep(1.0)
        self._try_auto_login_after_refresh()

    def _recover_from_stuck_stop(self):
        self.log("STATE_STOP 持续过久，判定可能登录态丢失，开始自动恢复。")
        self.page.refresh()
        self.log("页面刷新完成，尝试自动执行登录。")
        time.sleep(1.0)
        self._try_auto_login_after_refresh()

    def _probe_timeline(self):
        script = """
        return (() => {
            try {
                if (window.timeline) return "timeline@window";
                for (let i = 0; i < window.frames.length; i++) {
                    try {
                        if (window.frames[i] && window.frames[i].timeline) {
                            return "timeline@frame[" + i + "]";
                        }
                    } catch (e) {}
                }
                return "timeline_not_found";
            } catch (e) {
                return "timeline_probe_error";
            }
        })();
        """
        try:
            result = self.page.run_js(script)
            return str(result) if result else "timeline_probe_error"
        except Exception:
            return "timeline_probe_error"

    def _try_auto_login_after_refresh(self):
        agreement_xpath = (
            "xpath://div[contains(@class,'login-action')]"
            "//div[@id='agreement']//input[@type='checkbox']"
        )
        login_btn_xpath = (
            "xpath://div[contains(@class,'login-action')]"
            "//button[@id='login' and normalize-space()='登录']"
        )

        login_btn = self.page.ele(login_btn_xpath, timeout=2)
        if not login_btn:
            self.log("未检测到登录按钮，继续监听 SDK 状态。")
            return

        checked = False
        try:
            checked = bool(
                self.page.run_js(
                    "const n=document.querySelector('#agreement input[type=\"checkbox\"]');"
                    "return n ? n.checked : false;"
                )
            )
        except Exception:
            checked = False

        if not checked:
            checkbox = self.page.ele(agreement_xpath, timeout=1)
            if checkbox:
                checkbox.click()
                self.log("已自动勾选登录协议。")
                time.sleep(0.2)

        login_btn.click()
        self.log("已自动点击登录按钮。")

    def open_browser(self):
        def do_open():
            browser_path = self._load_saved_browser_path()
            if not self._page_connected():
                if self.page is not None:
                    self.log("检测到旧浏览器连接已失效，正在重新连接...")
                self.page = None
                self.page = ChromiumPage(self._build_options(browser_path))
                self.log(f"浏览器已连接，正在打开：{self.target_url}")
                self.page.get(self.target_url)
                self.log("页面已打开，请手动登录并进入课程。")
            else:
                self.log(f"浏览器已连接，正在跳转：{self.target_url}")
                self.page.get(self.target_url)
            self._set_status("浏览器已连接，等待开始挂机")
            self._set_sdk_state("UNKNOWN")

        try:
            do_open()
        except Exception as e:
            self.page = None
            self.log(f"首次连接浏览器失败：{e}")
            self.log("尝试自动配置浏览器路径...")

            if self._configure_browser_path():
                try:
                    do_open()
                    return
                except Exception as e2:
                    self.page = None
                    self.log(f"配置后重试仍失败：{e2}")
                    messagebox.showerror("错误", f"打开浏览器失败：\n{e2}")
            else:
                messagebox.showerror("错误", f"打开浏览器失败：\n{e}")

    def _monitor_loop(self):
        self.log("开始监听弹窗...")
        self._set_status("挂机中（监听弹窗）")
        last_heartbeat = 0.0
        last_sdk_state = "UNKNOWN"
        last_error_recover_at = 0.0
        stop_state_since = None
        last_stop_recover_at = 0.0
        try:
            while self.monitoring:
                try:
                    # 定时执行一个极轻量 JS，避免页面长时间完全空闲被系统判定为可挂起。
                    now = time.time()
                    if now - last_heartbeat >= 20:
                        self.page.run_js("void 0;")
                        last_heartbeat = now

                    sdk_state = self._get_sdk_state()
                    if sdk_state != last_sdk_state:
                        self._set_sdk_state(sdk_state)
                        if sdk_state == "UNKNOWN":
                            self.log(f"timeline 探测结果：{self._probe_timeline()}")
                            self.log(f"SDK 调试探针：{self._debug_sdk_probe()}")
                        if sdk_state == "STATE_STOP":
                            stop_state_since = now
                        else:
                            stop_state_since = None
                        last_sdk_state = sdk_state

                    if sdk_state == "STATE_ERROR":
                        if now - last_error_recover_at >= 30:
                            last_error_recover_at = now
                            self._recover_from_state_error()
                            time.sleep(1.0)
                        else:
                            time.sleep(1.0)
                        continue

                    if sdk_state == "STATE_STOP":
                        btn = self.page.ele(self.confirm_btn_xpath, timeout=0)
                        if btn:
                            btn.click()
                            self.log("检测到超时弹窗，已自动点击“确定”。")
                            time.sleep(0.6)
                        else:
                            if (
                                stop_state_since is not None
                                and now - stop_state_since >= self.stop_stuck_timeout_seconds
                                and now - last_stop_recover_at >= self.stop_recover_cooldown_seconds
                            ):
                                last_stop_recover_at = now
                                self._recover_from_stuck_stop()
                                time.sleep(1.0)
                            else:
                                time.sleep(1.0)
                        continue

                    time.sleep(1.0)
                except Exception as e:
                    self.log(f"监听异常：{e}")
                    if self._is_disconnect_error(e):
                        self.log("检测到浏览器/页面连接已断开，已自动停止挂机，请重新点击“打开浏览器”。")
                        self.page = None
                        self.monitoring = False
                        break
                    time.sleep(1.2)
        finally:
            self._restore_power_policy()
            self._set_status("已停止挂机")
            self._set_sdk_state("UNKNOWN")
            self.log("监听已停止。")

    def start_monitor(self):
        if not self._page_connected():
            self.page = None
            messagebox.showwarning("提示", "请先点击“打开浏览器”。")
            return
        if self.monitoring:
            self.log("挂机已在运行中。")
            return
        self._prevent_sleep()
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitor(self):
        if not self.monitoring:
            self.log("挂机当前未运行。")
            self._restore_power_policy()
            return
        self.monitoring = False

    def on_close(self):
        self.monitoring = False
        self._restore_power_policy()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    hide_console_window()
    app = HangUpApp()
    app.run()
