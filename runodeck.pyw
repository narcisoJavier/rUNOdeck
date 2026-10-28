import os
import sys
import json
import time
import threading
import subprocess
import webbrowser
import winreg
import ctypes
import serial
import serial.tools.list_ports
import pyautogui
import webview
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageOps

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

BAUD_RATE = 115200
CREATE_NO_WINDOW = 0x08000000

WORKDIR = r"c:\Users\UZNIR\Documents\antigravity\serene-meitner"
CONFIG_PATH = os.path.join(WORKDIR, "runodeck_config.json")
GUI_PATH = os.path.join(WORKDIR, "gui", "index.html")
LOGO_PNG_PATH = os.path.join(WORKDIR, "gui", "logo.png")
ICO_PATH = os.path.join(WORKDIR, "runodeck.ico")
SET_AUDIO_EXE = os.path.join(WORKDIR, "SetAudioDevice.exe")

# Set Windows AppUserModelID so the taskbar uses our custom icon instead of pythonw's default
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("uznir.runodeck.controller.3")
except Exception:
    pass

is_enabled = True
running = True
is_serial_connected = False
current_port_name = "COM7"
current_stick_mode = "MEDIA"
active_serial = None
main_window = None
tray_icon = None
is_window_maximized = False
mouse_rem_x = 0.0
mouse_rem_y = 0.0

DEFAULT_CONFIG = {
    "keys": {
        "1": { "name": "Mute Mic", "type": "hotkey", "target": "ctrl+shift+m" },
        "2": { "name": "Screenshot", "type": "hotkey", "target": "win+shift+s" },
        "3": { "name": "Copy", "type": "hotkey", "target": "ctrl+c" },
        "4": { "name": "Paste", "type": "hotkey", "target": "ctrl+v" },
        "5": { "name": "Spotify", "type": "app", "target": "spotify:" },
        "6": { "name": "YouTube", "type": "url", "target": "https://youtube.com" },
        "7": { "name": "Prev Desktop", "type": "hotkey", "target": "ctrl+win+left" },
        "8": { "name": "Next Desktop", "type": "hotkey", "target": "ctrl+win+right" },
        "9": { "name": "Calculator", "type": "app", "target": "calc" },
        "0": { "name": "Mute Audio", "type": "media", "target": "volumemute" },
        "A": { "name": "Task Manager", "type": "hotkey", "target": "ctrl+shift+esc" },
        "B": { "name": "Alt + Tab", "type": "hotkey", "target": "alt+tab" },
        "C": { "name": "File Explorer", "type": "hotkey", "target": "win+e" },
        "D": { "name": "Show Desktop", "type": "hotkey", "target": "win+d" },
        "#": { "name": "Play / Pause", "type": "media", "target": "playpause" }
    },
    "combos": {
        "1": { "name": "Discord", "type": "app", "target": "discord:" },
        "2": { "name": "VS Code", "type": "app", "target": "code" },
        "3": { "name": "Terminal", "type": "app", "target": "wt" },
        "4": { "name": "Speakers Output", "type": "audio", "target": "Speakers" },
        "5": { "name": "Headphones Output", "type": "audio", "target": "Headphones" },
        "6": { "name": "GitHub", "type": "url", "target": "https://github.com" },
        "C": { "name": "Earphone Jack", "type": "audio", "target": "Earphone" },
        "7": { "name": "ChatGPT", "type": "url", "target": "https://chatgpt.com" },
        "8": { "name": "Antigravity", "type": "app", "target": os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Antigravity.lnk") },
        "9": { "name": "OpenCode", "type": "app", "target": os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\OpenCode.lnk") },
        "0": { "name": "Toggle LCD / LEDs", "type": "device", "target": "toggle_led" }
    },
    "joystick_bindings": {
        "UP": { "name": "Volume Up (Hold)", "type": "media", "target": "volumeup" },
        "DOWN": { "name": "Volume Down (Hold)", "type": "media", "target": "volumedown" },
        "LEFT": { "name": "Previous Tab", "type": "hotkey", "target": "ctrl+shift+tab" },
        "RIGHT": { "name": "Next Tab", "type": "hotkey", "target": "ctrl+tab" }
    }
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if "combos" not in loaded:
                    loaded["combos"] = {}
                for k, v in DEFAULT_CONFIG["combos"].items():
                    if k not in loaded["combos"]:
                        loaded["combos"][k] = v
                if "joystick_bindings" not in loaded:
                    loaded["joystick_bindings"] = {}
                for k, v in DEFAULT_CONFIG["joystick_bindings"].items():
                    if k not in loaded["joystick_bindings"]:
                        loaded["joystick_bindings"][k] = v
                return loaded
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config_file(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")

config_data = load_config()

def switch_audio(keyword):
    if os.path.exists(SET_AUDIO_EXE):
        try:
            subprocess.Popen(
                [SET_AUDIO_EXE, keyword],
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"Audio switch error: {e}")

def launch_target_silently(target):
    expanded = os.path.expandvars(target)
    if os.path.exists(expanded):
        os.startfile(expanded)
    else:
        try:
            os.startfile(target)
        except Exception:
            subprocess.Popen(
                ["cmd", "/c", "start", "", target],
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

def send_serial_command(cmd_str):
    global active_serial
    if active_serial and active_serial.is_open:
        try:
            active_serial.write((cmd_str.strip() + "\n").encode("utf-8"))
        except Exception:
            pass

def send_lcd_toast(action_type, label):
    if not label:
        return
    clean = str(label).replace("|", " ").strip()
    if action_type in ("app", "url"):
        tag = "   [OPEN]"
        line2 = f"Open: {clean}" if len(clean) <= 10 else clean[:16]
    elif action_type == "audio":
        tag = "  [AUDIO]"
        line2 = f"Out: {clean}" if len(clean) <= 11 else clean[:16]
    else:
        tag = "  [MACRO]"
        line2 = clean[:16]
    send_serial_command(f"LCD: {tag}|{line2[:16]}")

def execute_generic_action(action_type, target, label=None):
    if not target or not is_enabled:
        return

    if label and action_type != "device":
        send_lcd_toast(action_type, label)

    try:
        if action_type == "hotkey":
            keys = [k.strip() for k in target.lower().split("+")]
            pyautogui.hotkey(*keys)
        elif action_type == "app":
            launch_target_silently(target)
        elif action_type == "url":
            url = target if target.startswith("http") else "https://" + target
            webbrowser.open(url)
        elif action_type == "media":
            pyautogui.press(target.lower())
        elif action_type == "audio":
            switch_audio(target)
        elif action_type == "device":
            if target.lower() == "toggle_led":
                send_serial_command("CMD: TOGGLE_LED")
            elif target.lower() == "cycle_mode":
                send_serial_command("CMD: CYCLE_MODE")
        elif action_type == "text":
            pyautogui.write(target)
    except Exception as e:
        print(f"Error executing action ({action_type}: {target}): {e}")

def get_installed_audio_devices():
    devices = []
    render_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
    try:
        hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, render_path)
        for i in range(winreg.QueryInfoKey(hkey)[0]):
            guid = winreg.EnumKey(hkey, i)
            try:
                dev_key = winreg.OpenKey(hkey, guid)
                state, _ = winreg.QueryValueEx(dev_key, "DeviceState")
                if state == 1:
                    prop_key = winreg.OpenKey(hkey, guid + r"\Properties")
                    name, _ = winreg.QueryValueEx(prop_key, "{a45c254e-df1c-4efd-8020-67d146a850e0},2")
                    devices.append({"id": guid, "name": name})
            except Exception:
                pass
    except Exception:
        pass
    return devices

class BridgeApi:
    def get_config(self):
        return config_data

    def save_config(self, new_cfg):
        global config_data
        config_data = new_cfg
        save_config_file(new_cfg)
        return True

    def get_audio_devices(self):
        return get_installed_audio_devices()

    def execute_action(self, action_type, target, label=None):
        execute_generic_action(action_type, target, label)
        return True

    def get_hardware_status(self):
        return {
            "connected": is_serial_connected,
            "port": current_port_name,
            "mode": current_stick_mode
        }

    def calibrate_joystick(self):
        send_serial_command("CMD: CALIBRATE")
        return True

    def set_joystick_mode(self, mode_name):
        global current_stick_mode
        m = (mode_name or "MEDIA").upper()
        if m in ("MEDIA", "MOUSE", "SCROLL"):
            current_stick_mode = m
            send_serial_command(f"CMD: MODE_{m}")
        return True

    def window_minimize(self):
        if main_window:
            main_window.minimize()
        return True

    def window_maximize(self):
        global is_window_maximized
        if main_window:
            if is_window_maximized:
                main_window.restore()
                is_window_maximized = False
            else:
                main_window.maximize()
                is_window_maximized = True
        return is_window_maximized

    def window_close(self):
        if main_window:
            main_window.hide()
        return True

def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = (port.description or "").upper()
        hwid = (port.hwid or "").upper()
        if any(k in desc for k in ["ARDUINO", "CH340", "USB-SERIAL", "USB SERIAL", "SILICON LABS", "FTDI", "CP210"]):
            return port.device
        if any(vid in hwid for vid in ["1A86:", "2341:", "2A03:", "0403:", "10C4:"]):
            return port.device
    non_system_ports = [p.device for p in ports if p.device.upper() != "COM1"]
    if non_system_ports:
        return non_system_ports[0]
    return "COM7"

def notify_ui(js_code):
    global main_window
    if main_window:
        try:
            main_window.evaluate_js(js_code)
        except Exception:
            pass

def serial_worker():
    global running, is_serial_connected, current_port_name, active_serial
    ser = None

    while running:
        if ser is None:
            port = find_arduino_port()
            current_port_name = port
            try:
                ser = serial.Serial(port, BAUD_RATE, timeout=0.02)
                active_serial = ser
                is_serial_connected = True
                notify_ui(f"window.onHardwareStatus && window.onHardwareStatus(true, '{port}')")
            except Exception:
                active_serial = None
                is_serial_connected = False
                notify_ui(f"window.onHardwareStatus && window.onHardwareStatus(false, '{port}')")
                time.sleep(1.5)
                continue

        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    handle_hardware_line(line)
            else:
                time.sleep(0.004)
        except (serial.SerialException, OSError):
            active_serial = None
            is_serial_connected = False
            notify_ui(f"window.onHardwareStatus && window.onHardwareStatus(false, '{current_port_name}')")
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(1.0)

HARDWARE_COMBO_MAP = {
    "AUDIO: SPEAKERS": "4",
    "AUDIO: HEADPHONES": "5",
    "AUDIO: EARPHONES": "C",
    "APP: CHATGPT": "7",
    "APP: ANTIGRAVITY": "8",
    "APP: OPENCODE": "9"
}

def handle_hardware_line(command):
    global current_stick_mode

    if command == "READY":
        notify_ui(f"window.onHardwareStatus && window.onHardwareStatus(true, '{current_port_name}')")
        return

    if command.startswith("LED: "):
        notify_ui("window.onComboTriggered && window.onComboTriggered('0')")
        return

    if command in HARDWARE_COMBO_MAP:
        combo_key = HARDWARE_COMBO_MAP[command]
        notify_ui(f"window.onComboTriggered && window.onComboTriggered('{combo_key}')")
        cfg = config_data.get("combos", {}).get(combo_key)
        if cfg:
            execute_generic_action(cfg.get("type"), cfg.get("target"), cfg.get("name"))
        return

    if command.startswith("KEY: "):
        key_id = command.replace("KEY: ", "").strip()
        notify_ui(f"window.onPhysicalKeyPress && window.onPhysicalKeyPress('{key_id}')")
        cfg = config_data.get("keys", {}).get(key_id)
        if cfg:
            execute_generic_action(cfg.get("type"), cfg.get("target"), cfg.get("name"))

    elif command.startswith("COMBO: "):
        combo_key = command.replace("COMBO: ", "").strip()
        notify_ui(f"window.onComboTriggered && window.onComboTriggered('{combo_key}')")
        cfg = config_data.get("combos", {}).get(combo_key)
        if cfg:
            execute_generic_action(cfg.get("type"), cfg.get("target"), cfg.get("name"))

    elif command.startswith("TELEM: "):
        coords = command.replace("TELEM: ", "").split(",")
        try:
            nx = int(coords[0])
            ny = int(coords[1])
            notify_ui(f"window.onJoystickTelemetry && window.onJoystickTelemetry({nx}, {ny})")
        except Exception:
            pass

    elif command.startswith("CALIBRATED: "):
        coords = command.replace("CALIBRATED: ", "").split(",")
        try:
            cx = int(coords[0])
            cy = int(coords[1])
            notify_ui(f"window.onJoystickCalibrated && window.onJoystickCalibrated({cx}, {cy})")
        except Exception:
            pass

    elif command.startswith("MOUSE: VEC ") or command.startswith("MOUSE: MOVE "):
        global mouse_rem_x, mouse_rem_y
        if not is_enabled:
            return
        prefix = "MOUSE: VEC " if command.startswith("MOUSE: VEC ") else "MOUSE: MOVE "
        coords = command.replace(prefix, "").split(",")
        try:
            mx = float(coords[0])
            my = float(coords[1])
            if prefix == "MOUSE: VEC ":
                nx = max(-1.0, min(1.0, mx / 100.0))
                ny = max(-1.0, min(1.0, my / 100.0))
                vx = (0.22 * nx + 0.78 * nx * abs(nx)) * 10.5
                vy = (0.22 * ny + 0.78 * ny * abs(ny)) * 10.5
            else:
                vx = mx * 0.65
                vy = my * 0.65
            mouse_rem_x += vx
            mouse_rem_y += vy
            step_x = int(mouse_rem_x)
            step_y = int(mouse_rem_y)
            if step_x != 0 or step_y != 0:
                mouse_rem_x -= step_x
                mouse_rem_y -= step_y
                ctypes.windll.user32.mouse_event(0x0001, step_x, step_y, 0, 0)
        except Exception:
            pass

    elif command == "MOUSE: CLICK":
        if is_enabled:
            ctypes.windll.user32.mouse_event(0x0002 | 0x0004, 0, 0, 0, 0)
    elif command == "MOUSE: MIDCLICK":
        if is_enabled:
            ctypes.windll.user32.mouse_event(0x0020 | 0x0040, 0, 0, 0, 0)

    elif command.startswith("SCROLL: "):
        if not is_enabled:
            return
        try:
            sy = float(command.replace("SCROLL: ", "").strip())
            ny = max(-1.0, min(1.0, sy / 100.0))
            wheel_delta = int((0.30 * ny + 0.70 * ny * abs(ny)) * 95.0)
            if wheel_delta != 0:
                ctypes.windll.user32.mouse_event(0x0800, 0, 0, wheel_delta, 0)
        except Exception:
            pass

    elif command in ("JOY: UP", "JOY: DOWN", "JOY: TAB_LEFT", "JOY: TAB_RIGHT"):
        dir_map = {
            "JOY: UP": "UP",
            "JOY: DOWN": "DOWN",
            "JOY: TAB_LEFT": "LEFT",
            "JOY: TAB_RIGHT": "RIGHT"
        }
        dir_key = dir_map[command]
        notify_ui(f"window.onJoystickDirection && window.onJoystickDirection('{dir_key}')")
        jb = config_data.get("joystick_bindings", {}).get(dir_key)
        if jb:
            execute_generic_action(jb.get("type"), jb.get("target"))
    elif command == "JOY: CLICK":
        pyautogui.press('playpause')

    elif command.startswith("MODE: "):
        m = command.replace("MODE: ", "").strip()
        current_stick_mode = m
        notify_ui(f"window.onModeChange && window.onModeChange('{m}')")

def create_tray_image(active=True):
    if os.path.exists(LOGO_PNG_PATH):
        try:
            img = Image.open(LOGO_PNG_PATH).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
            if not active:
                gray = ImageOps.grayscale(img).convert("RGBA")
                return gray
            return img
        except Exception:
            pass
    img = Image.new('RGBA', (64, 64), (20, 24, 33, 255))
    return img

def show_window(icon=None, item=None):
    global main_window
    if main_window:
        main_window.show()
        main_window.restore()

def toggle_enable(icon, item):
    global is_enabled
    is_enabled = not is_enabled
    icon.icon = create_tray_image(is_enabled)
    icon.title = f"rUNOdeck: {'Active' if is_enabled else 'Paused'}"

def on_tray_exit(icon, item):
    global running, main_window
    running = False
    if main_window:
        main_window.destroy()
    icon.stop()
    os._exit(0)

def setup_tray():
    global tray_icon
    menu = pystray.Menu(
        item("Open rUNOdeck", show_window, default=True),
        item(lambda text: f"Status: {'Active' if is_enabled else 'Paused'}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        item(lambda text: "Pause rUNOdeck" if is_enabled else "Resume rUNOdeck", toggle_enable),
        pystray.Menu.SEPARATOR,
        item("Exit rUNOdeck", on_tray_exit)
    )
    tray_icon = pystray.Icon("rUNOdeck", create_tray_image(True), "rUNOdeck Controller", menu)
    tray_icon.run()

def on_closing():
    global main_window
    if main_window:
        main_window.hide()
    return False

def apply_window_icon():
    if not os.path.exists(ICO_PATH):
        return
    time.sleep(0.6)
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, "rUNOdeck")
        if hwnd:
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1
            LR_LOADFROMFILE = 0x00000010
            IMAGE_ICON = 1
            hicon_big = ctypes.windll.user32.LoadImageW(0, ICO_PATH, IMAGE_ICON, 256, 256, LR_LOADFROMFILE)
            hicon_small = ctypes.windll.user32.LoadImageW(0, ICO_PATH, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            if hicon_big:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
            if hicon_small:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
    except Exception:
        pass

def cleanup_stale_instances():
    my_pid = os.getpid()
    ps_cmd = (
        f"Get-CimInstance Win32_Process | Where-Object {{ $_.ProcessId -ne {my_pid} -and "
        f"($_.Name -like 'python*') -and ($_.CommandLine -like '*runodeck.pyw*') }} | "
        f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd],
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3
        )
    except Exception:
        pass

def main():
    global main_window

    cleanup_stale_instances()

    serial_th = threading.Thread(target=serial_worker, daemon=True)
    serial_th.start()

    tray_th = threading.Thread(target=setup_tray, daemon=True)
    tray_th.start()

    icon_th = threading.Thread(target=apply_window_icon, daemon=True)
    icon_th.start()

    api = BridgeApi()
    main_window = webview.create_window(
        title="rUNOdeck",
        url=GUI_PATH,
        js_api=api,
        width=1140,
        height=740,
        min_size=(900, 600),
        frameless=True,
        easy_drag=False,
        resizable=True,
        background_color="#EAE9E4"
    )

    main_window.events.closing += on_closing
    webview.start(debug=False)

if __name__ == "__main__":
    main()
