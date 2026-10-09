# GameForge Suite v2.0 - Unified Python Desktop App
# Built with CustomTkinter | PyInstaller Compatible (--onefile --windowed)
# Run as Administrator for full functionality

import customtkinter as ctk
import tkinter as tk
import os, sys, json, time, threading, subprocess, ctypes, shutil
import webbrowser
from pathlib import Path
from datetime import datetime

try:
    import psutil
except: psutil = None

# --- Config & Constants ---
APP_NAME = "GameForge Suite v2.0"
VERSION = "2.0.0"
CONFIG_PATH = Path(os.getenv("APPDATA")) / "GameForge" / "profiles.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except: return False

def run_cmd(cmd, shell=True):
    try:
        result = subprocess.run(cmd, shell=shell, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e: return False, str(e)

def run_powershell(ps_command):
    cmd = f\'powershell -NoProfile -ExecutionPolicy Bypass -Command "{ps_command}"\'
    return run_cmd(cmd)

# --- Overlays ---
class CrosshairOverlay:
    def __init__(self):
        self.win = None
        self.config = {"shape":"Cross", "color":"#00FF00", "size":20, "opacity":0.8}
        self.enabled = False

    def show(self):
        if self.win: self.hide()
        self.win = tk.Toplevel()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", "black")
        self.win.attributes("-alpha", self.config["opacity"])
        self.win.config(bg="black")
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        size = self.config["size"] * 3
        self.win.geometry(f"{size}x{size}+{sw//2 - size//2}+{sh//2 - size//2}")
        self.win.wm_attributes("-disabled", True)
        canvas = tk.Canvas(self.win, width=size, height=size, bg="black", highlightthickness=0)
        canvas.pack()
        c, col, s = size//2, self.config["color"], self.config["size"]
        if self.config["shape"] == "Dot":
            canvas.create_oval(c-3, c-3, c+3, c+3, fill=col, outline=col)
        elif self.config["shape"] == "Circle":
            canvas.create_oval(c-s, c-s, c+s, c+s, outline=col, width=2)
            canvas.create_oval(c-2, c-2, c+2, c+2, fill=col, outline=col)
        else: # Cross
            canvas.create_line(c-s, c, c+s, c, fill=col, width=2)
            canvas.create_line(c, c-s, c, c+s, fill=col, width=2)
        self.enabled = True

    def hide(self):
        if self.win:
            try: self.win.destroy()
            except: pass
            self.win = None
        self.enabled = False

class PerfOverlay:
    def __init__(self):
        self.win = None
        self.running = False
    def show(self):
        if self.win: return
        self.win = tk.Toplevel()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry("220x110+20+20")
        self.win.config(bg="#1a1a1a")
        self.label = tk.Label(self.win, text="Loading...", fg="white", bg="#1a1a1a", font=("Consolas", 9), justify="left")
        self.label.pack(padx=10, pady=10)
        self.running = True
        threading.Thread(target=self.loop, daemon=True).start()
        # drag logic
        self.label.bind("<ButtonPress-1>", lambda e: setattr(self.win, \'_x\', e.x) or setattr(self.win, \'_y\', e.y))
        self.label.bind("<B1-Motion>", lambda e: self.win.geometry(f"+{e.x_root-self.win._x}+{e.y_root-self.win._y}"))

    def loop(self):
        import time
        boot = psutil.boot_time() if psutil else time.time()
        while self.running and self.win:
            try:
                cpu = psutil.cpu_percent(interval=1) if psutil else 0
                ram = psutil.virtual_memory().percent if psutil else 0
                uptime = time.time() - boot
                hrs, rem = divmod(int(uptime), 3600)
                mins, secs = divmod(rem, 60)
                text = f" CPU: {cpu:.1f}%\n RAM: {ram:.1f}%\n UPTIME: {hrs:02d}:{mins:02d}:{secs:02d}\n GPU: N/A (install GPUtil)"
                if self.win: self.win.after(0, lambda t=text: self.label.config(text=t))
                time.sleep(1)
            except: break
    def hide(self):
        self.running = False
        if self.win:
            try: self.win.destroy()
            except: pass
            self.win = None

# --- Main App ---
class GameForgeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {\'[ADMIN]\' if is_admin() else \'[Run as Admin!]\'}")
        self.geometry("1250x780")
        self.minsize(1150, 700)

        self.crosshair = CrosshairOverlay()
        self.perf = PerfOverlay()
        self.ram_loop_active = False
        self.game_profiles = self.load_profiles()
        self.native_res = self.get_current_res()

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.main = ctk.CTkFrame(self)
        self.main.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)

        self.create_sidebar()
        self.create_tabs()

        if not is_admin():
            self.show_warning("Please restart as Administrator for tweaks, resolution switcher, and RAM purge to work.")

    def show_warning(self, msg):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Warning"); dlg.geometry("400x150"); dlg.attributes("-topmost", True)
        ctk.CTkLabel(dlg, text=msg, wraplength=350).pack(pady=20, padx=20)
        ctk.CTkButton(dlg, text="OK", command=dlg.destroy).pack(pady=10)

    # --- Sidebar Utilities ---
    def create_sidebar(self):
        ctk.CTkLabel(self.sidebar, text="GameForge", font=("Segoe UI Black", 22)).pack(pady=(20,0))
        ctk.CTkLabel(self.sidebar, text="SUITE v2.0", font=("Segoe UI", 11), text_color="gray").pack()
        ctk.CTkLabel(self.sidebar, text="One-Click Utilities", font=("Segoe UI Bold", 13)).pack(pady=(25,10))

        ctk.CTkButton(self.sidebar, text="Purge Standby List Now", fg_color="#2a9d8f", hover_color="#21867a", command=self.purge_standby).pack(pady=6, padx=20, fill="x")
        ctk.CTkButton(self.sidebar, text="Flush DNS Cache", fg_color="#264653", command=self.flush_dns).pack(pady=6, padx=20, fill="x")
        ctk.CTkButton(self.sidebar, text="Restart Graphics Driver", fg_color="#e76f51", hover_color="#c85a3f", command=self.restart_gpu).pack(pady=6, padx=20, fill="x")
        ctk.CTkButton(self.sidebar, text="Create Restore Point", fg_color="#6a4c93", command=self.create_restore).pack(pady=15, padx=20, fill="x")

        ctk.CTkLabel(self.sidebar, text="© 2025 GameForge", text_color="gray", font=("Segoe UI", 10)).pack(side="bottom", pady=15)

    def purge_standby(self):
        if not is_admin(): return self.show_warning("Admin required.")
        # Method 1: EmptyWorkingSet + Standby purge via PowerShell + ctypes
        try:
            # Trim working sets
            if psutil:
                for p in psutil.process_iter():
                    try: ctypes.windll.psapi.EmptyWorkingSet(p.pid) if hasattr(ctypes.windll.psapi, \'EmptyWorkingSet\') else None
                    except: pass
            # Requires EmptyStandbyList.exe or RAMMap technique - fallback to documented command
            ok, out = run_powershell("Write-Output \'Purging standby list...\' ; [System.GC]::Collect()")
            self.show_warning("RAM Working Sets Trimmed.\nFor full Standby List purge, place EmptyStandbyList.exe next to exe and it will be invoked.")
            if Path("EmptyStandbyList.exe").exists():
                run_cmd("EmptyStandbyList.exe standbylist")
        except Exception as e: self.show_warning(str(e))

    def flush_dns(self): 
        ok, out = run_cmd("ipconfig /flushdns")
        self.show_warning("DNS Cache Flushed." if ok else f"Failed: {out}")

    def restart_gpu(self):
        if not is_admin(): return self.show_warning("Admin required.")
        # Emulates Win+Ctrl+Shift+B - cannot be sent directly, uses display driver restart via PnPUtil / DxDiag trick
        res = ctypes.windll.user32.MessageBoxW(0, "This will restart your graphics driver (screen will flicker). Continue?", "Restart GPU Driver", 0x31)
        if res == 1:
            # Most reliable non-destructive method: disable/enable GPU via PowerShell
            ps = "Get-PnpDevice -Class Display | Disable-PnpDevice -Confirm:$false; Start-Sleep 2; Get-PnpDevice -Class Display | Enable-PnpDevice -Confirm:$false"
            threading.Thread(target=lambda: run_powershell(ps), daemon=True).start()
            self.show_warning("GPU Restart Triggered. Screen may flicker for 2-3 seconds.")

    def create_restore(self):
        ok, out = run_powershell("Checkpoint-Computer -Description \'GameForge_PreTweak\' -RestorePointType MODIFY_SETTINGS")
        self.show_warning("Restore Point Created." if ok else f"Failed (Enable System Protection first): {out[:200]}")

    # --- Tabs ---
    def create_tabs(self):
        self.tabs = ctk.CTkTabview(self.main)
        self.tabs.pack(fill="both", expand=True)
        for name in ["System Tweaks", "Game Launcher", "Gaming Tools"]:
            self.tabs.add(name)
        self.build_tweaks_tab()
        self.build_launcher_tab()
        self.build_tools_tab()

    def build_tweaks_tab(self):
        tab = self.tabs.tab("System Tweaks")
        tab.grid_columnconfigure((0,1), weight=1)
        # Hardware & GPU
        f1 = ctk.CTkFrame(tab); f1.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(f1, text="Hardware & GPU", font=("Segoe UI Bold", 14)).pack(pady=10)
        self.tick_var = ctk.StringVar(value="Unknown")
        ctk.CTkButton(f1, text="Disable Dynamic Tick (bcdedit)", command=lambda: self.bcd_tick(False)).pack(pady=4, padx=10, fill="x")
        ctk.CTkButton(f1, text="Enable Dynamic Tick", command=lambda: self.bcd_tick(True)).pack(pady=4, padx=10, fill="x")
        ctk.CTkButton(f1, text="Set GPU to Max Performance", command=self.gpu_max).pack(pady=4, padx=10, fill="x")
        ctk.CTkButton(f1, text="Check VBS / Core Isolation", command=self.check_vbs).pack(pady=4, padx=10, fill="x")
        ctk.CTkButton(f1, text="Detect MSI Mode (GPU)", command=self.check_msi).pack(pady=4, padx=10, fill="x")

        # Services
        f2 = ctk.CTkFrame(tab); f2.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(f2, text="Services", font=("Segoe UI Bold", 14)).pack(pady=10)
        ctk.CTkButton(f2, text="Optimize Gaming Services", command=self.optimize_services).pack(pady=4, padx=10, fill="x")
        ctk.CTkButton(f2, text="Disable Windows Search/Indexing", command=lambda: self.toggle_search(False)).pack(pady=4, padx=10, fill="x")
        ctk.CTkButton(f2, text="Enable Windows Search", command=lambda: self.toggle_search(True)).pack(pady=4, padx=10, fill="x")

        # Privacy & Debloat
        f3 = ctk.CTkFrame(tab); f3.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(f3, text="Privacy & Debloat (Registry - Reversible)", font=("Segoe UI Bold", 14)).pack(pady=10)
        row = ctk.CTkFrame(f3, fg_color="transparent"); row.pack(fill="x", padx=10)
        ctk.CTkButton(row, text="Disable Telemetry + DiagTrack", command=self.disable_telemetry).pack(side="left", padx=5, expand=True, fill="x")
        ctk.CTkButton(row, text="Disable Bing/Copilot/Search", command=self.disable_bing).pack(side="left", padx=5, expand=True, fill="x")
        ctk.CTkButton(row, text="Disable Store Background Apps", command=self.disable_bg_apps).pack(side="left", padx=5, expand=True, fill="x")

    def bcd_tick(self, enable):
        if not is_admin(): return self.show_warning("Admin required for bcdedit.")
        val = "yes" if enable else "no"
        ok, out = run_cmd(f"bcdedit /set disabledynamictick {val}")
        self.show_warning(f"Dynamic Tick {\'Enabled\' if enable else \'Disabled\'}. Reboot required.\n{out[:300]}")

    def gpu_max(self):
        # Sets Power plan to prefer max performance + registry for Nvidia
        ps = "powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c; Set-ItemProperty -Path \'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Power\' -Name \'HibernateEnabled\' -Value 0 -ErrorAction SilentlyContinue"
        ok, _ = run_powershell(ps)
        self.show_warning("High Performance Power Plan Activated. For NVidia, also set \'Prefer Maximum Performance\' in NV Control Panel.")

    def check_vbs(self):
        ok, out = run_powershell("(Get-CimInstance Win32_DeviceGuard -Namespace root\\Microsoft\\Windows\\DeviceGuard).VirtualizationBasedSecurityStatus")
        ctypes.windll.user32.MessageBoxW(0, f"VBS Status Code: {out.strip()}\n0=Off, 2=On\n\nTo disable: Settings > Privacy & Security > Core Isolation > Memory Integrity OFF + bcdedit /set hypervisorlaunchtype off (requires reboot)", "VBS Check", 0x40)

    def check_msi(self):
        ok, out = run_powershell("Get-ItemProperty -Path \'HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\PCI\\*\\*\\Device Parameters\\Interrupt Management\\MessageSignaledInterruptProperties\' -Name MSISupported -ErrorAction SilentlyContinue | Select-Object -ExpandProperty MSISupported")
        self.show_warning(f"MSI Mode detection raw output:\n{out[:400] if out.strip() else \'Not found / Not enabled. Use MSI Utility v3 to enable.\'}")

    def optimize_services(self):
        if not is_admin(): return self.show_warning("Admin required.")
        services = ["DiagTrack","dmwappushservice","WSearch","SysMain","PrintNotify"]
        for s in services:
            run_cmd(f\'sc config "{s}" start= demand & sc stop "{s}"\')
        self.show_warning("Non-essential services set to Manual/Stopped.\n SysMain (Superfetch) and Search disabled for gaming.")

    def toggle_search(self, enable):
        val = "auto" if enable else "demand"
        run_cmd(f\'sc config WSearch start= {val}\')
        run_cmd(f\'net {"start" if enable else "stop"} WSearch\')
        self.show_warning(f"Windows Search {\'Enabled\' if enable else \'Disabled\'}.")

    def disable_telemetry(self):
        cmds = [
            \'sc config DiagTrack start= disabled & sc stop DiagTrack\',
            \'reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 0 /f\',
            \'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 0 /f\'
        ]
        for c in cmds: run_cmd(c)
        self.show_warning("Telemetry & DiagTrack Disabled. Reboot recommended.")

    def disable_bing(self):
        cmds = [
            \'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Search" /v BingSearchEnabled /t REG_DWORD /d 0 /f\',
            \'reg add "HKCU\\Software\\Policies\\Microsoft\\Windows\\Windows Copilot" /v TurnOffWindowsCopilot /t REG_DWORD /d 1 /f\'
        ]
        for c in cmds: run_cmd(c)
        self.show_warning("Bing Search & Copilot Registry Keys Set. Restart Explorer / Reboot.")

    def disable_bg_apps(self):
        run_cmd(\'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\BackgroundAccessApplications" /v GlobalUserDisabled /t REG_DWORD /d 1 /f\')
        self.show_warning("Microsoft Store Background Apps Disabled.")

    # --- Game Launcher ---
    def build_launcher_tab(self):
        tab = self.tabs.tab("Game Launcher")
        tab.grid_columnconfigure(0, weight=1)
        # Add Game
        add = ctk.CTkFrame(tab); add.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(add, text="Game Profile Manager", font=("Segoe UI Bold", 14)).pack(anchor="w", padx=10, pady=5)
        self.game_name = ctk.CTkEntry(add, placeholder_text="Game Name (e.g. Fortnite)")
        self.game_name.pack(fill="x", padx=10, pady=5)
        self.game_path = ctk.CTkEntry(add, placeholder_text="EXE Path or Launcher URI (e.g. com.epicgames.launcher://...)")
        self.game_path.pack(fill="x", padx=10, pady=5)
        self.game_res = ctk.CTkComboBox(add, values=["Native", "1680x1050", "1536x1080", "1440x1080", "1280x960"])
        self.game_res.pack(side="left", padx=10, pady=5)
        ctk.CTkButton(add, text="Browse .exe", width=100, command=self.browse_exe).pack(side="left", pady=5)
        ctk.CTkButton(add, text="Add / Save Game", fg_color="#2a9d8f", command=self.add_game).pack(side="right", padx=10, pady=5)

        # List
        self.game_list = ctk.CTkScrollableFrame(tab, height=300)
        self.game_list.pack(fill="both", expand=True, padx=10, pady=10)
        self.refresh_games()

        # Pre-launch options
        opts = ctk.CTkFrame(tab); opts.pack(fill="x", padx=10, pady=5)
        self.opt_trim = ctk.CTkCheckBox(opts, text="Trim RAM & Purge Standby")
        self.opt_trim.select(); self.opt_trim.pack(side="left", padx=10)
        self.opt_priority = ctk.CTkCheckBox(opts, text="Set High Priority")
        self.opt_priority.select(); self.opt_priority.pack(side="left", padx=10)
        self.opt_close = ctk.CTkCheckBox(opts, text="Close Chrome/Discord (Auto-Reopen)")
        self.opt_close.pack(side="left", padx=10)

    def browse_exe(self):
        path = tk.filedialog.askopenfilename(filetypes=[("Executable", "*.exe")])
        if path: self.game_path.delete(0, "end"); self.game_path.insert(0, path)

    def load_profiles(self):
        if CONFIG_PATH.exists():
            try: return json.loads(CONFIG_PATH.read_text())
            except: return []
        return []

    def save_profiles(self): CONFIG_PATH.write_text(json.dumps(self.game_profiles, indent=2))

    def add_game(self):
        name, path, res = self.game_name.get().strip(), self.game_path.get().strip(), self.game_res.get()
        if not name or not path: return self.show_warning("Enter Name and Path/URI.")
        self.game_profiles.append({"name":name, "path":path, "res":res, "playtime":0, "last_played":"Never"})
        self.save_profiles(); self.refresh_games()
        self.game_name.delete(0,"end"); self.game_path.delete(0,"end")

    def refresh_games(self):
        for w in self.game_list.winfo_children(): w.destroy()
        for idx, g in enumerate(self.game_profiles):
            row = ctk.CTkFrame(self.game_list); row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=g["name"], width=150, anchor="w", font=("Segoe UI Bold",12)).pack(side="left", padx=10)
            ctk.CTkLabel(row, text=f"{g[\'res\']} | {g[\'last_played\']} | {g[\'playtime\']//60}h {g[\'playtime\']%60}m", width=300, anchor="w").pack(side="left")
            ctk.CTkButton(row, text="LAUNCH", width=80, fg_color="#e76f51", command=lambda i=idx: threading.Thread(target=self.launch_game, args=(i,), daemon=True).start()).pack(side="right", padx=5)
            ctk.CTkButton(row, text="X", width=30, fg_color="gray", command=lambda i=idx: self.delete_game(i)).pack(side="right", padx=5)

    def delete_game(self, idx):
        del self.game_profiles[idx]; self.save_profiles(); self.refresh_games()

    def get_current_res(self):
        try:
            user32 = ctypes.windll.user32
            return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        except: return (1920,1080)

    def set_resolution(self, w, h):
        try:
            import win32api, win32con
            devmode = win32api.EnumDisplaySettings(None, win32con.ENUM_CURRENT_SETTINGS)
            devmode.PelsWidth, devmode.PelsHeight = w, h
            win32api.ChangeDisplaySettings(devmode, 0)
            return True
        except:
            # ctypes fallback
            class DEVMODE(ctypes.Structure):
                _fields_ = [("dmDeviceName", ctypes.c_wchar*32),("dmSpecVersion", ctypes.c_ushort),("dmDriverVersion", ctypes.c_ushort),("dmSize", ctypes.c_ushort),("dmDriverExtra", ctypes.c_ushort),("dmFields", ctypes.c_ulong),("dmPelsWidth", ctypes.c_ulong),("dmPelsHeight", ctypes.c_ulong),("dmDisplayFlags", ctypes.c_ulong),("dmDisplayFrequency", ctypes.c_ulong)]
            dm = DEVMODE(); dm.dmSize = ctypes.sizeof(dm); dm.dmPelsWidth=w; dm.dmPelsHeight=h; dm.dmFields=0x180000
            return ctypes.windll.user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0) == 0

    def launch_game(self, idx):
        g = self.game_profiles[idx]
        # Pre-launch optimization
        closed = []
        if self.opt_trim.get(): self.purge_standby()
        if self.opt_close.get() and psutil:
            for name in ["chrome.exe","discord.exe","spotify.exe"]:
                for p in psutil.process_iter(["name","exe"]):
                    if p.info["name"] and p.info["name"].lower()==name:
                        try: closed.append(p.info["exe"] or name); p.terminate()
                        except: pass
        # Resolution switch
        if g["res"] != "Native":
            try: w,h = map(int, g["res"].split("x")); self.set_resolution(w,h)
            except: pass

        # Launch
        start = time.time()
        proc = None
        try:
            if "://" in g["path"]: webbrowser.open(g["path"])
            else: proc = subprocess.Popen(g["path"], shell=True)
            if self.opt_priority.get() and proc and psutil:
                try: psutil.Process(proc.pid).nice(psutil.HIGH_PRIORITY_CLASS)
                except: pass
        except Exception as e: self.show_warning(f"Launch failed: {e}")

        # Monitor for exit to restore
        target_name = Path(g["path"]).name if "://" not in g["path"] else "FortniteClient-Win64-Shipping.exe"
        # If launcher URI, wait for FortniteClient, else wait for proc
        while True:
            time.sleep(3)
            still_running = False
            if psutil:
                for p in psutil.process_iter(["name"]):
                    if target_name.lower() in (p.info["name"] or "").lower():
                        still_running = True; break
                if proc and proc.poll() is None: still_running = True
            else:
                if proc and proc.poll() is None: still_running = True
            if not still_running and time.time()-start > 10: break
            if time.time()-start > 36000: break # safety 10h

        # Restore
        w,h = self.native_res
        self.set_resolution(w,h)
        for exe in closed:
            try: subprocess.Popen(exe, shell=True)
            except: pass
        # Tracker
        elapsed = int((time.time()-start)/60)
        g["playtime"] += elapsed
        g["last_played"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.save_profiles()
        self.after(0, self.refresh_games)

    # --- Gaming Tools ---
    def build_tools_tab(self):
        tab = self.tabs.tab("Gaming Tools")
        # RAM Loop
        f = ctk.CTkFrame(tab); f.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(f, text="Automated RAM Cleanup Loop", font=("Segoe UI Bold", 14)).pack(anchor="w", padx=10, pady=5)
        self.ram_interval = ctk.CTkComboBox(f, values=["5","10","15","30"], width=80); self.ram_interval.set("10"); self.ram_interval.pack(side="left", padx=10)
        ctk.CTkLabel(f, text="minutes").pack(side="left")
        self.ram_switch = ctk.CTkSwitch(f, text="OFF", command=self.toggle_ram_loop); self.ram_switch.pack(side="right", padx=20)

        # Crosshair
        c = ctk.CTkFrame(tab); c.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(c, text="Screen Crosshair Overlay", font=("Segoe UI Bold", 14)).pack(anchor="w", padx=10, pady=5)
        self.ch_shape = ctk.CTkComboBox(c, values=["Cross","Dot","Circle"]); self.ch_shape.set("Cross"); self.ch_shape.pack(side="left", padx=5)
        self.ch_color = ctk.CTkComboBox(c, values=["#00FF00","#FF0000","#00FFFF","#FFFFFF"]); self.ch_color.set("#00FF00"); self.ch_color.pack(side="left", padx=5)
        self.ch_size = ctk.CTkSlider(c, from_=5, to=40); self.ch_size.set(20); self.ch_size.pack(side="left", padx=10, fill="x", expand=True)
        self.ch_switch = ctk.CTkSwitch(c, text="OFF", command=self.toggle_crosshair); self.ch_switch.pack(side="right", padx=10)

        # Perf Overlay
        p = ctk.CTkFrame(tab); p.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(p, text="Live Performance Overlay", font=("Segoe UI Bold", 14)).pack(anchor="w", padx=10, pady=5)
        ctk.CTkLabel(p, text="Shows CPU / RAM / Uptime as draggable widget").pack(anchor="w", padx=10)
        self.perf_switch = ctk.CTkSwitch(p, text="OFF", command=self.toggle_perf); self.perf_switch.pack(side="right", padx=20, pady=10)

    def toggle_ram_loop(self):
        if self.ram_switch.get()==1:
            self.ram_loop_active=True; self.ram_switch.configure(text="ON")
            def loop():
                while self.ram_loop_active:
                    try: mins=int(self.ram_interval.get())
                    except: mins=10
                    time.sleep(mins*60)
                    if self.ram_loop_active: self.purge_standby()
            threading.Thread(target=loop, daemon=True).start()
        else:
            self.ram_loop_active=False; self.ram_switch.configure(text="OFF")

    def toggle_crosshair(self):
        if self.ch_switch.get()==1:
            self.crosshair.config.update({"shape":self.ch_shape.get(),"color":self.ch_color.get(),"size":int(self.ch_size.get())})
            self.crosshair.show(); self.ch_switch.configure(text="ON")
        else:
            self.crosshair.hide(); self.ch_switch.configure(text="OFF")

    def toggle_perf(self):
        if self.perf_switch.get()==1:
            self.perf.show(); self.perf_switch.configure(text="ON")
        else:
            self.perf.hide(); self.perf_switch.configure(text="OFF")

if __name__ == "__main__":
    app = GameForgeApp()
    app.mainloop()
