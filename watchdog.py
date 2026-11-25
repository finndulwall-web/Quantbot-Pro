#!/usr/bin/env python3
import psutil
import time
import logging
import subprocess
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("QuantBot-Watchdog")

BOT_SERVICE = "quantbot"
UI_SERVICE = "quantbot-ui"
MEMORY_LIMIT_MB = 2500
UI_MEMORY_LIMIT_MB = 500
CHECK_INTERVAL = 30

def get_service_memory(service_name: str) -> int:
    try:
        result = subprocess.run(
            ['systemctl', 'show', service_name, '--property=MainPID'],
            capture_output=True, text=True, check=True
        )
        pid_line = result.stdout.strip()
        if '=' in pid_line:
            pid = int(pid_line.split('=')[1])
            if pid > 0:
                process = psutil.Process(pid)
                mem_info = process.memory_info()
                return mem_info.rss // (1024 * 1024)
    except Exception as e:
        logger.debug(f"Could not get memory for {service_name}: {e}")
    return 0

def restart_service(service_name: str):
    logger.warning(f"Restarting {service_name} due to memory limit")
    try:
        subprocess.run(['systemctl', 'restart', service_name], check=True, timeout=30)
        logger.info(f"Successfully restarted {service_name}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to restart {service_name}: {e}")
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout restarting {service_name}")

def main():
    logger.info(f"Starting watchdog. Memory limits: Bot={MEMORY_LIMIT_MB}MB, UI={UI_MEMORY_LIMIT_MB}MB")
    
    while True:
        try:
            bot_mem = get_service_memory(BOT_SERVICE)
            ui_mem = get_service_memory(UI_SERVICE)
            
            if bot_mem > 0:
                logger.debug(f"Bot memory: {bot_mem}MB")
                if bot_mem > MEMORY_LIMIT_MB:
                    logger.warning(f"Bot memory ({bot_mem}MB) exceeds limit ({MEMORY_LIMIT_MB}MB)")
                    restart_service(BOT_SERVICE)
            
            if ui_mem > 0:
                logger.debug(f"UI memory: {ui_mem}MB")
                if ui_mem > UI_MEMORY_LIMIT_MB:
                    logger.warning(f"UI memory ({ui_mem}MB) exceeds limit ({UI_MEMORY_LIMIT_MB}MB)")
                    restart_service(UI_SERVICE)
            
        except Exception as e:
            logger.error(f"Watchdog error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
