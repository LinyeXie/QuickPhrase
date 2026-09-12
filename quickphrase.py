from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import keyboard
from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QRect,
    QPropertyAnimation,
    QSettings,
    QSize,
    Qt,
    Signal,
    QObject,
    Property,
    QTimer,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QKeySequenceEdit,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

APP_NAME = "QuickPhrase"
APP_VERSION = "1.8.3"
ORG_NAME = "LinyeXie"
APP_ICON_NAME = "QP.ico"
DEFAULT_HOTKEY = "Ctrl+Alt+Space"

if os.name == "nt":
    from ctypes import wintypes


# ---------------------------------------------------------------------------
# Paths / Settings
# ---------------------------------------------------------------------------

def app_icon_path() -> Path | None:
    """
    Resolve QP.ico consistently in development, PyInstaller one-file mode,
    and the installed application folder.
    """
    candidates: list[Path] = []

    # PyInstaller --add-data "QP.ico;ico"
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "ico" / APP_ICON_NAME)
        candidates.append(Path(bundle_root) / APP_ICON_NAME)

    # Development: QP.ico sits next to quickphrase.py.
    try:
        candidates.append(Path(__file__).resolve().parent / APP_ICON_NAME)
    except Exception:
        pass

    # Installed fallback: {app}\\ico\\QP.ico.
    try:
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "ico" / APP_ICON_NAME)
        candidates.append(exe_dir / APP_ICON_NAME)
    except Exception:
        pass

    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def load_app_icon() -> QIcon:
    path = app_icon_path()
    if path is None:
        return QIcon()
    return QIcon(str(path))


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        path = Path(base) / APP_NAME
    else:
        path = Path.home() / f".{APP_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_FILE = app_data_dir() / "phrases.json"


class AppSettings:
    def __init__(self):
        self.qs = QSettings(ORG_NAME, APP_NAME)

    @property
    def theme_mode(self) -> str:
        value = str(self.qs.value("ui/themeMode", "system"))
        return value if value in {"system", "light", "dark"} else "system"

    @theme_mode.setter
    def theme_mode(self, value: str) -> None:
        self.qs.setValue("ui/themeMode", value)

    @property
    def hotkey(self) -> str:
        return str(self.qs.value("hotkey/summon", DEFAULT_HOTKEY))

    @hotkey.setter
    def hotkey(self, value: str) -> None:
        self.qs.setValue("hotkey/summon", value)

    @property
    def action_mode(self) -> str:
        value = str(self.qs.value("behavior/actionMode", "paste"))
        return value if value in {"paste", "copy"} else "paste"

    @action_mode.setter
    def action_mode(self, value: str) -> None:
        self.qs.setValue("behavior/actionMode", value)

    @property
    def clear_clipboard(self) -> bool:
        return self.qs.value("behavior/clearClipboard", False, type=bool)

    @clear_clipboard.setter
    def clear_clipboard(self, value: bool) -> None:
        self.qs.setValue("behavior/clearClipboard", bool(value))

    @property
    def phrase_trigger_mode(self) -> str:
        value = str(self.qs.value("behavior/phraseTriggerMode", "single"))
        return value if value in {"single", "double"} else "single"

    @phrase_trigger_mode.setter
    def phrase_trigger_mode(self, value: str) -> None:
        if value in {"single", "double"}:
            self.qs.setValue("behavior/phraseTriggerMode", value)

    @property
    def close_prompt_suppressed(self) -> bool:
        return self.qs.value("window/closePromptSuppressed", False, type=bool)

    @close_prompt_suppressed.setter
    def close_prompt_suppressed(self, value: bool) -> None:
        self.qs.setValue("window/closePromptSuppressed", bool(value))

    @property
    def close_action(self) -> str:
        value = str(self.qs.value("window/closeAction", "minimize"))
        return value if value in {"minimize", "exit"} else "minimize"

    @close_action.setter
    def close_action(self, value: str) -> None:
        if value in {"minimize", "exit"}:
            self.qs.setValue("window/closeAction", value)

    @property
    def tray_double_click_action(self) -> str:
        value = str(self.qs.value("tray/doubleClickAction", "main"))
        return value if value in {"main", "picker", "preferences"} else "main"

    @tray_double_click_action.setter
    def tray_double_click_action(self, value: str) -> None:
        if value in {"main", "picker", "preferences"}:
            self.qs.setValue("tray/doubleClickAction", value)

    @property
    def startup_enabled(self) -> bool:
        # Windows Run registry is the source of truth so installer and app UI
        # always reflect the same state.
        return windows_startup_enabled()

    @property
    def security_mode(self) -> str:
        value = str(self.qs.value("security/mode", "pin"))
        return value if value in {"pin", "password"} else "pin"

    @security_mode.setter
    def security_mode(self, value: str) -> None:
        if value in {"pin", "password"}:
            self.qs.setValue("security/mode", value)
            self.qs.sync()

    @property
    def picker_position_remembered(self) -> bool:
        return self.qs.value("window/pickerPositionRemembered", False, type=bool)

    @picker_position_remembered.setter
    def picker_position_remembered(self, value: bool) -> None:
        self.qs.setValue("window/pickerPositionRemembered", bool(value))

    @property
    def picker_position_schema(self) -> int:
        return int(self.qs.value("window/pickerPositionSchema", 1))

    @picker_position_schema.setter
    def picker_position_schema(self, value: int) -> None:
        self.qs.setValue("window/pickerPositionSchema", int(value))

    def save_main_geometry(self, geometry) -> None:
        self.qs.setValue("window/mainGeometry", geometry)

    def main_geometry(self):
        return self.qs.value("window/mainGeometry")

    def picker_pos(self):
        value = self.qs.value("window/pickerPos")
        return value if isinstance(value, QPoint) else None

    def save_picker_pos(self, pos: QPoint) -> None:
        self.qs.setValue("window/pickerPos", pos)


STARTUP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_RUN_VALUE = "QuickPhrase"


def startup_command() -> str:
    """
    Command stored in HKCU Run.

    Installed/PyInstaller builds:
        "QuickPhrase.exe" --startup

    Source/dev runs:
        "python.exe" "quickphrase.py" --startup
    """
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" --startup'

    try:
        script = Path(__file__).resolve()
    except Exception:
        script = Path(sys.argv[0]).resolve()

    return f'"{Path(sys.executable).resolve()}" "{script}" --startup'


def windows_startup_enabled() -> bool:
    if os.name != "nt":
        return False

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            STARTUP_RUN_KEY,
            0,
            winreg.KEY_READ,
        ) as key:
            value, _ = winreg.QueryValueEx(key, STARTUP_RUN_VALUE)

        return bool(str(value).strip())
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_windows_startup_enabled(enabled: bool) -> tuple[bool, str]:
    if os.name != "nt":
        return False, "开机自启动仅支持 Windows。"

    try:
        import winreg

        if enabled:
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                STARTUP_RUN_KEY,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(
                    key,
                    STARTUP_RUN_VALUE,
                    0,
                    winreg.REG_SZ,
                    startup_command(),
                )
        else:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    STARTUP_RUN_KEY,
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.DeleteValue(key, STARTUP_RUN_VALUE)
            except FileNotFoundError:
                pass

        return True, ""
    except OSError as exc:
        return False, f"无法修改 Windows 开机自启动设置：{exc}"


# ---------------------------------------------------------------------------
# Windows helpers
# ---------------------------------------------------------------------------

def windows_apps_use_light_theme() -> bool:
    if os.name != "nt":
        return True
    try:
        import winreg

        path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return bool(int(value))
    except Exception:
        return True


def windows_accent_color() -> QColor:
    """
    Read the current Windows accent color. Falls back to Windows blue only
    when the registry value cannot be read.
    """
    fallback = QColor("#0067C0")
    if os.name != "nt":
        return fallback

    try:
        import winreg

        path = r"Software\Microsoft\Windows\DWM"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, _ = winreg.QueryValueEx(key, "ColorizationColor")
        value = int(value)
        r = (value >> 16) & 0xFF
        g = (value >> 8) & 0xFF
        b = value & 0xFF
        color = QColor(r, g, b)
        return color if color.isValid() else fallback
    except Exception:
        return fallback


def available_screen_for_point(point: QPoint):
    screen = QApplication.screenAt(point)
    return screen or QApplication.primaryScreen()


def clamp_window_top_left(
    pos: QPoint,
    size: QSize,
    screen=None,
    margin: int = 8,
) -> QPoint:
    """
    Keep a top-level window fully reachable on the chosen monitor.
    Uses Qt logical pixels, so it remains stable at 100/125/150/175/200% DPI.
    """
    screen = screen or available_screen_for_point(pos)
    if screen is None:
        return pos

    area = screen.availableGeometry()

    max_x = max(area.left() + margin, area.right() - size.width() - margin + 1)
    max_y = max(area.top() + margin, area.bottom() - size.height() - margin + 1)

    x = min(max(pos.x(), area.left() + margin), max_x)
    y = min(max(pos.y(), area.top() + margin), max_y)
    return QPoint(int(x), int(y))


def centered_window_pos(size: QSize, screen=None) -> QPoint:
    screen = screen or QApplication.primaryScreen()
    if screen is None:
        return QPoint(100, 100)
    area = screen.availableGeometry()
    return QPoint(
        area.left() + max(0, (area.width() - size.width()) // 2),
        area.top() + max(0, (area.height() - size.height()) // 2),
    )


def adaptive_slim_size(screen=None) -> QSize:
    """
    Target roughly 1:2 (width:height) while remaining usable on small screens.
    """
    screen = screen or QApplication.primaryScreen()
    if screen is None:
        return QSize(340, 680)

    area = screen.availableGeometry()
    usable_w = max(320, area.width() - 24)
    usable_h = max(500, area.height() - 24)

    target_h = min(760, usable_h, max(540, int(area.height() * 0.72)))
    target_w = min(390, usable_w, max(310, int(target_h / 2)))

    # On very small displays, preserve reachability over the nominal ratio.
    if target_h > usable_h:
        target_h = usable_h
    if target_w > usable_w:
        target_w = usable_w

    return QSize(int(target_w), int(target_h))


def adaptive_picker_size(screen=None) -> QSize:
    """Quick picker is 70% of the normal slim-window size."""
    base = adaptive_slim_size(screen)
    return QSize(
        max(218, int(round(base.width() * 0.70))),
        max(350, int(round(base.height() * 0.70))),
    )


def fit_dialog_to_screen(
    dialog: QWidget,
    desired_w: int,
    desired_h: int,
    min_w: int,
    min_h: int,
    screen=None,
) -> None:
    screen = screen or dialog.screen() or QApplication.primaryScreen()
    if screen is None:
        dialog.resize(desired_w, desired_h)
        dialog.setMinimumSize(min_w, min_h)
        return

    area = screen.availableGeometry()
    usable_w = max(360, area.width() - 32)
    usable_h = max(320, area.height() - 32)

    width = min(desired_w, usable_w)
    height = min(desired_h, usable_h)
    minimum_w = min(min_w, usable_w)
    minimum_h = min(min_h, usable_h)

    dialog.setMinimumSize(minimum_w, minimum_h)
    dialog.resize(width, height)


def set_windows_titlebar_dark(widget: QWidget, dark: bool) -> None:
    if os.name != "nt":
        return
    try:
        hwnd = int(widget.winId())
        value = ctypes.c_int(1 if dark else 0)
        dwmapi = ctypes.windll.dwmapi
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 on current Windows 10/11.
        # 19 is retained as fallback for older Windows 10 builds.
        result = dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), 20, ctypes.byref(value), ctypes.sizeof(value)
        )
        if result != 0:
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), 19, ctypes.byref(value), ctypes.sizeof(value)
            )
    except Exception:
        pass


def current_foreground_hwnd() -> int:
    if os.name != "nt":
        return 0
    try:
        return int(ctypes.windll.user32.GetForegroundWindow())
    except Exception:
        return 0


def set_window_no_activate(widget: QWidget, enabled: bool = True) -> bool:
    """
    Toggle WS_EX_NOACTIVATE without rebuilding the native frame.

    The old implementation forced a frame refresh every time. That made the
    frameless picker visibly flash after Windows Hello / PIN closed.
    """
    if os.name != "nt":
        return False

    try:
        hwnd = int(widget.winId())
        if not hwnd:
            return False

        user32 = ctypes.windll.user32
        target = wintypes.HWND(hwnd)
        GWL_EXSTYLE = -20
        WS_EX_NOACTIVATE = 0x08000000

        get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        get_long.restype = ctypes.c_ssize_t
        set_long.restype = ctypes.c_ssize_t

        style = int(get_long(target, GWL_EXSTYLE))
        currently_enabled = bool(style & WS_EX_NOACTIVATE)
        if currently_enabled == bool(enabled):
            return True

        new_style = (
            style | WS_EX_NOACTIVATE
            if enabled
            else style & ~WS_EX_NOACTIVATE
        )
        set_long(target, GWL_EXSTYLE, new_style)

        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        user32.SetWindowPos(
            target,
            None,
            0,
            0,
            0,
            0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE,
        )
        return True
    except Exception:
        return False


def _hwnd_insert_after(value: int):
    # HWND_TOP = 0, HWND_BOTTOM = 1, HWND_TOPMOST = -1, HWND_NOTOPMOST = -2
    return ctypes.c_void_p(value)


def is_window_topmost(hwnd: int) -> bool:
    if os.name != "nt" or not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        target = wintypes.HWND(hwnd)
        if not user32.IsWindow(target):
            return False

        GWL_EXSTYLE = -20
        WS_EX_TOPMOST = 0x00000008

        get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        get_long.restype = ctypes.c_ssize_t
        style = int(get_long(target, GWL_EXSTYLE))
        return bool(style & WS_EX_TOPMOST)
    except Exception:
        return False


def foreground_hwnd() -> int:
    if os.name != "nt":
        return 0
    try:
        return int(ctypes.windll.user32.GetForegroundWindow() or 0)
    except Exception:
        return 0


def force_user_foreground(widget: QWidget) -> bool:
    """
    Foreground activation for an explicit user gesture.

    Windows can reject SetForegroundWindow even when the request came from a
    tray double-click because Explorer currently owns the foreground queue.
    First try the normal path; only if Windows refuses it, use the classic ALT
    unlock once and retry. No TOPMOST/NOTOPMOST pulse is used.
    """
    try:
        widget.show()
        widget.raise_()

        try:
            QApplication.setActiveWindow(widget)
        except Exception:
            pass

        handle = widget.windowHandle()
        if handle is not None:
            try:
                handle.requestActivate()
            except Exception:
                pass

        if os.name != "nt":
            widget.activateWindow()
            return True

        hwnd = int(widget.winId())
        if activate_window(hwnd):
            widget.activateWindow()
            return True

        user32 = ctypes.windll.user32
        target = wintypes.HWND(hwnd)

        # Foreground-lock fallback. Sending a neutral ALT press/release lets
        # Windows treat this as user-driven foreground activation.
        VK_MENU = 0x12
        KEYEVENTF_KEYUP = 0x0002
        try:
            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        except Exception:
            pass

        user32.ShowWindow(target, 5)  # SW_SHOW
        user32.BringWindowToTop(target)
        user32.SetForegroundWindow(target)
        user32.SetActiveWindow(target)
        user32.SetFocus(target)

        try:
            widget.activateWindow()
            if handle is not None:
                handle.requestActivate()
        except Exception:
            pass

        return int(user32.GetForegroundWindow() or 0) == hwnd
    except Exception:
        return False


def bring_window_top_noactivate(hwnd: int) -> bool:
    """Move a normal window to the top of its z-band without taking focus."""
    if os.name != "nt" or not hwnd:
        return False

    try:
        user32 = ctypes.windll.user32
        target = wintypes.HWND(hwnd)
        if not user32.IsWindow(target):
            return False

        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040

        user32.SetWindowPos(
            target,
            _hwnd_insert_after(0),  # HWND_TOP
            0,
            0,
            0,
            0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        return True
    except Exception:
        return False


def keep_window_topmost_noactivate(hwnd: int) -> bool:
    """Re-assert TOPMOST for the picker without activating it."""
    if os.name != "nt" or not hwnd:
        return False

    try:
        user32 = ctypes.windll.user32
        target = wintypes.HWND(hwnd)
        if not user32.IsWindow(target):
            return False

        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040

        user32.SetWindowPos(
            target,
            _hwnd_insert_after(-1),  # HWND_TOPMOST
            0,
            0,
            0,
            0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        return True
    except Exception:
        return False


def activate_window(hwnd: int) -> bool:
    """
    Strong foreground restore for Windows.

    SetForegroundWindow alone is not reliable after Windows Security / Hello:
    the shell can restore another window after the consent UI starts closing.
    AttachThreadInput + BringWindowToTop makes the foreground handoff much more
    reliable without leaving the target permanently topmost.
    """
    if os.name != "nt" or not hwnd:
        return False

    attached: list[int] = []
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        target = wintypes.HWND(hwnd)

        if not user32.IsWindow(target):
            return False

        SW_RESTORE = 9
        SW_SHOW = 5
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_SHOWWINDOW = 0x0040

        user32.ShowWindow(target, SW_RESTORE if user32.IsIconic(target) else SW_SHOW)

        current_thread = int(kernel32.GetCurrentThreadId())
        target_thread = int(user32.GetWindowThreadProcessId(target, None))

        foreground = user32.GetForegroundWindow()
        foreground_thread = (
            int(user32.GetWindowThreadProcessId(foreground, None))
            if foreground
            else 0
        )

        # Temporarily join input queues. This bypasses the common foreground
        # lock race that occurs when the Windows Security window is dismissed.
        for thread_id in {target_thread, foreground_thread}:
            if thread_id and thread_id != current_thread:
                if user32.AttachThreadInput(current_thread, thread_id, True):
                    attached.append(thread_id)

        user32.BringWindowToTop(target)
        user32.SetWindowPos(
            target,
            _hwnd_insert_after(0),  # HWND_TOP
            0,
            0,
            0,
            0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW,
        )
        user32.SetForegroundWindow(target)
        user32.SetActiveWindow(target)
        user32.SetFocus(target)

        return int(user32.GetForegroundWindow() or 0) == int(hwnd)
    except Exception:
        return False
    finally:
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            current_thread = int(kernel32.GetCurrentThreadId())
            for thread_id in reversed(attached):
                user32.AttachThreadInput(current_thread, thread_id, False)
        except Exception:
            pass



# ---------------------------------------------------------------------------
# Software password
# ---------------------------------------------------------------------------

SOFTWARE_PASSWORD_MIN_LENGTH = 6
SOFTWARE_PASSWORD_ITERATIONS = 350_000
SOFTWARE_PASSWORD_SALT_KEY = "security/softwarePasswordSalt"
SOFTWARE_PASSWORD_HASH_KEY = "security/softwarePasswordHash"
SOFTWARE_PASSWORD_ITERATIONS_KEY = "security/softwarePasswordIterations"


class SoftwarePasswordManager:
    """
    Local software-password verifier.

    Only a PBKDF2-HMAC-SHA256 verifier is stored in QSettings:
    - random 16-byte salt
    - derived 32-byte digest
    - iteration count

    The plaintext password is never stored. The password can be changed only
    after the current password is verified; there is no recovery/bypass reset.
    """

    @staticmethod
    def is_configured(settings: AppSettings) -> bool:
        salt = str(settings.qs.value(SOFTWARE_PASSWORD_SALT_KEY, "") or "")
        digest = str(settings.qs.value(SOFTWARE_PASSWORD_HASH_KEY, "") or "")
        return bool(salt and digest)

    @staticmethod
    def _derive(password: str, salt: bytes, iterations: int) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
            dklen=32,
        )

    @staticmethod
    def _write_verifier(settings: AppSettings, password: str) -> None:
        salt = secrets.token_bytes(16)
        digest = SoftwarePasswordManager._derive(
            password,
            salt,
            SOFTWARE_PASSWORD_ITERATIONS,
        )

        settings.qs.setValue(
            SOFTWARE_PASSWORD_SALT_KEY,
            base64.b64encode(salt).decode("ascii"),
        )
        settings.qs.setValue(
            SOFTWARE_PASSWORD_HASH_KEY,
            base64.b64encode(digest).decode("ascii"),
        )
        settings.qs.setValue(
            SOFTWARE_PASSWORD_ITERATIONS_KEY,
            SOFTWARE_PASSWORD_ITERATIONS,
        )
        settings.qs.sync()

    @staticmethod
    def configure(settings: AppSettings, password: str) -> None:
        if SoftwarePasswordManager.is_configured(settings):
            raise RuntimeError(
                "软件密码已经设置。如需修改，请先验证原密码。"
            )

        SoftwarePasswordManager._write_verifier(settings, password)

    @staticmethod
    def change(
        settings: AppSettings,
        old_password: str,
        new_password: str,
    ) -> bool:
        if not SoftwarePasswordManager.is_configured(settings):
            raise RuntimeError("当前尚未设置软件密码。")

        if not SoftwarePasswordManager.verify(settings, old_password):
            return False

        SoftwarePasswordManager._write_verifier(settings, new_password)
        return True

    @staticmethod
    def delete(
        settings: AppSettings,
        current_password: str,
    ) -> bool:
        """Delete the software-password verifier after proving the password."""
        if not SoftwarePasswordManager.is_configured(settings):
            return True

        if not SoftwarePasswordManager.verify(
            settings,
            current_password,
        ):
            return False

        for key in (
            SOFTWARE_PASSWORD_SALT_KEY,
            SOFTWARE_PASSWORD_HASH_KEY,
            SOFTWARE_PASSWORD_ITERATIONS_KEY,
        ):
            settings.qs.remove(key)

        settings.qs.sync()
        return True

    @staticmethod
    def verify(settings: AppSettings, password: str) -> bool:
        try:
            salt_b64 = str(
                settings.qs.value(SOFTWARE_PASSWORD_SALT_KEY, "") or ""
            )
            digest_b64 = str(
                settings.qs.value(SOFTWARE_PASSWORD_HASH_KEY, "") or ""
            )
            iterations = int(
                settings.qs.value(
                    SOFTWARE_PASSWORD_ITERATIONS_KEY,
                    SOFTWARE_PASSWORD_ITERATIONS,
                )
            )

            if not salt_b64 or not digest_b64:
                return False

            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected = base64.b64decode(digest_b64.encode("ascii"))
            actual = SoftwarePasswordManager._derive(
                password,
                salt,
                iterations,
            )
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# DPAPI for hidden phrases
# ---------------------------------------------------------------------------

if os.name == "nt":
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]


def _make_blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    blob = DATA_BLOB(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    return blob, buffer


def dpapi_encrypt(text: str) -> str:
    raw = text.encode("utf-8")
    if os.name != "nt":
        return "portable:" + base64.b64encode(raw).decode("ascii")

    in_blob, in_buffer = _make_blob(raw)
    out_blob = DATA_BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x1

    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise ctypes.WinError()

    try:
        protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return base64.b64encode(protected).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def dpapi_decrypt(value: str) -> str:
    if value.startswith("portable:"):
        raw = base64.b64decode(value[len("portable:"):])
        return raw.decode("utf-8")

    if os.name != "nt":
        raise RuntimeError("Windows DPAPI data can only be decrypted on Windows.")

    protected = base64.b64decode(value.encode("ascii"))
    in_blob, in_buffer = _make_blob(protected)
    out_blob = DATA_BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x1

    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise ctypes.WinError()

    try:
        raw = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return raw.decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Phrase:
    id: str
    name: str
    text: str
    hidden: bool = False
    protected_blob: str = field(default="", repr=False)


class PhraseStore:
    def __init__(self, path: Path = DATA_FILE):
        self.path = path
        self.phrases: list[Phrase] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.phrases = []
            return

        loaded: list[Phrase] = []
        for item in data.get("phrases", []):
            hidden = bool(item.get("hidden", False))
            text = str(item.get("text") or "")
            protected = str(item.get("text_protected") or "")

            if hidden and protected:
                try:
                    text = dpapi_decrypt(protected)
                except Exception:
                    # Preserve ciphertext if decryption failed. Never overwrite it.
                    text = ""

            loaded.append(
                Phrase(
                    id=str(item.get("id") or uuid.uuid4()),
                    name=str(item.get("name") or ""),
                    text=text,
                    hidden=hidden,
                    protected_blob=protected,
                )
            )
        self.phrases = loaded

    def _record(self, phrase: Phrase) -> dict:
        record = {
            "id": phrase.id,
            "name": phrase.name,
            "hidden": phrase.hidden,
        }

        if phrase.hidden:
            # Existing hidden phrases keep their already encrypted DPAPI blob.
            # A new/edited hidden phrase has no protected_blob and is encrypted once.
            if phrase.protected_blob:
                protected = phrase.protected_blob
            else:
                protected = dpapi_encrypt(phrase.text)
            record["text_protected"] = protected
        else:
            record["text"] = phrase.text

        return record

    def save(self) -> None:
        payload = {
            "version": 2,
            "phrases": [self._record(x) for x in self.phrases],
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, phrase: Phrase) -> None:
        self.phrases.append(phrase)
        self.save()

    def update(self, phrase: Phrase) -> None:
        for index, current in enumerate(self.phrases):
            if current.id == phrase.id:
                self.phrases[index] = phrase
                self.save()
                return

    def delete(self, phrase_id: str) -> None:
        self.phrases = [x for x in self.phrases if x.id != phrase_id]
        self.save()

    def reorder(self, ordered_ids: list[str]) -> bool:
        """Persist a full phrase order without altering phrase contents."""
        if len(ordered_ids) != len(self.phrases):
            return False

        current = {phrase.id: phrase for phrase in self.phrases}
        if set(ordered_ids) != set(current):
            return False

        reordered = [current[phrase_id] for phrase_id in ordered_ids]
        if [x.id for x in reordered] == [x.id for x in self.phrases]:
            return True

        self.phrases = reordered
        self.save()
        return True

    def by_id(self, phrase_id: str) -> Phrase | None:
        return next((x for x in self.phrases if x.id == phrase_id), None)


# ---------------------------------------------------------------------------
# Windows Hello / Windows Security verification
# ---------------------------------------------------------------------------

if os.name == "nt":
    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        ]

        @classmethod
        def from_string(cls, value: str) -> "GUID":
            import uuid as _uuid
            return cls.from_buffer_copy(_uuid.UUID(value).bytes_le)


class WindowsHelloVerifier:
    """
    Native desktop Windows Hello verification.

    For a Win32 desktop app Microsoft requires IUserConsentVerifierInterop
    instead of the UWP-only RequestVerificationAsync static call. This
    implementation calls the native COM/WinRT ABI directly via ctypes, passing
    the PySide6 HWND as the owner of the Windows Security prompt.

    UserConsentVerificationResult:
        0 Verified
        1 DeviceNotPresent
        2 NotConfiguredForUser
        3 DisabledByPolicy
        4 DeviceBusy
        5 RetriesExhausted
        6 Canceled
    """

    CLASS_NAME = "Windows.Security.Credentials.UI.UserConsentVerifier"
    IID_INTEROP_TEXT = "39E050C3-4E74-441A-8DC0-B81104DF949C"
    IID_STATICS_TEXT = "AF4F3F91-564C-4DDC-B8B5-973447627C65"
    IID_ASYNC_RESULT_TEXT = "FD596FFD-2318-558F-9DBE-D21DF43764A5"
    IID_ASYNC_INFO_TEXT = "00000036-0000-0000-C000-000000000046"

    @staticmethod
    def _hr_failed(hr: int) -> bool:
        return int(hr) < 0

    @staticmethod
    def _hr_hex(hr: int) -> str:
        return f"0x{(int(hr) & 0xFFFFFFFF):08X}"

    @staticmethod
    def _method(ptr, index: int, restype, *argtypes):
        vtable = ctypes.cast(
            ptr,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
        ).contents
        address = vtable[index]
        prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
        return prototype(address)

    @staticmethod
    def _release(ptr) -> None:
        if not ptr:
            return
        try:
            release = WindowsHelloVerifier._method(
                ptr, 2, ctypes.c_ulong
            )
            release(ptr)
        except Exception:
            pass

    @staticmethod
    def _create_hstring(text: str):
        combase = ctypes.windll.combase
        handle = ctypes.c_void_p()
        # WindowsCreateString length is UTF-16 code units.
        length = len(text.encode("utf-16-le")) // 2
        hr = combase.WindowsCreateString(
            ctypes.c_wchar_p(text),
            ctypes.c_uint32(length),
            ctypes.byref(handle),
        )
        if WindowsHelloVerifier._hr_failed(hr):
            raise OSError(
                f"WindowsCreateString 失败："
                f"{WindowsHelloVerifier._hr_hex(hr)}"
            )
        return handle

    @staticmethod
    def _delete_hstring(handle) -> None:
        if handle:
            try:
                ctypes.windll.combase.WindowsDeleteString(handle)
            except Exception:
                pass

    @staticmethod
    def check_availability(
        timeout_seconds: float = 6.0,
    ) -> tuple[bool, int, str]:
        """
        Return (selectable, availability_code, message).

        Availability values:
            0 Available
            1 DeviceNotPresent
            2 NotConfiguredForUser
            3 DisabledByPolicy
            4 DeviceBusy

        DeviceBusy still means a verifier exists/configured, so the PIN option
        remains selectable; an actual verification attempt can ask the user to
        retry later.
        """
        if os.name != "nt":
            return False, -1, "Windows PIN / Hello 仅支持 Windows。"

        try:
            if sys.getwindowsversion().build < 22000:
                return (
                    False,
                    -2,
                    "当前系统版本不支持 QuickPhrase 使用的桌面 Windows Hello "
                    "验证接口，请使用软件密码。",
                )
        except Exception:
            pass

        combase = ctypes.windll.combase

        combase.RoInitialize.argtypes = [ctypes.c_uint32]
        combase.RoInitialize.restype = ctypes.c_long
        combase.RoUninitialize.argtypes = []
        combase.RoUninitialize.restype = None
        combase.WindowsCreateString.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        combase.WindowsCreateString.restype = ctypes.c_long
        combase.WindowsDeleteString.argtypes = [ctypes.c_void_p]
        combase.WindowsDeleteString.restype = ctypes.c_long
        combase.RoGetActivationFactory.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(GUID),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        combase.RoGetActivationFactory.restype = ctypes.c_long

        init_hr = combase.RoInitialize(0)
        RPC_E_CHANGED_MODE = 0x80010106
        should_uninit = (
            (int(init_hr) & 0xFFFFFFFF)
            in (0x00000000, 0x00000001)
        )

        if (
            WindowsHelloVerifier._hr_failed(init_hr)
            and (int(init_hr) & 0xFFFFFFFF) != RPC_E_CHANGED_MODE
        ):
            return (
                False,
                -3,
                "Windows Runtime 初始化失败："
                + WindowsHelloVerifier._hr_hex(init_hr),
            )

        class_hstring = None
        factory = ctypes.c_void_p()
        async_op = ctypes.c_void_p()
        async_info = ctypes.c_void_p()

        try:
            class_hstring = WindowsHelloVerifier._create_hstring(
                WindowsHelloVerifier.CLASS_NAME
            )

            iid_statics = GUID.from_string(
                WindowsHelloVerifier.IID_STATICS_TEXT
            )
            iid_async_info = GUID.from_string(
                WindowsHelloVerifier.IID_ASYNC_INFO_TEXT
            )

            hr = combase.RoGetActivationFactory(
                class_hstring,
                ctypes.byref(iid_statics),
                ctypes.byref(factory),
            )
            if WindowsHelloVerifier._hr_failed(hr) or not factory:
                return (
                    False,
                    -4,
                    "无法读取 Windows PIN / Hello 可用状态："
                    + WindowsHelloVerifier._hr_hex(hr),
                )

            # IUserConsentVerifierStatics::CheckAvailabilityAsync
            # IUnknown(3) + IInspectable(3) => method index 6.
            check = WindowsHelloVerifier._method(
                factory,
                6,
                ctypes.c_long,
                ctypes.POINTER(ctypes.c_void_p),
            )

            hr = check(factory, ctypes.byref(async_op))
            if WindowsHelloVerifier._hr_failed(hr) or not async_op:
                return (
                    False,
                    -5,
                    "Windows PIN / Hello 可用性检查启动失败："
                    + WindowsHelloVerifier._hr_hex(hr),
                )

            query_interface = WindowsHelloVerifier._method(
                async_op,
                0,
                ctypes.c_long,
                ctypes.POINTER(GUID),
                ctypes.POINTER(ctypes.c_void_p),
            )
            hr = query_interface(
                async_op,
                ctypes.byref(iid_async_info),
                ctypes.byref(async_info),
            )
            if WindowsHelloVerifier._hr_failed(hr) or not async_info:
                return (
                    False,
                    -6,
                    "无法读取 Windows PIN / Hello 检查状态："
                    + WindowsHelloVerifier._hr_hex(hr),
                )

            get_status = WindowsHelloVerifier._method(
                async_info,
                7,
                ctypes.c_long,
                ctypes.POINTER(ctypes.c_int),
            )

            deadline = time.monotonic() + max(1.0, timeout_seconds)
            status = ctypes.c_int(0)

            while time.monotonic() < deadline:
                hr = get_status(async_info, ctypes.byref(status))
                if WindowsHelloVerifier._hr_failed(hr):
                    return (
                        False,
                        -7,
                        "读取 Windows PIN / Hello 检查状态失败："
                        + WindowsHelloVerifier._hr_hex(hr),
                    )

                if status.value != 0:
                    break

                app = QApplication.instance()
                if app:
                    app.processEvents()
                time.sleep(0.02)

            if status.value == 0:
                return False, -8, "Windows PIN / Hello 可用性检查超时。"
            if status.value == 2:
                return False, -9, "Windows PIN / Hello 可用性检查已取消。"
            if status.value == 3:
                return False, -10, "Windows PIN / Hello 可用性检查发生系统错误。"

            # IAsyncOperation<UserConsentVerifierAvailability>::GetResults
            get_results = WindowsHelloVerifier._method(
                async_op,
                8,
                ctypes.c_long,
                ctypes.POINTER(ctypes.c_int),
            )

            availability = ctypes.c_int(-1)
            hr = get_results(async_op, ctypes.byref(availability))
            if WindowsHelloVerifier._hr_failed(hr):
                return (
                    False,
                    -11,
                    "获取 Windows PIN / Hello 可用性结果失败："
                    + WindowsHelloVerifier._hr_hex(hr),
                )

            messages = {
                0: "Windows PIN / Hello 可用。",
                1: "未检测到 Windows PIN / Hello 安全设备。",
                2: "当前用户尚未配置 Windows PIN / Hello。",
                3: "Windows PIN / Hello 已被系统策略禁用。",
                4: "Windows PIN / Hello 已配置，但当前设备正忙。",
            }

            # DeviceBusy means the security method exists, just temporarily
            # unavailable for an immediate authentication.
            selectable = availability.value in (0, 4)
            return (
                selectable,
                availability.value,
                messages.get(
                    availability.value,
                    f"Windows PIN / Hello 状态未知（{availability.value}）。",
                ),
            )

        except Exception as exc:
            return False, -12, f"Windows PIN / Hello 可用性检查失败：{exc}"
        finally:
            WindowsHelloVerifier._release(async_info)
            WindowsHelloVerifier._release(async_op)
            WindowsHelloVerifier._release(factory)
            WindowsHelloVerifier._delete_hstring(class_hstring)
            if should_uninit:
                try:
                    combase.RoUninitialize()
                except Exception:
                    pass

    @staticmethod
    def verify(
        owner_hwnd: int,
        reason: str = "QuickPhrase：验证身份以使用隐藏常用语",
    ) -> tuple[bool, str]:
        if os.name != "nt":
            return False, "Windows 安全验证仅支持 Windows。"

        try:
            if sys.getwindowsversion().build < 22000:
                return (
                    False,
                    "当前系统版本不支持 QuickPhrase 使用的桌面 Windows Hello "
                    "Interop。隐藏常用语安全验证需要 Windows 11（Build 22000+）。",
                )
        except Exception:
            pass

        if not owner_hwnd:
            return False, "无法取得当前 QuickPhrase 窗口句柄，安全验证未启动。"

        combase = ctypes.windll.combase

        # Explicit signatures make pointer width correct on 64-bit Windows.
        combase.RoInitialize.argtypes = [ctypes.c_uint32]
        combase.RoInitialize.restype = ctypes.c_long
        combase.RoUninitialize.argtypes = []
        combase.RoUninitialize.restype = None

        combase.WindowsCreateString.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        combase.WindowsCreateString.restype = ctypes.c_long
        combase.WindowsDeleteString.argtypes = [ctypes.c_void_p]
        combase.WindowsDeleteString.restype = ctypes.c_long
        combase.RoGetActivationFactory.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(GUID),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        combase.RoGetActivationFactory.restype = ctypes.c_long

        # RO_INIT_SINGLETHREADED keeps this aligned with the Qt GUI thread.
        init_hr = combase.RoInitialize(0)
        # RPC_E_CHANGED_MODE is acceptable: COM was already initialized with
        # another apartment model by the host application.
        RPC_E_CHANGED_MODE = 0x80010106
        should_uninit = (int(init_hr) & 0xFFFFFFFF) in (0x00000000, 0x00000001)
        if (
            WindowsHelloVerifier._hr_failed(init_hr)
            and (int(init_hr) & 0xFFFFFFFF) != RPC_E_CHANGED_MODE
        ):
            return (
                False,
                "Windows Runtime 初始化失败："
                + WindowsHelloVerifier._hr_hex(init_hr),
            )

        class_hstring = None
        message_hstring = None
        factory = ctypes.c_void_p()
        async_op = ctypes.c_void_p()
        async_info = ctypes.c_void_p()

        try:
            class_hstring = WindowsHelloVerifier._create_hstring(
                WindowsHelloVerifier.CLASS_NAME
            )
            message_hstring = WindowsHelloVerifier._create_hstring(reason)

            iid_interop = GUID.from_string(
                WindowsHelloVerifier.IID_INTEROP_TEXT
            )
            iid_async = GUID.from_string(
                WindowsHelloVerifier.IID_ASYNC_RESULT_TEXT
            )
            iid_async_info = GUID.from_string(
                WindowsHelloVerifier.IID_ASYNC_INFO_TEXT
            )

            hr = combase.RoGetActivationFactory(
                class_hstring,
                ctypes.byref(iid_interop),
                ctypes.byref(factory),
            )
            if WindowsHelloVerifier._hr_failed(hr):
                return (
                    False,
                    "无法加载 Windows Hello 桌面验证接口："
                    + WindowsHelloVerifier._hr_hex(hr),
                )

            # Windows Hello's desktop interop is most reliable when the owner
            # HWND is already foreground at the instant the request is created.
            # The picker temporarily opts out of WS_EX_NOACTIVATE before this
            # point, so this call does not permanently steal focus.
            try:
                if foreground_hwnd() != int(owner_hwnd):
                    activate_window(int(owner_hwnd))
                QApplication.processEvents()
            except Exception:
                pass

            # IUserConsentVerifierInterop::RequestVerificationForWindowAsync
            # IUnknown(3) + IInspectable(3) => method index 6.
            request = WindowsHelloVerifier._method(
                factory,
                6,
                ctypes.c_long,
                wintypes.HWND,
                ctypes.c_void_p,          # HSTRING
                ctypes.POINTER(GUID),     # REFIID
                ctypes.POINTER(ctypes.c_void_p),
            )

            hr = request(
                factory,
                wintypes.HWND(owner_hwnd),
                message_hstring,
                ctypes.byref(iid_async),
                ctypes.byref(async_op),
            )
            if WindowsHelloVerifier._hr_failed(hr) or not async_op:
                return (
                    False,
                    "Windows 安全验证请求启动失败："
                    + WindowsHelloVerifier._hr_hex(hr),
                )

            # Query IAsyncInfo so we can poll AsyncStatus without constructing
            # a Python COM callback object.
            query_interface = WindowsHelloVerifier._method(
                async_op,
                0,
                ctypes.c_long,
                ctypes.POINTER(GUID),
                ctypes.POINTER(ctypes.c_void_p),
            )
            hr = query_interface(
                async_op,
                ctypes.byref(iid_async_info),
                ctypes.byref(async_info),
            )
            if WindowsHelloVerifier._hr_failed(hr) or not async_info:
                return (
                    False,
                    "无法读取 Windows 安全验证状态："
                    + WindowsHelloVerifier._hr_hex(hr),
                )

            # IAsyncInfo: IInspectable methods 0..5, Id=6, Status=7.
            get_status = WindowsHelloVerifier._method(
                async_info,
                7,
                ctypes.c_long,
                ctypes.POINTER(ctypes.c_int),
            )

            deadline = time.monotonic() + 120.0
            status = ctypes.c_int(0)  # Started

            while time.monotonic() < deadline:
                hr = get_status(async_info, ctypes.byref(status))
                if WindowsHelloVerifier._hr_failed(hr):
                    return (
                        False,
                        "读取 Windows 安全验证状态失败："
                        + WindowsHelloVerifier._hr_hex(hr),
                    )

                if status.value != 0:
                    break

                # Keep the PySide UI responsive while Windows Security owns
                # the foreground verification dialog.
                app = QApplication.instance()
                if app:
                    app.processEvents()
                time.sleep(0.03)

            if status.value == 0:
                return False, "Windows 安全验证等待超时。"
            if status.value == 2:
                return False, "已取消 Windows 安全验证。"
            if status.value == 3:
                return False, "Windows 安全验证返回系统错误。"

            # IAsyncOperation<T>: put_Completed=6, get_Completed=7,
            # GetResults=8.
            get_results = WindowsHelloVerifier._method(
                async_op,
                8,
                ctypes.c_long,
                ctypes.POINTER(ctypes.c_int),
            )
            result = ctypes.c_int(-1)
            hr = get_results(async_op, ctypes.byref(result))
            if WindowsHelloVerifier._hr_failed(hr):
                return (
                    False,
                    "获取 Windows 安全验证结果失败："
                    + WindowsHelloVerifier._hr_hex(hr),
                )

            messages = {
                0: "",
                1: "没有可用的 Windows Hello 身份验证设备。",
                2: "当前用户尚未配置 Windows Hello。请先在“设置 → 账户 → 登录选项”中配置 PIN。",
                3: "Windows Hello 已被系统策略禁用。",
                4: "Windows Hello 当前正忙，请稍后重试。",
                5: "验证失败次数过多，请稍后再试。",
                6: "已取消 Windows 安全验证。",
            }

            if result.value == 0:
                return True, ""
            return False, messages.get(
                result.value,
                f"Windows 安全验证未通过（结果 {result.value}）。",
            )

        except Exception as exc:
            return False, f"Windows 安全验证调用失败：{exc}"
        finally:
            WindowsHelloVerifier._release(async_info)
            WindowsHelloVerifier._release(async_op)
            WindowsHelloVerifier._release(factory)
            WindowsHelloVerifier._delete_hstring(message_hstring)
            WindowsHelloVerifier._delete_hstring(class_hstring)
            if should_uninit:
                try:
                    combase.RoUninitialize()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

def blend(foreground: QColor, background: QColor, amount: float) -> QColor:
    amount = max(0.0, min(1.0, amount))
    r = round(background.red() * (1 - amount) + foreground.red() * amount)
    g = round(background.green() * (1 - amount) + foreground.green() * amount)
    b = round(background.blue() * (1 - amount) + foreground.blue() * amount)
    return QColor(r, g, b)


def color_hex(color: QColor) -> str:
    return color.name(QColor.HexRgb)


def theme_tokens(dark: bool, accent: QColor) -> dict[str, str]:
    if dark:
        base = {
            "page": "#202020",
            "sidebar": "#242424",
            "card": "#2B2B2B",
            "card_hover": "#303030",
            "control": "#303030",
            "control_hover": "#363636",
            "text": "#FFFFFF",
            "muted": "#C7C7C7",
            "disabled": "#777777",
            "border": "#454545",
            "separator": "#3D3D3D",
            "track": "#4A4A4A",
        }
        selected = blend(accent, QColor(base["card"]), 0.18)
    else:
        base = {
            "page": "#F3F3F3",
            "sidebar": "#EEF1F6",
            "card": "#FBFBFB",
            "card_hover": "#F6F6F6",
            "control": "#FFFFFF",
            "control_hover": "#F9F9F9",
            "text": "#1A1A1A",
            "muted": "#5D5D5D",
            "disabled": "#9A9A9A",
            "border": "#D7D7D7",
            "separator": "#E5E5E5",
            "track": "#D5D5D5",
        }
        selected = blend(accent, QColor(base["card"]), 0.10)

    base["accent"] = color_hex(accent)
    # Selected phrase text should stay visually strong and neutral:
    # light theme -> black, dark theme -> white.
    base["selected_text"] = "#FFFFFF" if dark else "#000000"
    base["accent_hover"] = color_hex(
        blend(QColor("#FFFFFF") if dark else QColor("#000000"), accent, 0.08)
    )
    base["accent_pressed"] = color_hex(
        blend(QColor("#FFFFFF") if dark else QColor("#000000"), accent, 0.16)
    )
    base["selected"] = color_hex(selected)
    return base


def build_stylesheet(t: dict[str, str]) -> str:
    return f"""
    * {{
        font-family: "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI";
        font-size: 10.5pt;
        color: {t["text"]};
    }}

    QMainWindow, QDialog, QWidget#pageRoot {{
        background: {t["page"]};
    }}

    QMenuBar#mainMenuBar {{
        background: {t["page"]};
        border: 0;
        border-bottom: 1px solid {t["separator"]};
        padding: 2px 6px;
        spacing: 1px;
    }}

    QMenuBar#mainMenuBar::item {{
        background: transparent;
        border: 0;
        border-radius: 4px;
        padding: 5px 10px;
        margin: 1px 0;
    }}

    QMenuBar#mainMenuBar::item:selected,
    QMenuBar#mainMenuBar::item:pressed {{
        background: {t["card_hover"]};
    }}

    QMenu {{
        background: {t["card"]};
        border: 1px solid {t["border"]};
        padding: 6px;
    }}

    QMenu::item {{
        padding: 7px 26px 7px 12px;
        border-radius: 5px;
    }}

    QMenu::item:selected {{
        background: {t["card_hover"]};
        color: {t["accent"]};
    }}

    QLabel#pageTitle {{
        font-size: 18pt;
        font-weight: 600;
    }}

    QLabel#dialogTitle {{
        font-size: 15.75pt;
        font-weight: 600;
    }}

    QLabel#sectionTitle {{
        font-size: 12.75pt;
        font-weight: 600;
    }}

    QLabel#rowTitle {{
        font-size: 10.5pt;
        font-weight: 600;
    }}

    QLabel#mutedLabel,
    QLabel#phrasePreview,
    QLabel#tinyLabel {{
        font-size: 9pt;
        color: {t["muted"]};
    }}

    QLabel#phraseTitle {{
        font-size: 10.5pt;
        font-weight: 600;
    }}

    QFrame#sidebar {{
        background: {t["sidebar"]};
        border: 0;
        border-right: 1px solid {t["separator"]};
    }}

    QFrame#settingsCard,
    QFrame#compactCard {{
        background: {t["card"]};
        border: 1px solid {t["border"]};
        border-radius: 8px;
    }}

    QFrame#pickerShell {{
        background: {t["card"]};
        border: 0;
        border-radius: 0;
    }}

    QFrame#settingsRow,
    QFrame#settingsRowLast {{
        background: transparent;
        border: 0;
    }}

    QFrame#settingsRow:hover,
    QFrame#settingsRowLast:hover {{
        background: {t["card_hover"]};
    }}

    QFrame#separator {{
        background: {t["separator"]};
        border: 0;
        min-height: 1px;
        max-height: 1px;
    }}

    QLineEdit, QTextEdit, QKeySequenceEdit {{
        background: {t["control"]};
        border: 1px solid {t["border"]};
        border-radius: 6px;
        padding: 7px 10px;
        selection-background-color: {t["accent"]};
    }}

    QLineEdit, QKeySequenceEdit {{
        min-height: 20px;
    }}

    QLineEdit:hover, QTextEdit:hover, QKeySequenceEdit:hover {{
        background: {t["control_hover"]};
    }}

    QLineEdit:focus, QTextEdit:focus, QKeySequenceEdit:focus {{
        border: 1px solid {t["accent"]};
    }}

    QPushButton {{
        min-height: 34px;
        padding: 0 14px;
        background: {t["control"]};
        border: 1px solid {t["border"]};
        border-radius: 6px;
        font-weight: 400;
    }}

    QPushButton:hover {{
        background: {t["control_hover"]};
    }}

    QPushButton:pressed {{
        background: {t["card_hover"]};
    }}

    QPushButton:disabled {{
        color: {t["disabled"]};
        background: {t["card"]};
        border-color: {t["border"]};
    }}

    QPushButton#primaryButton {{
        background: {t["accent"]};
        color: white;
        border-color: {t["accent"]};
        font-weight: 600;
    }}

    QPushButton#primaryButton:hover {{
        background: {t["accent_hover"]};
        border-color: {t["accent_hover"]};
    }}

    QPushButton#primaryButton:pressed {{
        background: {t["accent_pressed"]};
        border-color: {t["accent_pressed"]};
    }}

    QPushButton#primaryButton:disabled {{
        color: {t["disabled"]};
        background: {t["card"]};
        border-color: {t["border"]};
        font-weight: 400;
    }}

    QPushButton#dangerButton {{
        min-height: 32px;
        padding: 0 12px;
        border: 1px solid {t["border"]};
        border-radius: 6px;
        background: {t["control"]};
        color: {t["text"]};
        font-weight: 500;
    }}

    QPushButton#dangerButton:hover {{
        border-color: #C42B1C;
        color: #C42B1C;
        background: {t["card_hover"]};
    }}

    QPushButton#dangerButton:pressed {{
        border-color: #A4262C;
        color: #A4262C;
    }}

    QPushButton#flatButton {{
        background: transparent;
        border: 1px solid transparent;
        color: {t["accent"]};
    }}

    QPushButton#flatButton:hover {{
        background: {t["selected"]};
    }}

    QPushButton#iconButton {{
        min-width: 34px;
        max-width: 34px;
        min-height: 34px;
        max-height: 34px;
        padding: 0;
        border: 1px solid transparent;
        background: transparent;
        color: {t["accent"]};
        font-family: "Segoe Fluent Icons", "Segoe UI Symbol", "Segoe UI";
        font-size: 11pt;
    }}

    QPushButton#iconButton:hover {{
        background: {t["selected"]};
        border-color: {t["border"]};
    }}

    QPushButton#iconButton[editMode="true"] {{
        background: {t["selected"]};
        border-color: {t["accent"]};
        color: {t["accent"]};
        font-weight: 600;
    }}

    QLabel#reorderHandle {{
        color: {t["muted"]};
        font-family: "Segoe UI Symbol", "Segoe UI";
        font-size: 13pt;
        font-weight: 600;
    }}

    QWidget#phraseRow[selected="true"] QLabel#reorderHandle {{
        color: {t["accent"]};
    }}

    QPushButton#navButton {{
        text-align: left;
        padding: 0 14px;
        min-height: 42px;
        border: 1px solid transparent;
        background: transparent;
        border-radius: 6px;
    }}

    QPushButton#navButton:hover {{
        background: {t["card_hover"]};
    }}

    QPushButton#navButton:checked {{
        background: {t["card"]};
        border-color: {t["border"]};
        font-weight: 600;
        color: {t["accent"]};
    }}

    QPushButton#segmentButton {{
        min-height: 34px;
        padding: 0 14px;
        border-radius: 6px;
        background: {t["control"]};
        border: 1px solid {t["border"]};
    }}

    QPushButton#segmentButton:checked {{
        background: {t["selected"]};
        border-color: {t["accent"]};
        color: {t["accent"]};
        font-weight: 600;
    }}

    QListWidget#phraseList,
    QListWidget#pickerList {{
        background: transparent;
        border: 0;
        outline: none;
    }}

    QListWidget#phraseList::item {{
        background: {t["card"]};
        border: 1px solid {t["border"]};
        border-radius: 8px;
        margin: 0;
    }}

    QListWidget#phraseList::item:hover {{
        background: {t["card_hover"]};
    }}

    QListWidget#phraseList::item:selected {{
        background: {t["selected"]};
        border-color: {t["accent"]};
        color: {t["selected_text"]};
        font-weight: 600;
    }}

    QWidget#phraseRow {{
        background: transparent;
        border: 0;
    }}

    QWidget#phraseRow[selected="true"] QLabel#phraseTitle,
    QWidget#phraseRow[selected="true"] QLabel#phrasePreview {{
        color: {t["selected_text"]};
        font-weight: 600;
    }}

    QListWidget#pickerList::item {{
        background: {t["card"]};
        border: 1px solid {t["border"]};
        border-radius: 7px;
        padding: 4px 8px;
    }}

    QListWidget#pickerList::item:hover {{
        background: {t["card_hover"]};
    }}

    QListWidget#pickerList::item:selected {{
        background: {t["selected"]};
        border-color: {t["accent"]};
        color: {t["accent"]};
        font-weight: 600;
    }}

    QScrollArea {{
        background: transparent;
        border: 0;
    }}

    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}

    QScrollBar::handle:vertical {{
        background: {t["border"]};
        min-height: 30px;
        border-radius: 4px;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QToolTip {{
        background: {t["card"]};
        color: {t["text"]};
        border: 1px solid {t["border"]};
        padding: 5px 7px;
    }}
    """


class ThemeManager(QObject):
    theme_changed = Signal(bool, QColor)

    def __init__(self, settings: AppSettings):
        super().__init__()
        self.settings = settings
        self.dark = False
        self.accent = windows_accent_color()
        self.tokens: dict[str, str] = {}

    def resolve_dark(self, mode: str | None = None) -> bool:
        mode = mode or self.settings.theme_mode
        if mode == "dark":
            return True
        if mode == "light":
            return False
        return not windows_apps_use_light_theme()

    def apply(self, mode: str | None = None) -> None:
        mode = mode or self.settings.theme_mode
        self.dark = self.resolve_dark(mode)
        self.accent = windows_accent_color()
        self.tokens = theme_tokens(self.dark, self.accent)

        app = QApplication.instance()
        if app is None:
            return

        app.setProperty("qpAccent", self.tokens["accent"])
        app.setProperty("qpDark", self.dark)
        app.setStyleSheet(build_stylesheet(self.tokens))

        # QApplication.setStyleSheet() already propagates the new QSS.
        # Avoid manually unpolish/polish-ing every window: that causes a visible
        # redraw hitch on lower-power systems and when many widgets exist.
        for widget in app.topLevelWidgets():
            widget.update()
            QTimer.singleShot(
                0,
                lambda w=widget, d=self.dark: set_windows_titlebar_dark(w, d),
            )

        self.theme_changed.emit(self.dark, self.accent)


# ---------------------------------------------------------------------------
# Custom Fluent controls
# ---------------------------------------------------------------------------

class AccentCheckBox(QCheckBox):
    """Windows-like checkbox with transparent indicator and Accent check mark."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(28)

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        return QSize(max(base.width(), 90), max(base.height(), 28))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        app = QApplication.instance()
        accent = QColor(str(app.property("qpAccent") or "#0067C0"))
        dark = bool(app.property("qpDark"))
        text_color = QColor("#FFFFFF" if dark else "#1A1A1A")
        border = QColor("#747474" if dark else "#8A8A8A")

        indicator = QRect(2, (self.height() - 16) // 2, 16, 16)

        painter.setPen(QPen(border, 1.1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(indicator, 3, 3)

        if self.isChecked():
            pen = QPen(accent, 2.0)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)

            x = indicator.left()
            y = indicator.top()
            painter.drawLine(x + 4, y + 8, x + 7, y + 11)
            painter.drawLine(x + 7, y + 11, x + 13, y + 5)

        painter.setPen(text_color if self.isEnabled() else QColor("#888888"))
        text_rect = self.rect().adjusted(25, 0, 0, 0)
        painter.drawText(
            text_rect,
            Qt.AlignVCenter | Qt.AlignLeft,
            self.text(),
        )


class FluentSwitch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(46, 32)

        self._offset = 4.0
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(170)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, value: float) -> None:
        self._offset = float(value)
        self.update()

    offset = Property(float, get_offset, set_offset)

    def _positions(self) -> tuple[float, float]:
        return 5.0, 25.0

    def _animate(self, checked: bool) -> None:
        left, right = self._positions()
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(right if checked else left)
        self._animation.start()

    def showEvent(self, event) -> None:
        left, right = self._positions()
        self._offset = right if self.isChecked() else left
        super().showEvent(event)

    def paintEvent(self, event) -> None:
        app = QApplication.instance()
        accent = QColor(
            str(app.property("qpAccent") or "#0067C0")
        )
        dark = bool(app.property("qpDark"))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        track = self.rect().adjusted(3, 6, -3, -6)
        track_color = accent if self.isChecked() else (
            QColor("#5B5B5B") if dark else QColor("#B7B7B7")
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 10, 10)

        thumb_color = QColor("#FFFFFF") if self.isChecked() else (
            QColor("#EAEAEA") if dark else QColor("#FFFFFF")
        )
        painter.setBrush(thumb_color)
        painter.drawEllipse(
            int(self._offset),
            9,
            14,
            14,
        )


class NavigationButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("navButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.isChecked():
            return

        app = QApplication.instance()
        accent = QColor(str(app.property("qpAccent") or "#0067C0"))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent)
        y = (self.height() - 20) / 2
        painter.drawRoundedRect(1.0, y, 3.0, 20.0, 1.5, 1.5)


class SegmentedChoice(QWidget):
    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for key, label in options:
            button = QPushButton(label)
            button.setObjectName("segmentButton")
            button.setCheckable(True)
            button.setProperty("choiceKey", key)
            button.clicked.connect(
                lambda checked=False, k=key: self.changed.emit(k)
            )
            self.group.addButton(button)
            self.buttons[key] = button
            layout.addWidget(button)

    def set_value(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)

    def value(self) -> str:
        checked = self.group.checkedButton()
        if not checked:
            return ""
        return str(checked.property("choiceKey"))


class SettingsCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsCard")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._rows: list[QFrame] = []

    def add_row(
        self,
        title: str,
        description: str,
        control: QWidget,
        min_height: int = 64,
    ) -> None:
        if self._rows:
            sep_wrap = QWidget()
            sep_layout = QHBoxLayout(sep_wrap)
            sep_layout.setContentsMargins(18, 0, 16, 0)
            sep = QFrame()
            sep.setObjectName("separator")
            sep_layout.addWidget(sep)
            self._layout.addWidget(sep_wrap)

        row = QFrame()
        row.setObjectName("settingsRowLast")
        row.setMinimumHeight(min_height)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(18, 8, 16, 8)
        layout.setSpacing(14)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("rowTitle")
        desc_label = QLabel(description)
        desc_label.setObjectName("mutedLabel")
        desc_label.setWordWrap(True)

        text_box.addWidget(title_label)
        text_box.addWidget(desc_label)
        layout.addLayout(text_box, 1)
        layout.addWidget(control, 0, Qt.AlignVCenter)

        self._rows.append(row)
        self._layout.addWidget(row)


class DragArea(QWidget):
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            window = self.window()
            handle = window.windowHandle()
            if handle:
                begin_drag = getattr(window, "_begin_user_drag", None)
                if callable(begin_drag):
                    begin_drag()

                if handle.startSystemMove():
                    event.accept()
                    return

                cancel_drag = getattr(window, "_cancel_user_drag", None)
                if callable(cancel_drag):
                    cancel_drag()

        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Hotkey
# ---------------------------------------------------------------------------

class HotkeyBridge(QObject):
    triggered = Signal()


class GlobalHotkey:
    def __init__(self, callback: Callable[[], None]):
        self.callback = callback
        self._handle = None

    @staticmethod
    def normalize(sequence: str) -> str:
        parts = [p.strip().lower() for p in sequence.split("+") if p.strip()]
        replacements = {
            "control": "ctrl",
            "meta": "windows",
            "win": "windows",
        }
        return "+".join(replacements.get(x, x) for x in parts)

    def register(self, sequence: str) -> tuple[bool, str]:
        self.unregister()
        if not sequence.strip():
            return False, "快捷键不能为空。"

        try:
            self._handle = keyboard.add_hotkey(
                self.normalize(sequence),
                self.callback,
                suppress=False,
                trigger_on_release=False,
            )
            return True, ""
        except Exception as exc:
            self._handle = None
            return False, f"快捷键注册失败：{exc}"

    def unregister(self) -> None:
        if self._handle is not None:
            try:
                keyboard.remove_hotkey(self._handle)
            except Exception:
                pass
            self._handle = None


# ---------------------------------------------------------------------------
# Software-password dialogs / hidden-content security resolver
# ---------------------------------------------------------------------------

class SoftwarePasswordSetupDialog(QDialog):
    def __init__(
        self,
        settings: AppSettings,
        theme: ThemeManager,
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.theme = theme

        self.setWindowTitle("设置软件密码")
        fit_dialog_to_screen(self, 520, 350, 440, 320)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        title = QLabel("设置软件密码")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        desc = QLabel(
            "当前设备无法使用 Windows PIN / Hello，或你选择了软件密码。"
            "软件密码用于保护隐藏常用语。"
        )
        desc.setObjectName("mutedLabel")
        desc.setWordWrap(True)
        root.addWidget(desc)

        warning = QLabel(
            "重要：软件密码可以修改，但修改时必须提供原密码。"
            "软件密码无法找回；忘记原密码后只能卸载 QuickPhrase，"
            "卸载会永久删除全部常用语、隐藏内容和软件设置。"
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("font-weight:600;")
        root.addWidget(warning)

        card = QFrame()
        card.setObjectName("settingsCard")
        form = QFormLayout(card)
        form.setContentsMargins(18, 16, 18, 16)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText(
            f"至少 {SOFTWARE_PASSWORD_MIN_LENGTH} 位"
        )

        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.Password)
        self.confirm_edit.setPlaceholderText("再次输入软件密码")

        form.addRow("软件密码", self.password_edit)
        form.addRow("确认密码", self.confirm_edit)
        root.addWidget(card)

        self.error_label = QLabel("")
        self.error_label.setObjectName("mutedLabel")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Save
        )
        buttons.button(QDialogButtonBox.Save).setText("设置密码")
        buttons.button(QDialogButtonBox.Save).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._save_password)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        QTimer.singleShot(
            0,
            lambda: set_windows_titlebar_dark(self, self.theme.dark),
        )

    def _save_password(self) -> None:
        password = self.password_edit.text()
        confirm = self.confirm_edit.text()

        if len(password) < SOFTWARE_PASSWORD_MIN_LENGTH:
            self.error_label.setText(
                f"软件密码至少需要 {SOFTWARE_PASSWORD_MIN_LENGTH} 位。"
            )
            self.password_edit.setFocus()
            return

        if password != confirm:
            self.error_label.setText("两次输入的软件密码不一致。")
            self.confirm_edit.selectAll()
            self.confirm_edit.setFocus()
            return

        try:
            SoftwarePasswordManager.configure(self.settings, password)
        except Exception as exc:
            self.error_label.setText(str(exc))
            return

        # Clear plaintext fields before closing.
        self.password_edit.clear()
        self.confirm_edit.clear()
        self.accept()


class SoftwarePasswordDeleteDialog(QDialog):
    """Delete software password only after validating the current password."""

    def __init__(
        self,
        settings: AppSettings,
        theme: ThemeManager,
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.theme = theme

        self.setWindowTitle("删除软件密码")
        fit_dialog_to_screen(self, 500, 310, 430, 280)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        title = QLabel("删除软件密码")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        desc = QLabel(
            "删除软件密码必须先验证当前原密码。"
            "此操作只删除软件密码验证器，不会删除常用语。"
        )
        desc.setObjectName("mutedLabel")
        desc.setWordWrap(True)
        root.addWidget(desc)

        warning = QLabel(
            "删除后，如果设备没有可用 Windows PIN / Hello，"
            "下次需要保护隐藏常用语时会重新要求设置软件密码。"
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("font-weight:600;")
        root.addWidget(warning)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("输入当前软件密码")
        self.password_edit.returnPressed.connect(self._delete_password)
        root.addWidget(self.password_edit)

        self.error_label = QLabel("")
        self.error_label.setObjectName("mutedLabel")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok
        )
        delete_btn = buttons.button(QDialogButtonBox.Ok)
        delete_btn.setText("删除密码")
        delete_btn.setObjectName("dangerButton")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._delete_password)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        QTimer.singleShot(
            0,
            lambda: (
                set_windows_titlebar_dark(self, self.theme.dark),
                self.password_edit.setFocus(),
            ),
        )

    def _delete_password(self) -> None:
        current_password = self.password_edit.text()

        if not SoftwarePasswordManager.delete(
            self.settings,
            current_password,
        ):
            self.password_edit.clear()
            self.error_label.setText("原软件密码错误。")
            self.password_edit.setFocus()
            return

        self.password_edit.clear()
        self.accept()


class SoftwarePasswordChangeDialog(QDialog):
    """Change the local software password after proving the current password."""

    def __init__(
        self,
        settings: AppSettings,
        theme: ThemeManager,
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.theme = theme

        self.setWindowTitle("修改软件密码")
        fit_dialog_to_screen(self, 540, 390, 460, 350)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        title = QLabel("修改软件密码")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        desc = QLabel(
            "修改软件密码必须先验证当前原密码。"
            "新密码设置成功后，之后的隐藏常用语验证立即使用新密码。"
        )
        desc.setObjectName("mutedLabel")
        desc.setWordWrap(True)
        root.addWidget(desc)

        warning = QLabel(
            "软件密码无法找回。忘记原密码时无法直接重置，只能卸载 QuickPhrase；"
            "卸载会永久删除全部软件数据。"
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("font-weight:600;")
        root.addWidget(warning)

        card = QFrame()
        card.setObjectName("settingsCard")
        form = QFormLayout(card)
        form.setContentsMargins(18, 16, 18, 16)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        self.old_password_edit = QLineEdit()
        self.old_password_edit.setEchoMode(QLineEdit.Password)
        self.old_password_edit.setPlaceholderText("当前软件密码")

        self.new_password_edit = QLineEdit()
        self.new_password_edit.setEchoMode(QLineEdit.Password)
        self.new_password_edit.setPlaceholderText(
            f"至少 {SOFTWARE_PASSWORD_MIN_LENGTH} 位"
        )

        self.confirm_password_edit = QLineEdit()
        self.confirm_password_edit.setEchoMode(QLineEdit.Password)
        self.confirm_password_edit.setPlaceholderText("再次输入新密码")

        form.addRow("原密码", self.old_password_edit)
        form.addRow("新密码", self.new_password_edit)
        form.addRow("确认新密码", self.confirm_password_edit)
        root.addWidget(card)

        self.error_label = QLabel("")
        self.error_label.setObjectName("mutedLabel")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Save
        )
        buttons.button(QDialogButtonBox.Save).setText("修改密码")
        buttons.button(QDialogButtonBox.Save).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._change_password)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.old_password_edit.returnPressed.connect(
            self.new_password_edit.setFocus
        )
        self.new_password_edit.returnPressed.connect(
            self.confirm_password_edit.setFocus
        )
        self.confirm_password_edit.returnPressed.connect(
            self._change_password
        )

        QTimer.singleShot(
            0,
            lambda: (
                set_windows_titlebar_dark(self, self.theme.dark),
                self.old_password_edit.setFocus(),
            ),
        )

    def _clear_password_fields(self) -> None:
        self.old_password_edit.clear()
        self.new_password_edit.clear()
        self.confirm_password_edit.clear()

    def _change_password(self) -> None:
        old_password = self.old_password_edit.text()
        new_password = self.new_password_edit.text()
        confirm_password = self.confirm_password_edit.text()

        if not SoftwarePasswordManager.verify(
            self.settings,
            old_password,
        ):
            self.old_password_edit.clear()
            self.error_label.setText("原软件密码错误。")
            self.old_password_edit.setFocus()
            return

        if len(new_password) < SOFTWARE_PASSWORD_MIN_LENGTH:
            self.error_label.setText(
                f"新软件密码至少需要 {SOFTWARE_PASSWORD_MIN_LENGTH} 位。"
            )
            self.new_password_edit.setFocus()
            return

        if new_password != confirm_password:
            self.error_label.setText("两次输入的新软件密码不一致。")
            self.confirm_password_edit.selectAll()
            self.confirm_password_edit.setFocus()
            return

        if hmac.compare_digest(old_password, new_password):
            self.error_label.setText("新密码不能与原密码相同。")
            self.new_password_edit.clear()
            self.confirm_password_edit.clear()
            self.new_password_edit.setFocus()
            return

        try:
            changed = SoftwarePasswordManager.change(
                self.settings,
                old_password,
                new_password,
            )
        except Exception as exc:
            self.error_label.setText(str(exc))
            return

        if not changed:
            self.error_label.setText("原软件密码错误。")
            self.old_password_edit.clear()
            self.old_password_edit.setFocus()
            return

        self._clear_password_fields()
        self.accept()


class SoftwarePasswordVerifyDialog(QDialog):
    def __init__(
        self,
        settings: AppSettings,
        theme: ThemeManager,
        action_text: str,
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.theme = theme
        self.action_text = action_text

        self.setWindowTitle("验证软件密码")
        fit_dialog_to_screen(self, 470, 260, 410, 240)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        title = QLabel("验证软件密码")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        desc = QLabel(
            f"请输入软件密码以{action_text}隐藏常用语。"
        )
        desc.setObjectName("mutedLabel")
        desc.setWordWrap(True)
        root.addWidget(desc)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("软件密码")
        self.password_edit.returnPressed.connect(self._verify)
        root.addWidget(self.password_edit)

        self.error_label = QLabel("")
        self.error_label.setObjectName("mutedLabel")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        no_recovery = QLabel(
            "软件密码无法找回；修改或删除密码都必须验证原密码。"
            "忘记原密码只能卸载 QuickPhrase，卸载会永久删除全部软件数据。"
        )
        no_recovery.setObjectName("tinyLabel")
        no_recovery.setWordWrap(True)
        root.addWidget(no_recovery)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok
        )
        buttons.button(QDialogButtonBox.Ok).setText("验证")
        buttons.button(QDialogButtonBox.Ok).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._verify)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        QTimer.singleShot(
            0,
            lambda: (
                set_windows_titlebar_dark(self, self.theme.dark),
                self.password_edit.setFocus(),
            ),
        )

    def _verify(self) -> None:
        password = self.password_edit.text()
        if SoftwarePasswordManager.verify(self.settings, password):
            self.password_edit.clear()
            self.accept()
            return

        self.password_edit.clear()
        self.error_label.setText("软件密码错误。")
        self.password_edit.setFocus()


def delete_software_password(
    settings: AppSettings,
    theme: ThemeManager,
    parent: QWidget,
) -> bool:
    if not SoftwarePasswordManager.is_configured(settings):
        return True

    dialog = SoftwarePasswordDeleteDialog(settings, theme, parent)
    if (
        isinstance(parent, QDialog)
        and parent.windowFlags() & Qt.WindowStaysOnTopHint
    ):
        dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)

    return dialog.exec() == QDialog.Accepted


def change_software_password(
    settings: AppSettings,
    theme: ThemeManager,
    parent: QWidget,
) -> bool:
    if not SoftwarePasswordManager.is_configured(settings):
        return setup_software_password(settings, theme, parent)

    dialog = SoftwarePasswordChangeDialog(settings, theme, parent)
    if (
        isinstance(parent, QDialog)
        and parent.windowFlags() & Qt.WindowStaysOnTopHint
    ):
        dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)

    return dialog.exec() == QDialog.Accepted


def setup_software_password(
    settings: AppSettings,
    theme: ThemeManager,
    parent: QWidget,
) -> bool:
    if SoftwarePasswordManager.is_configured(settings):
        return True

    dialog = SoftwarePasswordSetupDialog(settings, theme, parent)
    if isinstance(parent, QDialog) and parent.windowFlags() & Qt.WindowStaysOnTopHint:
        dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    return dialog.exec() == QDialog.Accepted


def ensure_hidden_security_ready(
    settings: AppSettings,
    theme: ThemeManager,
    parent: QWidget,
    announce_missing_pin: bool = True,
) -> tuple[bool, str, bool]:
    """
    Returns:
        ready, resolved_mode, password_just_created
    """
    mode = settings.security_mode

    if mode == "pin":
        pin_available, _code, pin_message = (
            WindowsHelloVerifier.check_availability()
        )
        if pin_available:
            return True, "pin", False

        if announce_missing_pin:
            box = QMessageBox(parent)
            box.setWindowTitle("未检测到 PIN")
            box.setIcon(QMessageBox.Warning)
            box.setText("未检测到PIN安全设备，请设置软件密码。")
            box.setInformativeText(pin_message)
            box.setStandardButtons(QMessageBox.Ok)
            set_windows_titlebar_dark(box, theme.dark)
            box.exec()

        already_configured = SoftwarePasswordManager.is_configured(settings)
        if not already_configured:
            if not setup_software_password(settings, theme, parent):
                return False, "password", False

        settings.security_mode = "password"
        return True, "password", not already_configured

    # Explicit software-password mode.
    already_configured = SoftwarePasswordManager.is_configured(settings)
    if not already_configured:
        if not setup_software_password(settings, theme, parent):
            return False, "password", False

    return True, "password", not already_configured


# ---------------------------------------------------------------------------
# Phrase editor
# ---------------------------------------------------------------------------

class PhraseDialog(QDialog):
    def __init__(
        self,
        theme: ThemeManager,
        settings: AppSettings,
        parent=None,
        phrase: Phrase | None = None,
    ):
        super().__init__(parent)
        self.theme = theme
        self.settings = settings
        self.phrase = phrase
        self._reverting_hidden_switch = False

        self.setWindowTitle("编辑常用语" if phrase else "添加常用语")
        fit_dialog_to_screen(self, 580, 410, 500, 360)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(18)

        title = QLabel("编辑常用语" if phrase else "添加常用语")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        card = QFrame()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)

        name_label = QLabel("名称")
        name_label.setObjectName("rowTitle")
        self.name_edit = QLineEdit(phrase.name if phrase else "")
        self.name_edit.setPlaceholderText("可选；隐藏内容时必须设置名称")
        self.name_edit.setClearButtonEnabled(True)

        content_label = QLabel("常用语内容")
        content_label.setObjectName("rowTitle")
        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText("输入要复制或自动粘贴的内容…")
        self.text_edit.setMinimumHeight(130)
        if phrase:
            self.text_edit.setPlainText(phrase.text)

        hidden_line = QHBoxLayout()
        hidden_text = QVBoxLayout()
        hidden_text.setSpacing(2)
        hidden_title = QLabel("隐藏内容")
        hidden_title.setObjectName("rowTitle")
        hidden_desc = QLabel(
            "隐藏后列表只显示名称与“••••••”；使用时按“软件设置”中的安全方式验证"
        )
        hidden_desc.setObjectName("mutedLabel")
        hidden_desc.setWordWrap(True)
        hidden_text.addWidget(hidden_title)
        hidden_text.addWidget(hidden_desc)

        self.hidden_switch = FluentSwitch()
        self.hidden_switch.setChecked(bool(phrase.hidden) if phrase else False)
        self.hidden_switch.toggled.connect(self._hidden_toggled)

        hidden_line.addLayout(hidden_text, 1)
        hidden_line.addWidget(self.hidden_switch, 0, Qt.AlignVCenter)

        card_layout.addWidget(name_label)
        card_layout.addWidget(self.name_edit)
        card_layout.addWidget(content_label)
        card_layout.addWidget(self.text_edit)
        card_layout.addLayout(hidden_line)
        root.addWidget(card, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Save
        )
        buttons.button(QDialogButtonBox.Save).setText("保存")
        buttons.button(QDialogButtonBox.Save).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        QTimer.singleShot(
            0,
            lambda: set_windows_titlebar_dark(self, self.theme.dark),
        )

    def _hidden_toggled(self, checked: bool) -> None:
        if not checked or self._reverting_hidden_switch:
            return

        # Editing an already-hidden phrase was authenticated before this dialog
        # opened; do not ask again merely because its initial switch is on.
        if self.phrase is not None and self.phrase.hidden:
            return

        ready, _mode, _just_created = ensure_hidden_security_ready(
            self.settings,
            self.theme,
            self,
            announce_missing_pin=True,
        )
        if ready:
            return

        self._reverting_hidden_switch = True
        try:
            self.hidden_switch.setChecked(False)
        finally:
            self._reverting_hidden_switch = False

    def _validate(self) -> None:
        name = self.name_edit.text().strip()
        text = self.text_edit.toPlainText().strip()
        hidden = self.hidden_switch.isChecked()

        if not text:
            QMessageBox.warning(self, "无法保存", "常用语内容不能为空。")
            return

        if hidden and not name:
            QMessageBox.warning(
                self,
                "需要名称",
                "隐藏常用语必须设置名称，否则隐藏后无法识别。",
            )
            self.name_edit.setFocus()
            return

        self.accept()

    def value(self) -> Phrase:
        return Phrase(
            id=self.phrase.id if self.phrase else str(uuid.uuid4()),
            name=self.name_edit.text().strip(),
            text=self.text_edit.toPlainText().strip(),
            hidden=self.hidden_switch.isChecked(),
        )


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

class PreferencePage(QWidget):
    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 30, 34, 28)
        root.setSpacing(13)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        desc_label = QLabel(description)
        desc_label.setObjectName("mutedLabel")
        desc_label.setWordWrap(True)

        root.addWidget(title_label)
        root.addWidget(desc_label)
        root.addSpacing(10)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(13)
        root.addLayout(self.content_layout)
        root.addStretch(1)


class PreferencesDialog(QDialog):
    def __init__(
        self,
        settings: AppSettings,
        theme: ThemeManager,
        apply_callback: Callable[[dict], tuple[bool, str]],
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.theme = theme
        self.apply_callback = apply_callback

        self.setWindowTitle("QuickPhrase — 偏好设置")
        fit_dialog_to_screen(self, 920, 700, 760, 560)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 24, 16, 20)
        side.setSpacing(8)

        brand = QLabel("偏好设置")
        brand.setObjectName("sectionTitle")
        side.addWidget(brand)
        side.addSpacing(12)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        self.nav_appearance = NavigationButton("外观")
        self.nav_shortcut = NavigationButton("快捷键设置")
        self.nav_advanced = NavigationButton("高级设置")
        self.nav_software = NavigationButton("软件设置")

        for button in (
            self.nav_appearance,
            self.nav_shortcut,
            self.nav_advanced,
            self.nav_software,
        ):
            self.nav_group.addButton(button)
            side.addWidget(button)

        side.addStretch(1)
        version = QLabel(f"QuickPhrase {APP_VERSION}")
        version.setObjectName("tinyLabel")
        side.addWidget(version)

        root.addWidget(sidebar)

        # Right
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.stack = QStackedWidget()
        right_layout.addWidget(self.stack, 1)

        bottom = QFrame()
        bottom.setObjectName("compactCard")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(18, 10, 18, 10)
        bottom_layout.addStretch(1)

        cancel = QPushButton("取消")
        save = QPushButton("保存")
        save.setObjectName("primaryButton")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)

        bottom_layout.addWidget(cancel)
        bottom_layout.addWidget(save)
        right_layout.addWidget(bottom)

        root.addWidget(right, 1)

        self._build_appearance()
        self._build_shortcut()
        self._build_advanced()
        self._build_software()

        self.nav_appearance.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.nav_shortcut.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.nav_advanced.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        self.nav_software.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        self.nav_appearance.setChecked(True)

        QTimer.singleShot(
            0,
            lambda: set_windows_titlebar_dark(self, self.theme.dark),
        )

    def _build_appearance(self) -> None:
        page = PreferencePage(
            "外观",
            "选择应用主题。",
        )

        section = QLabel("应用外观")
        section.setObjectName("sectionTitle")
        page.content_layout.addWidget(section)

        self.theme_choice = SegmentedChoice([
            ("system", "跟随系统"),
            ("light", "浅色"),
            ("dark", "深色"),
        ])
        self.theme_choice.set_value(self.settings.theme_mode)

        card = SettingsCard()
        card.add_row(
            "应用主题",
            "跟随 Windows、始终使用浅色或始终使用深色",
            self.theme_choice,
            74,
        )

        page.content_layout.addWidget(card)
        self.stack.addWidget(page)

    def _build_shortcut(self) -> None:
        page = PreferencePage(
            "快捷键设置",
            "设置在任意窗口中召唤常用语快捷窗口的全局快捷键。",
        )

        section = QLabel("召唤快捷键")
        section.setObjectName("sectionTitle")
        page.content_layout.addWidget(section)

        self.hotkey_edit = QKeySequenceEdit(QKeySequence(self.settings.hotkey))
        self.hotkey_edit.setMaximumSequenceLength(1)
        self.hotkey_edit.setClearButtonEnabled(True)
        self.hotkey_edit.setFixedWidth(240)

        card = SettingsCard()
        card.add_row(
            "召唤常用语窗口",
            "建议使用 Ctrl / Alt / Shift 组合，避免和系统快捷键或游戏快捷键冲突",
            self.hotkey_edit,
            78,
        )
        page.content_layout.addWidget(card)

        note = QLabel("当前默认：Ctrl + Alt + Space")
        note.setObjectName("mutedLabel")
        page.content_layout.addWidget(note)

        self.stack.addWidget(page)

    def _build_advanced(self) -> None:
        page = PreferencePage(
            "高级设置",
            "设置常用语触发方式、执行行为，以及自动粘贴后的剪贴板处理方式。",
        )

        section = QLabel("常用语使用方式")
        section.setObjectName("sectionTitle")
        page.content_layout.addWidget(section)

        self.trigger_choice = SegmentedChoice([
            ("single", "单击"),
            ("double", "双击"),
        ])
        self.trigger_choice.set_value(self.settings.phrase_trigger_mode)

        self.action_choice = SegmentedChoice([
            ("paste", "自动粘贴到光标"),
            ("copy", "仅复制到剪贴板"),
        ])
        self.action_choice.set_value(self.settings.action_mode)
        self.action_choice.changed.connect(self._sync_clear_enabled)

        self.clear_switch = FluentSwitch()
        self.clear_switch.setChecked(self.settings.clear_clipboard)

        card = SettingsCard()
        card.add_row(
            "使用常用语的方式",
            "选择单击或双击触发常用语；默认单击",
            self.trigger_choice,
            82,
        )
        card.add_row(
            "触发后的操作",
            "自动回到召唤前的窗口粘贴，或仅复制到剪贴板",
            self.action_choice,
            82,
        )
        card.add_row(
            "粘贴后清除剪贴板",
            "自动粘贴完成后清除由 QuickPhrase 写入的复制内容；默认关闭",
            self.clear_switch,
            78,
        )
        page.content_layout.addWidget(card)

        security = QLabel(
            "安全说明：隐藏常用语的复制、自动粘贴、编辑和删除都会按“软件设置”中的 "
            "安全方式验证。Windows PIN / Hello 由系统处理；软件密码只保存加盐哈希。"
        )
        security.setObjectName("mutedLabel")
        security.setWordWrap(True)
        page.content_layout.addWidget(security)

        self.stack.addWidget(page)
        self._sync_clear_enabled(self.settings.action_mode)

    def _sync_clear_enabled(self, mode: str) -> None:
        self.clear_switch.setEnabled(mode == "paste")

    def _build_software(self) -> None:
        page = PreferencePage(
            "软件设置",
            "设置 QuickPhrase 主窗口和系统托盘相关的应用行为。",
        )

        section = QLabel("关闭行为")
        section.setObjectName("sectionTitle")
        page.content_layout.addWidget(section)

        # Translate the legacy v1.4.5 two-field representation into one clear
        # preference value.
        if not self.settings.close_prompt_suppressed:
            close_mode = "ask"
        else:
            close_mode = self.settings.close_action

        self.close_choice = SegmentedChoice([
            ("ask", "每次询问"),
            ("minimize", "最小化到托盘"),
            ("exit", "退出程序"),
        ])
        self.close_choice.set_value(close_mode)

        self.tray_double_click_choice = SegmentedChoice([
            ("main", "打开主界面"),
            ("picker", "打开常用语窗口"),
            ("preferences", "打开偏好设置"),
        ])
        self.tray_double_click_choice.set_value(
            self.settings.tray_double_click_action
        )

        self.startup_switch = FluentSwitch()
        self.startup_switch.setChecked(self.settings.startup_enabled)

        (
            self.pin_security_available,
            self.pin_security_status,
            self.pin_security_message,
        ) = WindowsHelloVerifier.check_availability()

        self.security_choice = SegmentedChoice([
            ("pin", "Windows PIN"),
            ("password", "软件密码"),
        ])

        # Give the English label enough room even when selected text becomes
        # semibold and Windows DPI/font scaling is >100%.
        self.security_choice.setMinimumWidth(252)
        self.security_choice.buttons["pin"].setMinimumWidth(132)
        self.security_choice.buttons["password"].setMinimumWidth(108)

        requested_security_mode = self.settings.security_mode
        if not self.pin_security_available:
            self.security_choice.buttons["pin"].setEnabled(False)
            self.security_choice.buttons["pin"].setToolTip(
                self.pin_security_message
            )
            requested_security_mode = "password"

        self.security_choice.set_value(requested_security_mode)

        self.password_setup_button = QPushButton()
        self.password_delete_button = QPushButton("删除软件密码")
        self.password_delete_button.setObjectName("dangerButton")

        password_actions = QWidget()
        password_actions_layout = QHBoxLayout(password_actions)
        password_actions_layout.setContentsMargins(0, 0, 0, 0)
        password_actions_layout.setSpacing(8)
        password_actions_layout.addWidget(self.password_setup_button)
        password_actions_layout.addWidget(self.password_delete_button)

        self.password_actions = password_actions

        self._sync_password_setup_button()
        self.password_setup_button.clicked.connect(
            self._setup_password_from_preferences
        )
        self.password_delete_button.clicked.connect(
            self._delete_password_from_preferences
        )

        card = SettingsCard()
        card.add_row(
            "点击主窗口关闭按钮",
            "选择点击右上角 × 时的默认行为；“每次询问”会继续显示关闭确认窗口",
            self.close_choice,
            82,
        )
        card.add_row(
            "双击任务栏托盘图标",
            "设置双击 QuickPhrase 托盘图标时打开的界面",
            self.tray_double_click_choice,
            82,
        )
        card.add_row(
            "开机自启动",
            "登录 Windows 后自动启动 QuickPhrase 到系统托盘，不弹出主界面",
            self.startup_switch,
            78,
        )

        pin_desc = (
            "默认使用 Windows PIN / Hello 验证隐藏常用语"
            if self.pin_security_available
            else "当前设备未检测到可用 Windows PIN / Hello；PIN 已禁用"
        )
        card.add_row(
            "隐藏内容验证方式",
            pin_desc,
            self.security_choice,
            84,
        )
        card.add_row(
            "软件密码",
            "可使用原密码修改或删除；无法找回，忘记原密码只能卸载并删除全部软件数据",
            self.password_actions,
            84,
        )

        page.content_layout.addWidget(card)

        hint = QLabel(
            "选择“每次询问”后，关闭确认窗口中的“不再提示”仍可用于快速记住当次选择；"
            "之后也可以随时回到这里重新修改。"
        )
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        page.content_layout.addWidget(hint)

        self.stack.addWidget(page)

    def _sync_password_setup_button(self) -> None:
        configured = SoftwarePasswordManager.is_configured(self.settings)
        self.password_setup_button.setText(
            "修改软件密码" if configured else "设置软件密码"
        )
        self.password_setup_button.setEnabled(True)
        self.password_delete_button.setVisible(configured)
        self.password_delete_button.setEnabled(configured)

    def _delete_password_from_preferences(self) -> None:
        if not SoftwarePasswordManager.is_configured(self.settings):
            self._sync_password_setup_button()
            return

        if not delete_software_password(
            self.settings,
            self.theme,
            self,
        ):
            return

        pin_available, _code, _message = (
            WindowsHelloVerifier.check_availability()
        )

        if pin_available:
            self.security_choice.buttons["pin"].setEnabled(True)
            self.security_choice.set_value("pin")
            self.settings.security_mode = "pin"
        else:
            self.security_choice.set_value("password")
            self.settings.security_mode = "password"

        self._sync_password_setup_button()

    def _setup_password_from_preferences(self) -> None:
        if SoftwarePasswordManager.is_configured(self.settings):
            if change_software_password(
                self.settings,
                self.theme,
                self,
            ):
                self._sync_password_setup_button()
            return

        if setup_software_password(self.settings, self.theme, self):
            self.security_choice.set_value("password")
            self._sync_password_setup_button()

    def _save(self) -> None:
        sequence = self.hotkey_edit.keySequence().toString(
            QKeySequence.PortableText
        ).strip()

        if not sequence:
            QMessageBox.warning(self, "无法保存", "召唤快捷键不能为空。")
            return

        security_mode = self.security_choice.value() or "password"

        if security_mode == "pin" and not self.pin_security_available:
            QMessageBox.warning(
                self,
                "PIN 不可用",
                "当前设备未检测到可用 Windows PIN / Hello，只能使用软件密码。",
            )
            return

        if (
            security_mode == "password"
            and not SoftwarePasswordManager.is_configured(self.settings)
        ):
            if not setup_software_password(self.settings, self.theme, self):
                return
            self._sync_password_setup_button()

        values = {
            "theme_mode": self.theme_choice.value() or "system",
            "hotkey": sequence,
            "action_mode": self.action_choice.value() or "paste",
            "phrase_trigger_mode": self.trigger_choice.value() or "single",
            "clear_clipboard": self.clear_switch.isChecked(),
            "close_mode": self.close_choice.value() or "ask",
            "tray_double_click_action":
                self.tray_double_click_choice.value() or "main",
            "startup_enabled": self.startup_switch.isChecked(),
            "security_mode": security_mode,
        }

        ok, message = self.apply_callback(values)
        if not ok:
            QMessageBox.warning(self, "无法保存", message)
            return

        self.accept()


PICKER_NAME_ROLE = 0x0101
PICKER_PREVIEW_ROLE = 0x0102

REORDER_NAME_ROLE = 0x0111
REORDER_PREVIEW_ROLE = 0x0112


class PickerPhraseDelegate(QStyledItemDelegate):
    """Paint `bold name：normal content` without per-row QWidget overhead."""

    def __init__(self, theme: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme = theme

    def paint(self, painter, option, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        # Let the native/QSS style draw hover, selected background and border.
        opt.text = ""
        style = opt.widget.style() if opt.widget is not None else QApplication.style()
        style.drawControl(
            QStyle.CE_ItemViewItem,
            opt,
            painter,
            opt.widget,
        )

        name = str(index.data(PICKER_NAME_ROLE) or "未命名常用语")
        preview = str(index.data(PICKER_PREVIEW_ROLE) or "")

        rect = option.rect.adjusted(10, 0, -10, 0)
        if rect.width() <= 8:
            return

        selected = bool(option.state & QStyle.State_Selected)
        color = QColor(
            self.theme.tokens["accent"]
            if selected
            else self.theme.tokens["text"]
        )

        painter.save()
        painter.setPen(color)

        # Keep the name readable but leave enough room for content.
        normal_font = QFont(option.font)
        name_font = QFont(option.font)
        name_font.setWeight(QFont.DemiBold)

        painter.setFont(name_font)
        name_metrics = painter.fontMetrics()
        max_name_width = max(56, int(rect.width() * 0.46))
        shown_name = name_metrics.elidedText(
            name,
            Qt.ElideRight,
            max_name_width,
        )
        name_width = name_metrics.horizontalAdvance(shown_name)

        painter.drawText(
            QRect(rect.left(), rect.top(), name_width, rect.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            shown_name,
        )

        painter.setFont(normal_font)
        normal_metrics = painter.fontMetrics()
        separator = "："
        sep_width = normal_metrics.horizontalAdvance(separator)

        sep_x = rect.left() + name_width
        painter.drawText(
            QRect(sep_x, rect.top(), sep_width, rect.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            separator,
        )

        content_x = sep_x + sep_width
        content_width = max(0, rect.right() - content_x + 1)
        shown_preview = normal_metrics.elidedText(
            preview,
            Qt.ElideRight,
            content_width,
        )
        painter.drawText(
            QRect(content_x, rect.top(), content_width, rect.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            shown_preview,
        )

        painter.restore()


EMPTY_STATE_ROLE = 0x0121


class EmptyStateDelegate(QStyledItemDelegate):
    """Centered, bold empty-state message for the main phrase list."""

    def __init__(self, theme: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme = theme

    def paint(self, painter, option, index) -> None:
        if not bool(index.data(EMPTY_STATE_ROLE)):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = option.rect.adjusted(12, 8, -12, -8)
        tokens = self.theme.tokens

        line1 = "暂无常用语"
        line2 = "点击右上角 + 添加"

        title_font = QFont(option.font)
        title_font.setWeight(QFont.DemiBold)

        sub_font = QFont(option.font)
        sub_font.setWeight(QFont.Medium)

        title_metrics = QFontMetrics(title_font)
        sub_metrics = QFontMetrics(sub_font)

        gap = 4
        total_h = title_metrics.height() + gap + sub_metrics.height()
        top = rect.center().y() - total_h // 2

        painter.setFont(title_font)
        painter.setPen(QColor(tokens["text"]))
        painter.drawText(
            QRect(
                rect.left(),
                top,
                rect.width(),
                title_metrics.height(),
            ),
            Qt.AlignHCenter | Qt.AlignVCenter,
            line1,
        )

        painter.setFont(sub_font)
        painter.setPen(QColor(tokens["muted"]))
        painter.drawText(
            QRect(
                rect.left(),
                top + title_metrics.height() + gap,
                rect.width(),
                sub_metrics.height(),
            ),
            Qt.AlignHCenter | Qt.AlignVCenter,
            line2,
        )

        painter.restore()


class ReorderPhraseDelegate(QStyledItemDelegate):
    """Paint a compact reorder row with a subtle three-line drag grip."""

    def __init__(self, theme: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme = theme

    def paint(self, painter, option, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        # Draw only the normal item background/border through the active
        # style. Reorder text is stored in two dedicated model roles, so Qt
        # can never merge/normalize a title+newline+preview display string.
        opt.text = ""
        style = (
            opt.widget.style()
            if opt.widget is not None
            else QApplication.style()
        )
        painter.save()
        style.drawControl(
            QStyle.CE_ItemViewItem,
            opt,
            painter,
            opt.widget,
        )
        painter.restore()

        title = str(index.data(REORDER_NAME_ROLE) or "未命名常用语")
        preview = str(index.data(REORDER_PREVIEW_ROLE) or "")

        selected = bool(option.state & QStyle.State_Selected)
        tokens = self.theme.tokens

        text_color = QColor(
            tokens["selected_text"]
            if selected
            else tokens["text"]
        )
        muted_color = QColor(
            tokens["accent"]
            if selected
            else tokens["muted"]
        )

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = option.rect
        grip_x = rect.left() + 15
        center_y = rect.center().y()

        # Refined grip: short, thin, rounded strokes instead of a Unicode ☰.
        grip_pen = QPen(muted_color, 1.6)
        grip_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(grip_pen)

        half = 5
        for dy in (-5, 0, 5):
            painter.drawLine(
                grip_x - half,
                center_y + dy,
                grip_x + half,
                center_y + dy,
            )

        text_left = rect.left() + 34
        text_right = rect.right() - 8
        text_width = max(20, text_right - text_left)

        title_font = QFont(option.font)
        title_font.setWeight(QFont.DemiBold)
        painter.setFont(title_font)
        painter.setPen(text_color)

        # IMPORTANT: draw text by BASELINE, not inside small QRect boxes.
        # QRect-based drawText clips glyphs when the real Windows font ascent /
        # descent is slightly larger than the computed rectangle, which caused
        # the visibly chopped text reported on several DPI/font combinations.
        title_metrics = QFontMetrics(title_font)
        preview_font = QFont(option.font)
        preview_metrics = QFontMetrics(preview_font)

        # Two independent text lines, positioned by their real font metrics.
        # There is no shared text string and no multiline drawing call.
        title_line_height = title_metrics.height()
        preview_line_height = preview_metrics.height()
        row_gap = max(4, title_metrics.leading(), preview_metrics.leading())

        block_height = title_line_height + row_gap + preview_line_height
        block_top = rect.center().y() - block_height // 2

        title_baseline = block_top + title_metrics.ascent()
        preview_baseline = (
            block_top
            + title_line_height
            + row_gap
            + preview_metrics.ascent()
        )

        title_text = title_metrics.elidedText(
            title,
            Qt.ElideRight,
            text_width,
        )

        # Point/baseline overload: no vertical text rectangle => no glyph
        # clipping at the top/bottom.
        painter.setFont(title_font)
        painter.setPen(text_color)
        painter.drawText(text_left, title_baseline, title_text)

        preview_text = preview_metrics.elidedText(
            preview,
            Qt.ElideRight,
            text_width,
        )
        painter.setFont(preview_font)
        painter.setPen(
            QColor(
                tokens["selected_text"]
                if selected
                else tokens["muted"]
            )
        )
        painter.drawText(text_left, preview_baseline, preview_text)

        painter.restore()


class ReorderListWidget(QListWidget):
    """
    Lightweight phrase reordering without Qt native Drag & Drop.

    Why:
    QListWidget.InternalMove can create a short-lived native drag helper
    window on Windows when drag capability is enabled. On some systems this
    appears as a tiny blank title-bar window for one frame.

    This implementation never enables native drag/drop. It tracks the mouse,
    moves QListWidgetItems directly, and emits the final phrase-id order once
    on mouse release.
    """

    order_changed = Signal(list)

    def __init__(self, theme: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._reorder_delegate = ReorderPhraseDelegate(theme, self)
        self._default_delegate = self.itemDelegate()

        self._reorder_enabled = False
        self._pressed_row = -1
        self._drag_row = -1
        self._press_pos = QPoint()
        self._dragging = False
        self._last_target_row = -1

        # Explicitly keep all native drag/drop facilities disabled forever.
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)

    def set_reorder_enabled(self, enabled: bool) -> None:
        self._reorder_enabled = bool(enabled)
        self.setItemDelegate(
            self._reorder_delegate
            if enabled
            else self._default_delegate
        )

        # Do NOT toggle native drag/drop here. That was the source of the
        # one-frame auxiliary native window on Windows.
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)

        self._pressed_row = -1
        self._drag_row = -1
        self._dragging = False
        self._last_target_row = -1

        self.viewport().setCursor(
            Qt.OpenHandCursor if enabled else Qt.ArrowCursor
        )

    def _phrase_ids(self) -> list[str]:
        result: list[str] = []
        for row in range(self.count()):
            phrase_id = valid_phrase_id(self.item(row))
            if phrase_id:
                result.append(phrase_id)
        return result

    def _row_from_pos(self, pos: QPoint) -> int:
        item = self.itemAt(pos)
        if item is not None:
            return self.row(item)

        if self.count() <= 0:
            return -1

        # When dragging slightly above/below the last visible card, keep
        # movement predictable instead of cancelling the drag.
        first_rect = self.visualItemRect(self.item(0))
        last_rect = self.visualItemRect(self.item(self.count() - 1))

        if pos.y() < first_rect.top():
            return 0
        if pos.y() > last_rect.bottom():
            return self.count() - 1

        return -1

    def _move_item(self, from_row: int, to_row: int) -> int:
        if (
            from_row < 0
            or to_row < 0
            or from_row >= self.count()
            or to_row >= self.count()
            or from_row == to_row
        ):
            return from_row

        current = self.currentItem()
        item = self.takeItem(from_row)
        if item is None:
            return from_row

        self.insertItem(to_row, item)
        self.setCurrentItem(item)

        if current is item:
            self.scrollToItem(item, QAbstractItemView.EnsureVisible)

        return to_row

    def mousePressEvent(self, event) -> None:
        if self._reorder_enabled and event.button() == Qt.LeftButton:
            row = self._row_from_pos(event.position().toPoint())
            if row >= 0:
                self._pressed_row = row
                self._drag_row = row
                self._press_pos = event.position().toPoint()
                self._dragging = False
                self._last_target_row = row
                self.setCurrentRow(row)
                self.viewport().setCursor(Qt.ClosedHandCursor)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            self._reorder_enabled
            and self._pressed_row >= 0
            and (event.buttons() & Qt.LeftButton)
        ):
            pos = event.position().toPoint()

            if not self._dragging:
                distance = (pos - self._press_pos).manhattanLength()
                if distance < QApplication.startDragDistance():
                    event.accept()
                    return
                self._dragging = True

            target_row = self._row_from_pos(pos)
            if target_row >= 0 and target_row != self._drag_row:
                self._drag_row = self._move_item(
                    self._drag_row,
                    target_row,
                )
                self._last_target_row = self._drag_row

            # Auto-scroll near the viewport edges without starting QDrag.
            margin = 24
            if pos.y() < margin:
                bar = self.verticalScrollBar()
                bar.setValue(bar.value() - max(8, bar.singleStep()))
            elif pos.y() > self.viewport().height() - margin:
                bar = self.verticalScrollBar()
                bar.setValue(bar.value() + max(8, bar.singleStep()))

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._reorder_enabled and event.button() == Qt.LeftButton:
            was_dragging = self._dragging

            self._pressed_row = -1
            self._drag_row = -1
            self._dragging = False
            self._last_target_row = -1
            self.viewport().setCursor(Qt.OpenHandCursor)

            if was_dragging:
                ordered_ids = self._phrase_ids()
                if ordered_ids:
                    self.order_changed.emit(ordered_ids)

            event.accept()
            return

        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if self._reorder_enabled and not (QApplication.mouseButtons() & Qt.LeftButton):
            self.viewport().setCursor(Qt.OpenHandCursor)
        super().leaveEvent(event)


# ---------------------------------------------------------------------------
# Phrase row + display helpers
# ---------------------------------------------------------------------------

def phrase_display_text(phrase: Phrase, preview_limit: int = 42) -> str:
    title = phrase.name.strip() or "未命名常用语"
    if phrase.hidden:
        preview = "••••••"
    else:
        preview = " ".join(phrase.text.split())
        if len(preview) > preview_limit:
            preview = preview[:preview_limit] + "…"
    return f"{title}\n{preview}"


def valid_phrase_id(item: QListWidgetItem | None) -> str:
    if item is None:
        return ""
    return str(item.data(Qt.UserRole) or "")


class PhraseRow(QWidget):
    copy_requested = Signal(str)
    edit_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(
        self,
        phrase: Phrase,
        reorder_mode: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.phrase = phrase
        self.setObjectName("phraseRow")
        self.setProperty("selected", False)

        root = QHBoxLayout(self)
        root.setContentsMargins(7 if reorder_mode else 10, 5, 5, 5)
        root.setSpacing(4)

        self.reorder_handle = QLabel("☰")
        self.reorder_handle.setObjectName("reorderHandle")
        self.reorder_handle.setAlignment(Qt.AlignCenter)
        self.reorder_handle.setFixedWidth(22)
        self.reorder_handle.setVisible(reorder_mode)
        root.addWidget(self.reorder_handle)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)

        title = QLabel(phrase.name.strip() or "未命名常用语")
        title.setObjectName("phraseTitle")

        if phrase.hidden:
            preview_text = "••••••"
        else:
            preview_text = " ".join(phrase.text.split())
            if len(preview_text) > 25:
                preview_text = preview_text[:25] + "…"

        preview = QLabel(preview_text)
        preview.setObjectName("phrasePreview")

        text_box.addWidget(title)
        text_box.addWidget(preview)
        root.addLayout(text_box, 1)

        self.copy_btn = QPushButton("\uE8C8")
        self.copy_btn.setObjectName("iconButton")
        self.copy_btn.setToolTip("复制")
        self.copy_btn.clicked.connect(
            lambda: self.copy_requested.emit(self.phrase.id)
        )

        self.edit_btn = QPushButton("\uE70F")
        self.edit_btn.setObjectName("iconButton")
        self.edit_btn.setToolTip("编辑")
        self.edit_btn.clicked.connect(
            lambda: self.edit_requested.emit(self.phrase.id)
        )

        self.delete_btn = QPushButton("\uE74D")
        self.delete_btn.setObjectName("iconButton")
        self.delete_btn.setToolTip("删除")
        self.delete_btn.clicked.connect(
            lambda: self.delete_requested.emit(self.phrase.id)
        )

        root.addWidget(self.copy_btn)
        root.addWidget(self.edit_btn)
        root.addWidget(self.delete_btn)

        # Sorting mode is intentionally simple: the whole card becomes a drag
        # surface and action buttons disappear, while the three-line handle
        # communicates that the row can be moved.
        for button in (self.copy_btn, self.edit_btn, self.delete_btn):
            button.setVisible(not reorder_mode)

        if reorder_mode:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_selected(self, selected: bool) -> None:
        if bool(self.property("selected")) == bool(selected):
            return
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)
        for label in self.findChildren(QLabel):
            label.style().unpolish(label)
            label.style().polish(label)
        self.update()


# ---------------------------------------------------------------------------
# Draggable Quick Picker
# ---------------------------------------------------------------------------

class QuickPicker(QDialog):
    phrase_activated = Signal(str)

    def __init__(
        self,
        store: PhraseStore,
        settings: AppSettings,
        theme: ThemeManager,
        parent=None,
    ):
        super().__init__(parent)
        self.store = store
        self.settings = settings
        self.theme = theme
        self.target_hwnd = 0
        self._normal_footer = ""
        self._search_focus_active = False
        self._programmatic_move = False
        self._user_moved = False
        self._user_drag_active = False
        self._interactive_open = False

        self._search_refresh_timer = QTimer(self)
        self._search_refresh_timer.setSingleShot(True)
        self._search_refresh_timer.setInterval(45)
        self._search_refresh_timer.timeout.connect(self.refresh)

        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        # Solid edge-to-edge floating window: no transparent outer shell.
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self._apply_slim_geometry()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        shell = QFrame()
        shell.setObjectName("pickerShell")
        outer.addWidget(shell)

        root = QVBoxLayout(shell)
        root.setContentsMargins(11, 10, 11, 11)
        root.setSpacing(8)

        # Entire header blank area can be used to drag the window.
        header = QHBoxLayout()
        drag = DragArea()
        drag_layout = QHBoxLayout(drag)
        drag_layout.setContentsMargins(2, 0, 0, 0)
        drag_layout.setSpacing(6)

        title = QLabel("常用语")
        title.setObjectName("sectionTitle")
        self.mode_label = QLabel("")
        self.mode_label.setObjectName("tinyLabel")

        drag_layout.addWidget(title)
        drag_layout.addWidget(self.mode_label)
        drag_layout.addStretch(1)

        close_btn = QPushButton("\uE8BB")
        close_btn.setObjectName("iconButton")
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(self.hide)

        header.addWidget(drag, 1)
        header.addWidget(close_btn)
        root.addLayout(header)

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._schedule_refresh)
        self.search.installEventFilter(self)
        self.search.editingFinished.connect(self._finish_search_focus)
        root.addWidget(self.search)

        self.list = QListWidget()
        self.list.setObjectName("pickerList")
        self.list.setItemDelegate(PickerPhraseDelegate(self.theme, self.list))
        self.list.setSpacing(4)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.itemClicked.connect(self._single_click)
        self.list.itemDoubleClicked.connect(self._double_click)
        root.addWidget(self.list, 1)

        self.footer = QLabel("")
        self.footer.setObjectName("mutedLabel")
        self.footer.setWordWrap(True)
        root.addWidget(self.footer)

        self.refresh()

    def _apply_slim_geometry(self, screen=None) -> None:
        screen = (
            screen
            or QApplication.screenAt(QCursor.pos())
            or QApplication.primaryScreen()
        )
        size = adaptive_picker_size(screen)
        self.resize(size)
        self.setMinimumSize(
            min(218, size.width()),
            min(350, size.height()),
        )

    def _schedule_refresh(self) -> None:
        self._search_refresh_timer.start()

    def refresh(self) -> None:
        query = self.search.text().strip().lower()
        self.list.setUpdatesEnabled(False)
        try:
            self.list.clear()

            for phrase in self.store.phrases:
                # Hidden content is intentionally excluded from search.
                searchable = phrase.name.lower()
                if not phrase.hidden:
                    searchable += " " + phrase.text.lower()

                if query and query not in searchable:
                    continue

                title = phrase.name.strip() or "未命名常用语"
                if phrase.hidden:
                    preview = "••••••"
                else:
                    preview = " ".join(phrase.text.split())

                item = QListWidgetItem()
                item.setData(Qt.UserRole, phrase.id)
                item.setData(PICKER_NAME_ROLE, title)
                item.setData(PICKER_PREVIEW_ROLE, preview)
                # Plain display value remains available for accessibility and
                # keyboard tools even though the delegate paints rich weights.
                item.setData(Qt.DisplayRole, f"{title}：{preview}")
                item.setSizeHint(QSize(0, 44))
                self.list.addItem(item)

            # Opening / refreshing the quick phrase picker must keep a
            # neutral state. Do not preselect or highlight the first phrase.
            self.list.clearSelection()
            self.list.setCurrentItem(None)
        finally:
            self.list.setUpdatesEnabled(True)

        if self.settings.action_mode == "paste":
            self.mode_label.setText("自动粘贴")
        else:
            self.mode_label.setText("复制")

        # Normal help text is intentionally hidden. The picker is closed using
        # the top-right X; this footer is reserved for temporary status hints.
        self._normal_footer = ""
        self.footer.clear()
        self.footer.setVisible(False)

    def show_hint(self, text: str, timeout_ms: int = 1400) -> None:
        self.footer.setText(text)
        self.footer.setVisible(bool(text.strip()))

        def restore_footer() -> None:
            if not self.isVisible():
                return
            self.footer.setText(self._normal_footer)
            self.footer.setVisible(bool(self._normal_footer.strip()))

        QTimer.singleShot(timeout_ms, restore_footer)

    def _activate_phrase_item(self, item: QListWidgetItem) -> None:
        phrase_id = valid_phrase_id(item)
        if phrase_id:
            self.phrase_activated.emit(phrase_id)

    def _single_click(self, item: QListWidgetItem) -> None:
        if self.settings.phrase_trigger_mode == "single":
            self._activate_phrase_item(item)

    def _double_click(self, item: QListWidgetItem) -> None:
        if self.settings.phrase_trigger_mode == "double":
            self._activate_phrase_item(item)

    def summon(self, interactive: bool = False) -> None:
        # Store the window that was active before QuickPhrase appears. This is
        # still used as the paste target even when an interactive tray
        # double-click intentionally activates the picker.
        self.target_hwnd = current_foreground_hwnd()
        self._user_moved = False
        self._interactive_open = bool(interactive)

        # Avoid the old clear() -> textChanged(refresh) -> refresh() double rebuild.
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.refresh()
        self.list.clearSelection()
        self.list.setCurrentItem(None)

        screen = (
            QApplication.screenAt(QCursor.pos())
            or QApplication.primaryScreen()
        )
        self._apply_slim_geometry(screen)

        # v1.6.1 position-memory schema:
        # older builds could save a false top-left position from a system
        # moveEvent during first show. Ignore that legacy value once.
        if self.settings.picker_position_schema < 2:
            self.settings.picker_position_remembered = False
            self.settings.picker_position_schema = 2

        # Create/configure the native window BEFORE positioning it. Calling
        # winId() inside set_window_no_activate() can create the HWND; if this
        # happened after move(), Windows could reset the first position.
        if self._interactive_open:
            set_window_no_activate(self, False)
        else:
            set_window_no_activate(self, True)

        self._programmatic_move = True
        try:
            saved = self.settings.picker_pos()
            if self.settings.picker_position_remembered and saved is not None:
                saved_screen = QApplication.screenAt(saved)
                target_screen = saved_screen or screen
                desired_pos = clamp_window_top_left(
                    saved,
                    self.size(),
                    target_screen,
                )
            else:
                # First use / migrated legacy state: exact screen center.
                desired_pos = centered_window_pos(self.size(), screen)

            self.move(desired_pos)
        finally:
            self._programmatic_move = False

        self.show()
        self.raise_()

        if self._interactive_open:
            force_user_foreground(self)
            self.list.setFocus(Qt.ActiveWindowFocusReason)
            hwnd = int(self.winId())

            def refocus_if_needed() -> None:
                if (
                    self.isVisible()
                    and self._interactive_open
                    and foreground_hwnd() != hwnd
                ):
                    force_user_foreground(self)

            # Explorer sometimes keeps foreground ownership through the final
            # double-click mouse-up. One retry after that dispatch is enough;
            # WM_MOUSEACTIVATE guarantees that even if this retry is refused,
            # the first real click is not swallowed.
            QTimer.singleShot(140, refocus_if_needed)
        else:
            keep_window_topmost_noactivate(int(self.winId()))

    def nativeEvent(self, event_type, message):
        if os.name == "nt":
            try:
                msg = ctypes.cast(
                    int(message),
                    ctypes.POINTER(wintypes.MSG),
                ).contents

                WM_MOUSEACTIVATE = 0x0021
                if msg.message == WM_MOUSEACTIVATE:
                    MA_ACTIVATE = 1
                    MA_NOACTIVATE = 3

                    # Most important detail:
                    # neither result eats the original mouse message.
                    # So the first click can press a button or start dragging.
                    if self._interactive_open:
                        return True, MA_ACTIVATE
                    return True, MA_NOACTIVATE
            except Exception:
                pass

        return super().nativeEvent(event_type, message)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.search and event.type() == event.Type.MouseButtonPress:
            # Keyboard text entry requires focus, so search is the one explicit
            # exception to the no-activate behavior.
            self._begin_search_focus()
        return super().eventFilter(watched, event)

    def _begin_search_focus(self) -> None:
        if self._search_focus_active:
            return
        self._search_focus_active = True
        set_window_no_activate(self, False)
        self.activateWindow()
        self.search.setFocus(Qt.MouseFocusReason)

    def _finish_search_focus(self) -> None:
        if not self._search_focus_active:
            return
        self._search_focus_active = False
        set_window_no_activate(self, True)
        if self.target_hwnd:
            activate_window(self.target_hwnd)

    def showEvent(self, event) -> None:
        super().showEvent(event)

        def apply_native_picker_state() -> None:
            # summon() already selected the activation mode before show().
            if self._interactive_open:
                if foreground_hwnd() != int(self.winId()):
                    force_user_foreground(self)
            else:
                if not is_window_topmost(int(self.winId())):
                    keep_window_topmost_noactivate(int(self.winId()))

            handle = self.windowHandle()
            if handle is not None:
                # Dynamic property lives on the actual QWindow, so even if a
                # Python wrapper is recreated we still connect only once.
                if not bool(handle.property("qpScreenChangedConnected")):
                    handle.screenChanged.connect(self._on_screen_changed)
                    handle.setProperty("qpScreenChangedConnected", True)

        QTimer.singleShot(0, apply_native_picker_state)

    def _on_screen_changed(self, screen) -> None:
        if screen is None:
            return

        # Keep the current remembered position concept, but make sure the
        # window remains reachable after moving between differently scaled
        # monitors.
        safe = clamp_window_top_left(self.pos(), self.size(), screen)
        if safe != self.pos():
            self._programmatic_move = True
            try:
                self.move(safe)
            finally:
                self._programmatic_move = False

    def _begin_user_drag(self) -> None:
        self._user_drag_active = True
        self._user_moved = False
        QTimer.singleShot(25, self._poll_user_drag_release)

    def _cancel_user_drag(self) -> None:
        self._user_drag_active = False

    def _poll_user_drag_release(self) -> None:
        if not self._user_drag_active:
            return

        if QApplication.mouseButtons() & Qt.LeftButton:
            QTimer.singleShot(25, self._poll_user_drag_release)
            return

        self._user_drag_active = False
        if self._user_moved:
            self.settings.picker_position_remembered = True
            self.settings.picker_position_schema = 2
            self.settings.save_picker_pos(self.pos())

    def moveEvent(self, event) -> None:
        super().moveEvent(event)

        # Window managers, DPI changes, first show and native HWND creation can
        # all emit moveEvent. None of those count as a remembered user move.
        if (
            self.isVisible()
            and self._user_drag_active
            and not self._programmatic_move
        ):
            self._user_moved = True

    def hideEvent(self, event) -> None:
        if self._user_drag_active:
            self._user_drag_active = False

        if self._user_moved:
            self.settings.picker_position_remembered = True
            self.settings.picker_position_schema = 2
            self.settings.save_picker_pos(self.pos())

        self._search_focus_active = False
        self._interactive_open = False
        if self.target_hwnd:
            activate_window(self.target_hwnd)
        super().hideEvent(event)

    def keyPressEvent(self, event) -> None:
        # Closing the quick phrase window is intentionally explicit via the
        # top-right X. Escape is not a close shortcut.
        super().keyPressEvent(event)


class CloseActionDialog(QDialog):
    """Compact close confirmation shown only for the main-window title-bar X."""

    def __init__(self, theme: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.choice: str | None = None

        self.setWindowTitle("关闭 QuickPhrase")
        self.setModal(True)
        fit_dialog_to_screen(self, 450, 170, 390, 160)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(16)

        title = QLabel("关闭 QuickPhrase？")
        title.setObjectName("dialogTitle")

        description = QLabel(
            "关闭主窗口后，你希望让 QuickPhrase 继续在系统托盘运行，"
            "还是完全退出程序？"
        )
        description.setObjectName("mutedLabel")
        description.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(description)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self.dont_ask = AccentCheckBox("不再提示")
        self.dont_ask.setToolTip("记住本次选择，以后点击主窗口关闭按钮时直接执行")

        minimize_btn = QPushButton("最小化到托盘")
        minimize_btn.setObjectName("primaryButton")
        minimize_btn.setMinimumWidth(126)

        exit_btn = QPushButton("退出程序")
        exit_btn.setMinimumWidth(96)

        minimize_btn.clicked.connect(self._choose_minimize)
        exit_btn.clicked.connect(self._choose_exit)

        bottom.addWidget(self.dont_ask, 0, Qt.AlignVCenter)
        bottom.addStretch(1)
        bottom.addWidget(exit_btn)
        bottom.addWidget(minimize_btn)

        root.addLayout(bottom)

        QTimer.singleShot(
            0,
            lambda: set_windows_titlebar_dark(self, self.theme.dark),
        )

    def _choose_minimize(self) -> None:
        self.choice = "minimize"
        self.accept()

    def _choose_exit(self) -> None:
        self.choice = "exit"
        self.accept()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: AppSettings,
        theme: ThemeManager,
    ):
        super().__init__()
        self.settings = settings
        self.theme = theme
        self.store = PhraseStore()
        self._allow_exit = False
        self._security_restore_generation = 0
        self._reorder_mode = False

        self.setWindowTitle(f"{APP_NAME} — 常用语")
        self._apply_slim_geometry()

        self.bridge = HotkeyBridge()
        self.bridge.triggered.connect(self.show_picker)
        self.global_hotkey = GlobalHotkey(lambda: self.bridge.triggered.emit())

        self.picker = QuickPicker(
            self.store,
            self.settings,
            self.theme,
            None,
        )
        self.picker.phrase_activated.connect(self.activate_phrase)

        self._tray_single_click_timer = QTimer(self)
        self._tray_single_click_timer.setSingleShot(True)
        self._tray_single_click_timer.setInterval(
            max(180, QApplication.doubleClickInterval() - 20)
        )
        self._tray_single_click_timer.timeout.connect(self.show_picker)

        self._build_ui()
        self._build_tray()
        self.refresh_list()

        # Only restore a previous geometry if it is already reasonably slim.
        geometry = self.settings.main_geometry()
        if geometry:
            old = self.saveGeometry()
            if self.restoreGeometry(geometry):
                ratio = self.width() / max(1, self.height())
                if ratio < 0.42 or ratio > 0.68:
                    self.restoreGeometry(old)

        # Always keep the restored geometry reachable after monitor/DPI changes.
        current_screen = self.screen() or QApplication.primaryScreen()
        if current_screen:
            safe = clamp_window_top_left(
                self.pos(),
                self.size(),
                current_screen,
            )
            self.move(safe)

        ok, message = self.global_hotkey.register(self.settings.hotkey)
        if not ok:
            QTimer.singleShot(
                350,
                lambda: self._show_priority_message(
                    self,
                    "快捷键不可用",
                    message + "\n\n请在偏好设置 → 快捷键设置中更换。",
                ),
            )

        self.theme.theme_changed.connect(self._on_theme_changed)
        QTimer.singleShot(
            0,
            lambda: set_windows_titlebar_dark(self, self.theme.dark),
        )

    def _apply_slim_geometry(self, screen=None) -> None:
        screen = screen or self.screen() or QApplication.primaryScreen()
        size = adaptive_slim_size(screen)
        self.resize(size)
        self.setMinimumSize(
            min(310, size.width()),
            min(500, size.height()),
        )

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("pageRoot")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 11)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(5)

        title = QLabel("常用语")
        title.setObjectName("sectionTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("tinyLabel")

        add_btn = QPushButton("\uE710")
        add_btn.setObjectName("iconButton")
        add_btn.setToolTip("添加常用语")
        add_btn.clicked.connect(self.add_phrase)

        self.reorder_btn = QPushButton("\uE70F")
        self.reorder_btn.setObjectName("iconButton")
        self.reorder_btn.setToolTip("调整常用语顺序")
        self.reorder_btn.setProperty("editMode", False)
        self.reorder_btn.clicked.connect(self.toggle_reorder_mode)

        prefs_btn = QPushButton("\uE713")
        prefs_btn.setObjectName("iconButton")
        prefs_btn.setToolTip("偏好设置")
        prefs_btn.clicked.connect(self.open_preferences)

        header.addWidget(title)
        header.addWidget(self.count_label)
        header.addStretch(1)
        header.addWidget(add_btn)
        header.addWidget(self.reorder_btn)
        header.addWidget(prefs_btn)
        root.addLayout(header)

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_list)
        root.addWidget(self.search)

        self.list = ReorderListWidget(self.theme)
        self.list.setObjectName("phraseList")
        self._empty_delegate = EmptyStateDelegate(self.theme, self.list)
        self.list.setSpacing(4)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(
            self._show_phrase_context_menu
        )
        self.list.itemDoubleClicked.connect(self._main_double_click)
        self.list.currentItemChanged.connect(self._sync_row_selection)
        self.list.order_changed.connect(self._apply_phrase_order)
        root.addWidget(self.list, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("tinyLabel")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)

        # Use the same QP.ico everywhere: application/title bar/taskbar/tray.
        icon = QApplication.windowIcon()
        if icon.isNull():
            icon = load_app_icon()
        self.tray.setIcon(icon)
        self.setWindowIcon(icon)
        self.picker.setWindowIcon(icon)

        menu = QMenu()
        show_picker = QAction("显示常用语", self)
        show_picker.triggered.connect(self.show_picker)

        show_main = QAction("打开管理器", self)
        show_main.triggered.connect(self.show_main_window)

        preferences = QAction("偏好设置", self)
        preferences.triggered.connect(self.open_preferences)

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.exit_app)

        menu.addAction(show_picker)
        menu.addAction(show_main)
        menu.addAction(preferences)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._tray_single_click_timer.stop()
            action = self.settings.tray_double_click_action

            if action == "picker":
                self.show_picker(interactive=True)
            elif action == "preferences":
                self.open_preferences_from_tray()
            else:
                self.show_main_window(force_focus=True)
            return

        if reason == QSystemTrayIcon.Trigger:
            # Single click remains a passive quick summon so the original text
            # caret is not stolen.
            self._tray_single_click_timer.start()

    def _on_theme_changed(self, dark: bool, accent: QColor) -> None:
        set_windows_titlebar_dark(self, dark)
        set_windows_titlebar_dark(self.picker, dark)
        self.picker.update()
        self.list.viewport().update()

    def _set_reorder_button_visual(self) -> None:
        self.reorder_btn.setText("\uE73E" if self._reorder_mode else "\uE70F")
        self.reorder_btn.setToolTip(
            "完成顺序调整"
            if self._reorder_mode
            else "调整常用语顺序"
        )
        self.reorder_btn.setProperty("editMode", self._reorder_mode)
        self.reorder_btn.style().unpolish(self.reorder_btn)
        self.reorder_btn.style().polish(self.reorder_btn)
        self.reorder_btn.update()

    def toggle_reorder_mode(self) -> None:
        entering = not self._reorder_mode
        self._reorder_mode = entering

        if entering:
            # Reordering a filtered subset is ambiguous, so enter with the
            # complete phrase list. No native drag/drop mode is enabled.
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
            self.search.setEnabled(False)
        else:
            self.search.setEnabled(True)

        self.list.set_reorder_enabled(entering)
        self._set_reorder_button_visual()

        # Exactly one controlled rebuild when entering/exiting edit mode.
        self.refresh_list()

    def _apply_phrase_order(self, ordered_ids: list[str]) -> None:
        if not self._reorder_mode:
            return

        # The QListWidget is already visually in the requested order.
        # Persist once on mouse release; avoid rebuilding the whole list here.
        self.store.reorder(ordered_ids)

    def _phrase_from_item(self, item: QListWidgetItem | None) -> Phrase | None:
        phrase_id = valid_phrase_id(item)
        return self.store.by_id(phrase_id) if phrase_id else None

    def _selected_phrase(self) -> Phrase | None:
        return self._phrase_from_item(self.list.currentItem())

    def _sync_row_selection(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        if previous is not None:
            previous_widget = self.list.itemWidget(previous)
            if isinstance(previous_widget, PhraseRow):
                previous_widget.set_selected(False)

        if current is not None:
            current_widget = self.list.itemWidget(current)
            if isinstance(current_widget, PhraseRow):
                current_widget.set_selected(True)

    def refresh_list(self) -> None:
        query = self.search.text().strip().lower()
        previous_id = valid_phrase_id(self.list.currentItem())

        self.list.setUpdatesEnabled(False)
        try:
            self.list.clear()
            previous_row = -1
            visible = 0

            for phrase in self.store.phrases:
                searchable = phrase.name.lower()
                if not phrase.hidden:
                    searchable += " " + phrase.text.lower()

                if query and query not in searchable:
                    continue

                item = QListWidgetItem()
                item.setData(Qt.UserRole, phrase.id)
                item.setSizeHint(
                    QSize(0, 66 if self._reorder_mode else 58)
                )

                if self._reorder_mode:
                    title = phrase.name.strip() or "未命名常用语"
                    if phrase.hidden:
                        preview = "••••••"
                    else:
                        preview = " ".join(phrase.text.split())
                        if len(preview) > 28:
                            preview = preview[:28] + "…"

                    # Plain rows are deliberate in reorder mode: no child
                    # widgets, no native drag/drop, no transient drag window.
                    #
                    # IMPORTANT: title and preview live in independent roles.
                    # Never put them into one display string with a newline.
                    # This guarantees hidden preview dots stay on line 2.
                    item.setData(REORDER_NAME_ROLE, title)
                    item.setData(REORDER_PREVIEW_ROLE, preview)
                    item.setData(
                        Qt.AccessibleTextRole,
                        f"{title}：{preview}",
                    )
                    item.setText("")
                    item.setFlags(
                        Qt.ItemIsEnabled | Qt.ItemIsSelectable
                    )
                    self.list.addItem(item)
                else:
                    row = PhraseRow(
                        phrase,
                        reorder_mode=False,
                    )
                    row.copy_requested.connect(self.copy_phrase)
                    row.edit_requested.connect(self.edit_phrase)
                    row.delete_requested.connect(self.delete_phrase)

                    self.list.addItem(item)
                    self.list.setItemWidget(item, row)

                if phrase.id == previous_id:
                    previous_row = visible

                visible += 1

            if not visible:
                if query:
                    item = QListWidgetItem("没有匹配的常用语")
                    item.setFlags(Qt.NoItemFlags)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setSizeHint(QSize(0, 58))
                    self.list.addItem(item)
                else:
                    item = QListWidgetItem()
                    item.setData(EMPTY_STATE_ROLE, True)
                    item.setFlags(Qt.NoItemFlags)

                    # Make the empty-state card tall enough to read as a
                    # centered placeholder instead of a normal list row.
                    viewport_h = max(110, self.list.viewport().height())
                    item.setSizeHint(QSize(0, viewport_h))
                    self.list.addItem(item)
            elif previous_row >= 0:
                self.list.setCurrentRow(previous_row)
            else:
                self.list.setCurrentRow(0)
            # Empty state uses a dedicated centered/bold delegate. Normal
            # phrase rows and reorder mode keep their own delegates.
            if not visible and not query:
                self.list.setItemDelegate(self._empty_delegate)
            else:
                self.list.set_reorder_enabled(self._reorder_mode)

        finally:
            self.list.setUpdatesEnabled(True)

        current = self.list.currentItem()
        if current is not None:
            row = self.list.itemWidget(current)
            if isinstance(row, PhraseRow):
                row.set_selected(True)

        self.count_label.setText(str(len(self.store.phrases)))
        if self._reorder_mode:
            self.status_label.setText("拖动常用语调整顺序 · 点击 ✓ 完成")
        else:
            self.status_label.setText(
                f"{self.settings.hotkey} · 关闭后驻留系统托盘"
            )
        if self.picker.isVisible():
            self.picker.refresh()

    def _main_double_click(self, item: QListWidgetItem) -> None:
        if self._reorder_mode:
            return
        phrase = self._phrase_from_item(item)
        if phrase:
            self.copy_phrase(phrase.id)

    def _show_phrase_context_menu(self, pos: QPoint) -> None:
        if self._reorder_mode:
            return

        item = self.list.itemAt(pos)
        phrase = self._phrase_from_item(item)
        if not phrase:
            return

        self.list.setCurrentItem(item)
        menu = QMenu(self)
        copy_action = menu.addAction("复制")
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")
        chosen = menu.exec(self.list.viewport().mapToGlobal(pos))

        if chosen == copy_action:
            self.copy_phrase(phrase.id)
        elif chosen == edit_action:
            self.edit_phrase(phrase.id)
        elif chosen == delete_action:
            self.delete_phrase(phrase.id)

    def _restore_after_security(self, owner: QWidget) -> None:
        """
        Restore window state after Windows Security closes without visible
        z-order flicker.

        v1.4.2 repaired twice and briefly pulsed the main window through the
        TOPMOST band. That fixed the hidden-window bug but could visibly flash.
        v1.4.3 waits for the Security surface to finish closing, checks the
        actual native state, and only performs one repair when required.
        """
        self._security_restore_generation += 1
        generation = self._security_restore_generation

        def repair_if_needed() -> None:
            if generation != self._security_restore_generation:
                return

            modal = QApplication.activeModalWidget()
            if modal is not None and modal is not owner:
                return

            try:
                if owner is self.picker:
                    if not self.picker.isVisible():
                        return

                    picker_hwnd = int(self.picker.winId())

                    # NOACTIVATE was already restored immediately after the
                    # Hello call. Do not rewrite the native style here.
                    if not is_window_topmost(picker_hwnd):
                        keep_window_topmost_noactivate(picker_hwnd)

                    target = self.picker.target_hwnd
                    if target and foreground_hwnd() != int(target):
                        activate_window(target)

                else:
                    # MainWindow is deliberately left to Windows' normal
                    # owner restoration. Any manual z-order touch here can be
                    # visible as a one-frame flash after PIN cancellation.
                    return
            except Exception:
                pass

        # Windows Security can report the result slightly before its window is
        # fully gone. Waiting once is smoother than repairing immediately and
        # then repairing again.
        QTimer.singleShot(120, repair_if_needed)

    def _show_priority_message(
        self,
        owner: QWidget,
        title: str,
        message: str,
        icon=QMessageBox.Warning,
    ) -> None:
        try:
            if owner is self.picker:
                set_window_no_activate(self.picker, True)
                picker_hwnd = int(self.picker.winId())
                if not is_window_topmost(picker_hwnd):
                    keep_window_topmost_noactivate(picker_hwnd)
            # MainWindow is intentionally not foreground-forced here.
            # The QMessageBox itself will become modal when actually needed.
        except Exception:
            pass

        box = QMessageBox(owner)
        box.setWindowTitle(title)
        box.setIcon(icon)
        box.setText(message)
        box.setStandardButtons(QMessageBox.Ok)
        box.setWindowModality(Qt.WindowModal)

        # The picker is intentionally always-on-top. Its child warning/error
        # dialogs therefore need the same top-most hint so they stay one layer
        # above the picker instead of being hidden behind it.
        box.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        box.show()
        box.raise_()
        box.activateWindow()
        set_windows_titlebar_dark(box, self.theme.dark)
        box.exec()

    def _show_soft_status(self, owner: QWidget, text: str) -> None:
        if owner is self.picker:
            self.picker.show_hint(text)
            return

        self.status_label.setText(text)

        def restore_status_only() -> None:
            if self.status_label.text() == text:
                self.status_label.setText(
                    f"{self.settings.hotkey} · 关闭后驻留系统托盘"
                )

        # Do not call refresh_list(): rebuilding every custom row was another
        # source of visible flashing after canceling Windows Hello.
        QTimer.singleShot(1400, restore_status_only)

    def _verify_hidden(self, phrase: Phrase, action_text: str) -> bool:
        if not phrase.hidden:
            return True

        owner = self.picker if self.picker.isVisible() else self

        ready, resolved_mode, password_just_created = (
            ensure_hidden_security_ready(
                self.settings,
                self.theme,
                owner,
                announce_missing_pin=True,
            )
        )
        if not ready:
            return False

        if resolved_mode == "password":
            # Creating the password requires two matching entries. If this
            # fallback was just created because PIN is unavailable, that setup
            # itself is accepted for the current operation.
            if password_just_created:
                return True

            dialog = SoftwarePasswordVerifyDialog(
                self.settings,
                self.theme,
                action_text,
                owner,
            )
            if owner is self.picker:
                dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)

            if dialog.exec() == QDialog.Accepted:
                return True

            self._show_soft_status(owner, "已取消软件密码验证")
            return False

        # Windows PIN / Hello path.
        owner_hwnd = int(owner.winId())
        picker_security_handoff = owner is self.picker

        if picker_security_handoff:
            set_window_no_activate(self.picker, False)
            force_user_foreground(self.picker)
            QApplication.processEvents()

        ok, message = WindowsHelloVerifier.verify(
            owner_hwnd,
            f"QuickPhrase：验证身份以{action_text}隐藏常用语",
        )

        if picker_security_handoff:
            set_window_no_activate(self.picker, True)
            self._restore_after_security(owner)

        if ok:
            return True

        if "取消" in message:
            self._show_soft_status(owner, "已取消身份验证")
            return False

        self._show_priority_message(
            owner,
            "Windows 安全验证",
            message,
        )
        return False

    def add_phrase(self) -> None:
        dialog = PhraseDialog(self.theme, self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.store.add(dialog.value())
            except Exception as exc:
                self._show_priority_message(self, "保存失败", str(exc), QMessageBox.Critical)
                return
            self.refresh_list()

    def edit_phrase(self, phrase_id: str) -> None:
        phrase = self.store.by_id(phrase_id)
        if not phrase:
            return

        # Editing reveals hidden text, so it is protected too.
        if not self._verify_hidden(phrase, "编辑"):
            return

        if phrase.hidden and not phrase.text:
            owner = self.picker if self.picker.isVisible() else self
            self._show_priority_message(
                owner,
                "无法编辑",
                "该隐藏常用语无法从 Windows DPAPI 解密。原加密数据没有被覆盖。",
            )
            return

        dialog = PhraseDialog(
            self.theme,
            self.settings,
            self,
            phrase,
        )
        if dialog.exec() == QDialog.Accepted:
            try:
                self.store.update(dialog.value())
            except Exception as exc:
                self._show_priority_message(self, "保存失败", str(exc), QMessageBox.Critical)
                return
            self.refresh_list()

    def delete_phrase(self, phrase_id: str) -> None:
        phrase = self.store.by_id(phrase_id)
        if not phrase:
            return

        title = phrase.name.strip() or "未命名常用语"
        owner = self.picker if self.picker.isVisible() else self

        box = QMessageBox(owner)
        box.setWindowTitle("删除常用语")
        box.setIcon(QMessageBox.Question)
        box.setText(f"确定删除“{title}”吗？")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.setWindowModality(Qt.WindowModal)

        # If deletion is triggered from the always-on-top picker, keep the
        # confirmation dialog one level above it.
        if owner is self.picker:
            box.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        set_windows_titlebar_dark(box, self.theme.dark)

        if box.exec() != QMessageBox.Yes:
            return

        # Hidden phrases require the configured security method before the
        # destructive delete is allowed.
        if phrase.hidden and not self._verify_hidden(phrase, "删除"):
            return

        self.store.delete(phrase_id)
        self.refresh_list()

    def copy_phrase(self, phrase_id: str) -> None:
        phrase = self.store.by_id(phrase_id)
        if not phrase:
            return

        if not self._verify_hidden(phrase, "复制"):
            return

        QApplication.clipboard().setText(phrase.text)
        self.status_label.setText("已复制到剪贴板")
        QTimer.singleShot(1100, self.refresh_list)

    def activate_phrase(self, phrase_id: str) -> None:
        phrase = self.store.by_id(phrase_id)
        if not phrase:
            return

        action_text = "自动粘贴" if self.settings.action_mode == "paste" else "复制"
        if not self._verify_hidden(phrase, action_text):
            return

        QApplication.clipboard().setText(phrase.text)

        if self.settings.action_mode == "copy":
            self.picker.hide()
            return

        target = self.picker.target_hwnd
        text_for_clear = phrase.text
        self.picker.hide()

        # Shorter staged delay than v1.1: enough for Windows to restore the
        # previous foreground window, without making the interaction feel slow.
        def focus_target() -> None:
            activate_window(target)

            def paste_now() -> None:
                keyboard.send("ctrl+v")

                if self.settings.clear_clipboard:
                    def clear_if_unchanged() -> None:
                        clipboard = QApplication.clipboard()
                        if clipboard.text() == text_for_clear:
                            clipboard.clear()
                    QTimer.singleShot(500, clear_if_unchanged)

            QTimer.singleShot(65, paste_now)

        QTimer.singleShot(45, focus_target)

    def show_picker(self, interactive: bool = False) -> None:
        self.picker.summon(interactive=interactive)

    def show_main_window(self, force_focus: bool = True) -> None:
        self.showNormal()
        self.raise_()

        if not force_focus:
            return

        force_user_foreground(self)
        hwnd = int(self.winId())

        def refocus_if_needed() -> None:
            if self.isVisible() and foreground_hwnd() != hwnd:
                force_user_foreground(self)

        QTimer.singleShot(140, refocus_if_needed)

    def open_preferences(self, force_focus: bool = False) -> None:
        dialog = PreferencesDialog(
            self.settings,
            self.theme,
            self.apply_preferences,
            self,
        )

        if force_focus:
            def focus_dialog() -> None:
                hwnd = int(dialog.winId())
                force_user_foreground(dialog)

                def retry_if_needed() -> None:
                    if dialog.isVisible() and foreground_hwnd() != hwnd:
                        force_user_foreground(dialog)

                QTimer.singleShot(140, retry_if_needed)

            QTimer.singleShot(0, focus_dialog)

        dialog.exec()

    def open_preferences_from_tray(self) -> None:
        # Keep the main window available as the modal parent, but the
        # Preferences dialog itself becomes the foreground window immediately.
        self.show_main_window(force_focus=True)
        QTimer.singleShot(
            0,
            lambda: self.open_preferences(force_focus=True),
        )

    def apply_preferences(self, values: dict) -> tuple[bool, str]:
        new_hotkey = str(values["hotkey"])
        old_hotkey = self.settings.hotkey

        if new_hotkey != old_hotkey:
            ok, message = self.global_hotkey.register(new_hotkey)
            if not ok:
                self.global_hotkey.register(old_hotkey)
                return False, message

        requested_startup = bool(values.get("startup_enabled", False))
        current_startup = self.settings.startup_enabled
        if requested_startup != current_startup:
            ok, message = set_windows_startup_enabled(requested_startup)
            if not ok:
                if new_hotkey != old_hotkey:
                    self.global_hotkey.register(old_hotkey)
                return False, message

        self.settings.hotkey = new_hotkey
        self.settings.action_mode = str(values["action_mode"])
        self.settings.phrase_trigger_mode = str(
            values.get("phrase_trigger_mode", "single")
        )
        self.settings.clear_clipboard = bool(values["clear_clipboard"])
        self.settings.theme_mode = str(values["theme_mode"])

        close_mode = str(values.get("close_mode", "ask"))
        if close_mode == "ask":
            self.settings.close_prompt_suppressed = False
            # Keep the last action value only as a harmless fallback.
        elif close_mode in {"minimize", "exit"}:
            self.settings.close_action = close_mode
            self.settings.close_prompt_suppressed = True

        self.settings.tray_double_click_action = str(
            values.get("tray_double_click_action", "main")
        )
        self.settings.security_mode = str(
            values.get("security_mode", self.settings.security_mode)
        )

        self.theme.apply(self.settings.theme_mode)
        self.refresh_list()
        return True, ""

    def _minimize_to_tray_from_close(self, event) -> None:
        event.ignore()
        self.hide()

    def _exit_from_close(self, event) -> None:
        self._allow_exit = True
        self.settings.save_main_geometry(self.saveGeometry())
        self.settings.save_picker_pos(self.picker.pos())
        self.global_hotkey.unregister()
        self.tray.hide()
        self.picker.close()
        event.accept()
        QTimer.singleShot(0, QApplication.quit)

    def closeEvent(self, event) -> None:
        self.settings.save_main_geometry(self.saveGeometry())

        if self._allow_exit:
            self.global_hotkey.unregister()
            event.accept()
            return

        # Without a system tray there is nowhere useful to minimize to.
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._exit_from_close(event)
            return

        # "不再提示" remembers the last selected action.
        if self.settings.close_prompt_suppressed:
            if self.settings.close_action == "exit":
                self._exit_from_close(event)
            else:
                self._minimize_to_tray_from_close(event)
            return

        dialog = CloseActionDialog(self.theme, self)
        result = dialog.exec()

        # Closing the confirmation itself means "cancel closing QuickPhrase".
        if result != QDialog.Accepted or dialog.choice not in {"minimize", "exit"}:
            event.ignore()
            return

        self.settings.close_action = dialog.choice
        self.settings.close_prompt_suppressed = dialog.dont_ask.isChecked()

        if dialog.choice == "exit":
            self._exit_from_close(event)
        else:
            self._minimize_to_tray_from_close(event)

    def exit_app(self) -> None:
        # Explicit tray "退出" always exits immediately and never shows the
        # title-bar close confirmation.
        self._allow_exit = True
        self.settings.save_main_geometry(self.saveGeometry())
        self.settings.save_picker_pos(self.picker.pos())
        self.global_hotkey.unregister()
        self.tray.hide()
        self.picker.close()
        QApplication.quit()


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setQuitOnLastWindowClosed(False)

    # QP.ico becomes the default icon for every top-level QuickPhrase window
    # and dialog. The tray explicitly reuses the same QIcon.
    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    font = QFont("Segoe UI Variable Text")
    font.setPointSizeF(10.5)
    app.setFont(font)

    settings = AppSettings()
    theme = ThemeManager(settings)
    theme.apply()

    window = MainWindow(settings, theme)

    # Windows Run / Inno Setup starts QuickPhrase with --startup so boot/login
    # never opens a distracting main window. The tray icon and global hotkey
    # are already initialized by MainWindow.
    if "--startup" in sys.argv[1:]:
        window.hide()
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
