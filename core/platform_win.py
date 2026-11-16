"""Увесь Windows API в одному місці. На інших системах функції тихо нічого не роблять —
так решту програми можна перевіряти без Windows."""

import ctypes
import os
import sys

IS_WIN = sys.platform == "win32"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "WidgetDesk"

SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
HWND_BOTTOM, HWND_TOPMOST, HWND_NOTOPMOST = 1, -1, -2
DESKTOP_CLASSES = ("WorkerW", "Progman")

if IS_WIN:
    from ctypes import wintypes

    u32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = wintypes.HWND
    ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    u32.FindWindowW.restype = HWND
    u32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    u32.FindWindowExW.restype = HWND
    u32.FindWindowExW.argtypes = [HWND, HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    u32.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]
    u32.SendMessageTimeoutW.argtypes = [HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    u32.SetParent.restype = HWND
    u32.SetParent.argtypes = [HWND, HWND]
    u32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 wintypes.UINT]
    u32.GetForegroundWindow.restype = HWND
    u32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
    u32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(wintypes.RECT)]
    u32.MonitorFromWindow.restype = wintypes.HANDLE
    u32.MonitorFromWindow.argtypes = [HWND, wintypes.DWORD]
    u32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
    u32.GetSystemMetrics.argtypes = [ctypes.c_int]
    u32.RegisterWindowMessageW.restype = wintypes.UINT
    u32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]


# ---------------- шари вікон ----------------
def find_wallpaper_parent():
    """Вікно, що лежить ПІД іконками робочого стола. Повертає (hwnd або None, опис способу)."""
    if not IS_WIN:
        return None, "не Windows"
    progman = u32.FindWindowW("Progman", None)
    if not progman:
        return None, "не знайдено Progman"
    res = ctypes.c_size_t(0)
    for wp, lp in ((0xD, 0x1), (0, 0)):
        u32.SendMessageTimeoutW(progman, 0x052C, wp, lp, 0, 1000, ctypes.byref(res))
    found = []

    def cb(top, _):
        if u32.FindWindowExW(top, None, "SHELLDLL_DefView", None):
            w = u32.FindWindowExW(None, top, "WorkerW", None)
            if w:
                found.append(w)
        return True

    u32.EnumWindows(ENUMPROC(cb), 0)
    if found:
        return found[0], "WorkerW"
    return progman, "Progman"


def attach_under_icons(hwnd):
    """Покласти вікно під іконки на весь головний монітор. Повертає опис способу або ''."""
    parent, how = find_wallpaper_parent()
    if not parent:
        return ""
    u32.SetParent(hwnd, parent)
    x, y = -u32.GetSystemMetrics(76), -u32.GetSystemMetrics(77)
    u32.SetWindowPos(hwnd, None, x, y, u32.GetSystemMetrics(0), u32.GetSystemMetrics(1), SWP_NOACTIVATE)
    return how


def set_z(hwnd, after):
    if IS_WIN:
        u32.SetWindowPos(hwnd, after, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def send_to_bottom(hwnd):
    set_z(hwnd, HWND_BOTTOM)


def taskbar_created_message():
    """Номер повідомлення, яке Windows розсилає після перезапуску Провідника (треба приєднатись знову)."""
    return u32.RegisterWindowMessageW("TaskbarCreated") if IS_WIN else 0


# ---------------- що зараз на екрані ----------------
def foreground_class():
    if not IS_WIN:
        return ""
    buf = ctypes.create_unicode_buffer(64)
    u32.GetClassNameW(u32.GetForegroundWindow(), buf, 64)
    return buf.value


def desktop_is_foreground():
    return foreground_class() in DESKTOP_CLASSES


def fullscreen_app_active():
    """True, якщо активне вікно займає весь монітор (гра, відео на весь екран)."""
    if not IS_WIN:
        return False
    hwnd = u32.GetForegroundWindow()
    if not hwnd:
        return False
    buf = ctypes.create_unicode_buffer(64)
    u32.GetClassNameW(hwnd, buf, 64)
    if buf.value in DESKTOP_CLASSES + ("Shell_TrayWnd", ""):
        return False
    r = wintypes.RECT()
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not u32.GetWindowRect(hwnd, ctypes.byref(r)):
        return False
    if not u32.GetMonitorInfoW(u32.MonitorFromWindow(hwnd, 2), ctypes.byref(mi)):
        return False
    m = mi.rcMonitor
    return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom


# ---------------- автозапуск ----------------
def autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    return f'"{exe}" "{os.path.abspath(sys.argv[0])}"'


def is_autostart():
    if not IS_WIN:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
            return True
    except OSError:
        return False


def set_autostart(on):
    if not IS_WIN:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
            else:
                try:
                    winreg.DeleteValue(k, RUN_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def open_folder(path):
    if IS_WIN:
        os.startfile(str(path))


# ---------------- шпалери Windows (для розмитого «скла») ----------------
def wallpaper_info():
    """(шлях до файла шпалер, режим: fill / fit / stretch). Порожній шлях, якщо не вдалося."""
    if not IS_WIN:
        return "", "fill"
    buf = ctypes.create_unicode_buffer(520)
    try:
        ctypes.windll.user32.SystemParametersInfoW(0x0073, 520, buf, 0)      # SPI_GETDESKWALLPAPER
    except Exception:
        return "", "fill"
    mode = "fill"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as k:
            style = str(winreg.QueryValueEx(k, "WallpaperStyle")[0])
        mode = {"2": "stretch", "6": "fit"}.get(style, "fill")
    except OSError:
        pass
    return buf.value, mode


# ---------------- гаряча клавіша на весь Windows ----------------
from PyQt6.QtCore import QObject, pyqtSignal  # noqa: E402


class GlobalHotkey(QObject):
    """RegisterHotKey у власному потоці. bindings: {"назва": ("ctrl+shift", код_клавіші)}"""
    pressed = pyqtSignal(str)
    MOD = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}

    def __init__(self, bindings):
        super().__init__()
        self.bindings = bindings
        self.failed = []
        if IS_WIN:
            import threading
            threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        from ctypes import wintypes as wt
        user32 = ctypes.windll.user32
        names = list(self.bindings)
        for i, name in enumerate(names, start=1):
            mods_s, vk = self.bindings[name]
            mods = 0x4000                                   # без автоповтору
            for m in mods_s.split("+"):
                mods |= self.MOD.get(m.strip().lower(), 0)
            if not user32.RegisterHotKey(None, i, mods, vk):
                self.failed.append(name)
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:
                idx = int(msg.wParam) - 1
                if 0 <= idx < len(names):
                    self.pressed.emit(names[idx])
