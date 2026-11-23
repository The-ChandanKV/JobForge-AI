"""Dispatch a local, count-only notification through the Windows Shell."""
import argparse
import os
import sys


def notify(message):
    if sys.platform != "win32":
        return "unsupported_platform"
    import ctypes
    from ctypes import wintypes as win

    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    window_proc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, win.HWND, win.UINT, win.WPARAM, win.LPARAM)
    callback_message, timer_message = 0x8001, 0x0113
    balloon_show, balloon_click = 0x0402, 0x0405

    class WindowClass(ctypes.Structure):
        _fields_ = [("style", win.UINT), ("proc", window_proc), ("class_extra", ctypes.c_int),
                    ("window_extra", ctypes.c_int), ("instance", win.HINSTANCE), ("icon", win.HANDLE),
                    ("cursor", win.HANDLE), ("background", win.HANDLE), ("menu", win.LPCWSTR),
                    ("name", win.LPCWSTR)]

    class NotifyIcon(ctypes.Structure):
        _fields_ = [("size", win.DWORD), ("window", win.HWND), ("identity", win.UINT), ("flags", win.UINT),
                    ("callback", win.UINT), ("icon", win.HANDLE), ("tip", win.WCHAR * 128),
                    ("state", win.DWORD), ("state_mask", win.DWORD), ("body", win.WCHAR * 256),
                    ("timeout", win.UINT), ("title", win.WCHAR * 64), ("info_flags", win.DWORD),
                    ("guid", win.DWORD * 4), ("balloon_icon", win.HANDLE)]

    def define(dll, name, result, *args):
        fn = getattr(dll, name)
        fn.restype = result
        fn.argtypes = args
        return fn

    default = define(user, "DefWindowProcW", ctypes.c_ssize_t, win.HWND, win.UINT, win.WPARAM, win.LPARAM)
    quit_loop = define(user, "PostQuitMessage", None, ctypes.c_int)
    state = "shell_did_not_report_shown"

    @window_proc
    def receive(window, event, wparam, lparam):
        nonlocal state
        if event == callback_message and lparam == balloon_show:
            state = "shell_reported_shown"
            return 0
        if event == callback_message and lparam == balloon_click:
            state = "clicked"
            try:
                os.startfile("http://127.0.0.1:8000/approvals")
            except OSError:
                pass
            quit_loop(0)
            return 0
        if event == timer_message:
            quit_loop(0)
            return 0
        return default(window, event, wparam, lparam)

    instance = define(kernel, "GetModuleHandleW", win.HMODULE, win.LPCWSTR)(None)
    register = define(user, "RegisterClassW", win.WORD, ctypes.POINTER(WindowClass))
    create = define(user, "CreateWindowExW", win.HWND, win.DWORD, win.LPCWSTR, win.LPCWSTR, win.DWORD,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, win.HWND, win.HMENU,
                    win.HINSTANCE, win.LPVOID)
    load_icon = define(user, "LoadIconW", win.HANDLE, win.HINSTANCE, ctypes.c_void_p)
    tray = define(shell, "Shell_NotifyIconW", win.BOOL, win.DWORD, ctypes.POINTER(NotifyIcon))
    set_timer = define(user, "SetTimer", ctypes.c_size_t, win.HWND, ctypes.c_size_t, win.UINT, win.LPVOID)
    destroy = define(user, "DestroyWindow", win.BOOL, win.HWND)
    get_message = define(user, "GetMessageW", win.BOOL, ctypes.POINTER(win.MSG), win.HWND, win.UINT, win.UINT)
    dispatch = define(user, "DispatchMessageW", ctypes.c_ssize_t, ctypes.POINTER(win.MSG))
    name = "JobForgeLocalNotice"
    wc = WindowClass(proc=receive, instance=instance, name=name)
    if not register(ctypes.byref(wc)):
        return "notification_window_unavailable"
    window = create(0, name, "JobForge AI", 0, 0, 0, 0, 0, None, None, instance, None)
    if not window:
        return "notification_window_unavailable"
    notification = NotifyIcon(size=ctypes.sizeof(NotifyIcon), window=window, identity=1, flags=0x07,
                              callback=callback_message, icon=load_icon(None, 32516), tip="JobForge AI")
    try:
        if not tray(0, ctypes.byref(notification)):
            return "shell_notification_area_unavailable"
        notification.flags = 0x10
        notification.body = message[:220]
        notification.title = "JobForge AI"
        notification.info_flags = 0x01
        if not tray(1, ctypes.byref(notification)) or not set_timer(window, 1, 15000, None):
            return "shell_rejected_notification"
        item = win.MSG()
        while get_message(ctypes.byref(item), None, 0, 0) > 0:
            dispatch(ctypes.byref(item))
        return state
    finally:
        tray(2, ctypes.byref(notification))
        destroy(window)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("message")
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    try:
        result = notify(args.message)
    except (AttributeError, OSError, ValueError):
        result = "windows_notification_error"
    if args.record:
        from .models import Log, Session
        with Session.begin() as db:
            db.add(Log(kind="desktop_delivery", message="Windows notification delivery checked", detail={"result": result}))
    else:
        print(result)


if __name__ == "__main__":
    main()
