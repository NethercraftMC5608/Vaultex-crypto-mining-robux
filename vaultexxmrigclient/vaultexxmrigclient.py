import os
import json
import subprocess
import threading
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import StringVar, Text, Scrollbar, END, messagebox
from tkinter.simpledialog import askstring
import requests
import time
import zipfile
import urllib.request

CONFIG_FILE = "config.json"
MINER_DIR = "miner"
XMRIG_URL = "https://github.com/xmrig/xmrig/releases/download/v6.22.2/xmrig-6.22.2-msvc-win64.zip"
CUDA_URL = "https://github.com/xmrig/xmrig-cuda/releases/download/v6.22.0/xmrig-cuda-6.22.0-cuda12_4-win64.zip"

def download_and_extract(url, extract_to):
    zip_path = os.path.join(extract_to, "temp.zip")
    urllib.request.urlretrieve(url, zip_path)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                # Extract files directly into the target directory without preserving folder structure
                filename = os.path.basename(member)
                if filename:  # Avoid directories
                    source = zip_ref.open(member)
                    target_path = os.path.join(extract_to, filename)
                    with open(target_path, "wb") as target:
                        target.write(source.read())
    except Exception as e:
        print(f"Error during extraction: {e}")
    finally:
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception as e:
                print(f"Error removing temporary zip file: {e}")

def ensure_miner_directory():
    if not os.path.exists(MINER_DIR):
        os.makedirs(MINER_DIR)
        download_and_extract(XMRIG_URL, MINER_DIR)

def ensure_cuda_extension():
    cuda_file = os.path.join(MINER_DIR, "xmrig-cuda.dll")
    if not os.path.exists(cuda_file):
        download_and_extract(CUDA_URL, MINER_DIR)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def setup_wizard():
    ensure_miner_directory()

    config = {}

    username = askstring("Setup Wizard", "Enter your username (indentifer):")
    if not username:
        messagebox.showerror("Error", "Username (indentifer) is required.")
        return None
    config["Username"] = username

    gpu_choice = messagebox.askquestion(
        "Setup Wizard", "Do you have an NVIDIA GPU? (Click 'No' for AMD or CPU only)"
    )

    if gpu_choice == "yes":
        config["GPU"] = "NVIDIA"
        ensure_cuda_extension()
    else:
        amd_choice = messagebox.askquestion(
            "Setup Wizard", "Do you have an AMD GPU? (Click 'No' for CPU only)"
        )
        config["GPU"] = "AMD" if amd_choice == "yes" else "CPU"

    save_config(config)
    return config

class VaultexXMRIGClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Vaultex XMRIG Client")
        self.root.geometry("800x600")
        self.root.resizable(False, False)

        self.miner_process = None
        self.is_gaming_mode = False
        self.hashrate = StringVar(value="Hashrate: 0 H/s")
        self.accepted_shares = StringVar(value="Accepted Shares: 0")
        self.uptime = StringVar(value="Uptime: 0 seconds")
        self.pool = StringVar(value="Pool: Not Connected")
        self.threads = StringVar(value="Threads: 0")

        self.config = load_config()
        if not self.config:
            self.config = setup_wizard()
            if not self.config:
                self.root.destroy()
                return

        # GUI Elements
        self.create_widgets()
        threading.Thread(target=self.update_stats, daemon=True).start()

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=BOTH, expand=YES)

        ttk.Label(frame, text="Vaultex XMRIG Client", font=("Arial", 18), bootstyle=PRIMARY).pack(pady=10)

        self.hashrate_label = ttk.Label(frame, textvariable=self.hashrate, font=("Arial", 14))
        self.hashrate_label.pack(pady=5)

        self.accepted_shares_label = ttk.Label(frame, textvariable=self.accepted_shares, font=("Arial", 14))
        self.accepted_shares_label.pack(pady=5)

        self.uptime_label = ttk.Label(frame, textvariable=self.uptime, font=("Arial", 14))
        self.uptime_label.pack(pady=5)

        self.pool_label = ttk.Label(frame, textvariable=self.pool, font=("Arial", 14))
        self.pool_label.pack(pady=5)

        self.threads_label = ttk.Label(frame, textvariable=self.threads, font=("Arial", 14))
        self.threads_label.pack(pady=5)

        self.start_button = ttk.Button(frame, text="Start Mining", bootstyle=SUCCESS, command=self.start_miner)
        self.start_button.pack(pady=10)

        self.stop_button = ttk.Button(frame, text="Stop Mining", bootstyle=DANGER, command=self.stop_miner, state=DISABLED)
        self.stop_button.pack(pady=10)

        self.gaming_mode_button = ttk.Checkbutton(
            frame, text="Gaming Mode", bootstyle="success-round-toggle", command=self.toggle_gaming_mode
        )
        self.gaming_mode_button.pack(pady=10)

        # Log display
        log_frame = ttk.Frame(frame)
        log_frame.pack(fill=BOTH, expand=YES, pady=10)

        self.log_text = Text(log_frame, wrap="none", height=15)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=YES)

        log_scroll = Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(side=RIGHT, fill=Y)
        self.log_text.config(yscrollcommand=log_scroll.set)

    def start_miner(self):
        if not os.path.exists("miner/") or not os.path.exists("miner/xmrig.exe"):
            self.hashrate.set("Error: XMRIG not found in the miner directory.")
            return

        cmd = ["miner/xmrig.exe", "-o", "robuxmoneropool.vaultex.store:3333"]
        cmd.append(f"-u {self.config['Username']}")

        if self.config["GPU"] == "NVIDIA":
            cmd.append("--cuda")
        elif self.config["GPU"] == "AMD":
            cmd.append("--opencl")

        if self.is_gaming_mode:
            cmd.append("--threads=1")

        self.miner_process = subprocess.Popen(
            cmd, cwd="miner", stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        self.start_button["state"] = DISABLED
        self.stop_button["state"] = NORMAL
        threading.Thread(target=self.monitor_miner_output, daemon=True).start()

    def stop_miner(self):
        if self.miner_process:
            self.miner_process.terminate()
            self.miner_process = None

        self.start_button["state"] = NORMAL
        self.stop_button["state"] = DISABLED

        self.hashrate.set("Hashrate: 0 H/s")
        self.accepted_shares.set("Accepted Shares: 0")
        self.uptime.set("Uptime: 0 seconds")
        self.pool.set("Pool: Not Connected")
        self.threads.set("Threads: 0")

    def toggle_gaming_mode(self):
        self.is_gaming_mode = not self.is_gaming_mode

    def monitor_miner_output(self):
        while self.miner_process and self.miner_process.poll() is None:
            output = self.miner_process.stdout.readline()
            if not output:
                continue

            # Log the output
            self.log_text.insert(END, output)
            self.log_text.see(END)

    def update_stats(self):
        while True:
            try:
                response = requests.get("http://127.0.0.1:8080/2/summary")
                if response.status_code == 200:
                    data = response.json()

                    hashrate = data.get("hashrate", {}).get("total", [0])[0]
                    accepted_shares = data.get("connection", {}).get("accepted", 0)
                    uptime = data.get("uptime", 0)
                    pool = data.get("connection", {}).get("pool", "Not Connected")
                    threads = data.get("cpu", {}).get("threads", 0)

                    self.hashrate.set(f"Hashrate: {hashrate} H/s")
                    self.accepted_shares.set(f"Accepted Shares: {accepted_shares}")
                    self.uptime.set(f"Uptime: {uptime} seconds")
                    self.pool.set(f"Pool: {pool}")
            except Exception as e:
                pass

            time.sleep(2)

if __name__ == "__main__":
    app = ttk.Window(themename="darkly")
    client = VaultexXMRIGClient(app)

    def on_closing():
        client.stop_miner()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()

