#!/usr/bin/env python3
import os, sys, time, subprocess, json, hashlib
from pathlib import Path

AUTH_DIR = Path.home() / ".local" / "share" / "opencode"
CONFIG_DIR = Path.home() / ".config" / "opencode"
CONFIG_FILE = CONFIG_DIR / "opencode.json"
SESSION = "autopilot"
PROMPT = "continue the task from where you left off"
STALL_TIMEOUT = 180 
API_KEYS = ["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"]
key_idx = 0

C_CYAN = "\033[96m"; C_GREEN = "\033[92m"; C_YELLOW = "\033[93m"; C_RED = "\033[91m"
C_BOLD = "\033[1m"; C_DIM = "\033[2m"; C_RESET = "\033[0m"
STATE = {"cycles": 0, "limits": 0, "crashes": 0, "start": time.time()}

def log(msg, color=C_RESET):
    print(f"{C_DIM}[{time.strftime('%H:%M:%S')}]{C_RESET} {color}{msg}{C_RESET}", flush=True)

def print_stats(status="Monitoring..."):
    uptime = int(time.time() - STATE["start"])
    h, r = divmod(uptime, 3600); m, s = divmod(r, 60)
    time_str = f"{h:02d}:{m:02d}:{s:02d}"
    pad_status = f"{status[:30]:<30}"
    print(f"\n{C_DIM}╭──────────────────────────────────────────────╮{C_RESET}")
    print(f"{C_DIM}│{C_RESET}  {C_CYAN}{C_BOLD}OCI OMNIPOTENT (v13.3){C_RESET}                      {C_DIM}│{C_RESET}")
    print(f"{C_DIM}├──────────────────────────────────────────────┤{C_RESET}")
    print(f"{C_DIM}│{C_RESET}  {C_CYAN}Uptime:{C_RESET} {C_GREEN}{time_str}{C_RESET}        {C_CYAN}Cycle:{C_RESET} {C_GREEN}{STATE['cycles']}{C_RESET}          {C_DIM}│{C_RESET}")
    print(f"{C_DIM}│{C_RESET}  {C_CYAN}Limits:{C_RESET} {C_RED}{STATE['limits']}{C_RESET}             {C_CYAN}Crashes:{C_RESET} {C_RED}{STATE['crashes']}{C_RESET}         {C_DIM}│{C_RESET}")
    print(f"{C_DIM}├──────────────────────────────────────────────┤{C_RESET}")
    print(f"{C_DIM}│{C_RESET}  {C_CYAN}Status:{C_RESET} {C_YELLOW}{pad_status}{C_RESET}{C_DIM}│{C_RESET}")
    print(f"{C_DIM}╰──────────────────────────────────────────────╯{C_RESET}\n")

def setup_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {
        "provider": {
            "nvidia": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "NVIDIA",
                "options": {
                    "baseURL": "https://integrate.api.nvidia.com/v1",
                    "apiKey": API_KEYS[key_idx]
                },
                "models": {
                    "nvidia/nemotron-3-ultra-550b-a55b": {"name": "Nemotron 3 Ultra"},
                    "minimaxai/minimax-m3.1-flash": {"name": "MiniMax Flash"}
                }
            }
        }
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def start_tmux():
    subprocess.run(["tmux", "kill-session", "-t", SESSION], capture_output=True)
    subprocess.run(["tmux", "new-session", "-d", "-s", SESSION, "-x", "100", "-y", "40"])
    subprocess.run(["tmux", "send-keys", "-t", SESSION, "opencode --continue", "Enter"])

def is_alive():
    return subprocess.run(["tmux", "has-session", "-t", SESSION], capture_output=True).returncode == 0

def get_screen_hash():
    res = subprocess.run(["tmux", "capture-pane", "-p", "-t", SESSION], capture_output=True, text=True)
    return hashlib.md5(res.stdout.encode()).hexdigest(), res.stdout

def main():
    global key_idx
    print_stats("Booting system...")
    subprocess.run(["termux-wake-lock"], capture_output=True)
    try:
        while True:
            STATE["cycles"] += 1
            print_stats("Wiping config...")
            setup_config()
            
            log("Starting OpenCode TUI...", C_CYAN)
            start_tmux()
            
            if STATE["cycles"] > 1:
                print_stats("Injecting prompt...")
                start_wait = time.time()
                while time.time() - start_wait < 30 and is_alive():
                    _, screen = get_screen_hash()
                    if "Ask anything" in screen or "Build" in screen:
                        time.sleep(2)
                        subprocess.run(["tmux", "send-keys", "-t", SESSION, PROMPT, "Enter"])
                        log("Prompt injected.", C_GREEN)
                        break
                    time.sleep(2)
            
            print_stats("Monitoring session...")
            last_hash = ""; last_change = time.time(); session_start = time.time()
            
            while is_alive():
                time.sleep(3)
                current_hash, screen_text = get_screen_hash()
                if current_hash != last_hash:
                    last_hash = current_hash; last_change = time.time()
                
                if "Cannot connect" in screen_text or "Free usage exceeded" in screen_text:
                    log("Error caught.", C_RED); STATE["limits"] += 1; break
                if time.time() - last_change > STALL_TIMEOUT:
                    log("Frozen. Killing...", C_RED); STATE["limits"] += 1; break
                    
            print_stats("Restarting engine...")
            subprocess.run(["tmux", "kill-session", "-t", SESSION], capture_output=True)
            
            if time.time() - session_start < 10:
                STATE["crashes"] += 1; time.sleep(5)
            else:
                STATE["crashes"] = 0; time.sleep(3)
    except KeyboardInterrupt:
        log("Exiting...", C_RED)
    finally:
        subprocess.run(["tmux", "kill-session", "-t", SESSION], capture_output=True)
        subprocess.run(["termux-wake-unlock"], capture_output=True)

if __name__ == "__main__":
    main()
