#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smart Proxy Rotator + CPU Stealth
Version: 2.0
Author: @L0G1_N
"""

import time
import math
import random
import threading
import requests
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import psutil
from colorama import Fore, Style, init

# ==============================================
# تنظیمات
# ==============================================

init(autoreset=True)

# تنظیمات CPU Stealth
CPU_TARGET_MIN = 5
CPU_TARGET_MAX = 15
CPU_CHECK_INTERVAL = 0.5

# تنظیمات Proxy Rotator
PROXY_FILE = "proxies.txt"
CHECK_URL = "http://httpbin.org/ip"
TIMEOUT = 5
MAX_THREADS = 20
RETRY_COUNT = 3

# ==============================================
# بخش ۱: مدیریت CPU Stealth
# ==============================================

class CPUStealth:
    """مدیریت و نوسان‌دهی مصرف CPU"""
    
    def __init__(self, min_load=CPU_TARGET_MIN, max_load=CPU_TARGET_MAX):
        self.min_load = min_load
        self.max_load = max_load
        self.running = False
        self.thread = None
        self.cpu_count = psutil.cpu_count(logical=False)
        self.total_cores = psutil.cpu_count(logical=True)
        print(f"{Fore.CYAN}[*] CPU Cores: {self.cpu_count} Physical, {self.total_cores} Logical")

    def _cpu_workload(self, duration=0.1):
        """ایجاد بار محاسباتی کنترل شده"""
        start = time.time()
        while time.time() - start < duration:
            _ = [i**2 for i in range(1000)]

    def _adjust_usage(self):
        """تنظیم خودکار مصرف CPU با نوسان"""
        while self.running:
            current_usage = psutil.cpu_percent(interval=0.1)
            
            # محاسبه هدف جدید با نوسان سینوسی
            cycle = time.time() * 0.1
            target = self.min_load + (self.max_load - self.min_load) * (0.5 + 0.5 * math.sin(cycle))
            
            print(f"\r{Fore.CYAN}📊 CPU: {current_usage:5.1f}% | Target: {target:5.1f}%{Style.RESET_ALL}", end="")
            
            if current_usage < target and target > 0:
                workload_time = min(0.3, (target - current_usage) / 100 * 0.1)
                self._cpu_workload(workload_time)
            elif current_usage > target + 5:
                time.sleep(0.05)
            else:
                time.sleep(CPU_CHECK_INTERVAL)

    def start(self):
        """شروع فرآیند مدیریت مصرف CPU"""
        if self.running:
            print(f"{Fore.YELLOW}[!] CPU management already running!")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._adjust_usage, daemon=True)
        self.thread.start()
        print(f"{Fore.GREEN}[+] CPU usage management started")

    def stop(self):
        """توقف فرآیند مدیریت مصرف CPU"""
        if not self.running:
            print(f"{Fore.YELLOW}[!] CPU management not running!")
            return
        
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        print(f"\n{Fore.RED}[-] CPU usage management stopped")

# ==============================================
# بخش ۲: مدیریت Proxy Rotator
# ==============================================

class ProxyRotator:
    """مدیریت و چرخش پروکسی"""
    
    def __init__(self, proxy_file=PROXY_FILE):
        self.proxy_file = proxy_file
        self.proxies = []
        self.working_proxies = []
        self.lock = threading.Lock()
        self.load_proxies()
        self.validate_proxies()

    def load_proxies(self):
        """بارگذاری پروکسی‌ها از فایل"""
        try:
            with open(self.proxy_file, 'r', encoding='utf-8') as f:
                self.proxies = [line.strip() for line in f if line.strip()]
            print(f"{Fore.GREEN}[+] {len(self.proxies)} proxies loaded from {self.proxy_file}")
        except FileNotFoundError:
            print(f"{Fore.RED}[!] Proxy file not found: {self.proxy_file}")
            print(f"{Fore.YELLOW}[*] Please create a file with your proxies")
            self.proxies = []

    def validate_proxy(self, proxy):
        """اعتبارسنجی یک پروکسی"""
        try:
            response = requests.get(
                CHECK_URL,
                proxies={'http': proxy, 'https': proxy},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                return True
        except:
            pass
        return False

    def validate_proxies(self):
        """اعتبارسنجی همه پروکسی‌ها (با ترد)"""
        if not self.proxies:
            return
        
        print(f"{Fore.YELLOW}[*] Validating proxies...")
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            results = list(executor.map(self.validate_proxy, self.proxies))
        
        self.working_proxies = [p for p, v in zip(self.proxies, results) if v]
        print(f"{Fore.GREEN}[+] {len(self.working_proxies)} working proxies found")
        print(f"{Fore.RED}[-] {len(self.proxies) - len(self.working_proxies)} proxies failed")

    def get_random_proxy(self):
        """دریافت یک پروکسی تصادفی از لیست معتبر"""
        if not self.working_proxies:
            return None
        return random.choice(self.working_proxies)

    def rotate_proxy(self):
        """چرخش پروکسی به صورت Round Robin"""
        if not self.working_proxies:
            return None
        with self.lock:
            proxy = self.working_proxies.pop(0)
            self.working_proxies.append(proxy)
            return proxy

    def request_with_retry(self, url, method='GET', headers=None, data=None, retries=RETRY_COUNT):
        """ارسال درخواست با چرخش پروکسی و تلاش مجدد"""
        for attempt in range(retries):
            proxy = self.get_random_proxy()
            if not proxy:
                print(f"{Fore.RED}[!] No working proxies available!")
                return None
            
            try:
                print(f"{Fore.CYAN}[*] Using proxy: {proxy}")
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=data,
                    proxies={'http': proxy, 'https': proxy},
                    timeout=TIMEOUT
                )
                if response.status_code == 200:
                    return response
                else:
                    print(f"{Fore.YELLOW}[!] Response {response.status_code} with proxy {proxy}")
            except Exception as e:
                print(f"{Fore.RED}[-] Error with proxy {proxy}: {str(e)}")
            
            time.sleep(random.uniform(0.5, 2))
        
        return None

    def multi_request(self, urls, method='GET', headers=None, data=None):
        """ارسال چند درخواست همزمان با چرخش پروکسی"""
        results = []
        with ThreadPoolExecutor(max_workers=min(MAX_THREADS, len(self.working_proxies))) as executor:
            futures = []
            for url in urls:
                future = executor.submit(self.request_with_retry, url, method, headers, data)
                futures.append(future)
            
            for future in futures:
                results.append(future.result())
        
        return results

# ==============================================
# بخش ۳: ترکیب هر دو (Smart Proxy Rotator)
# ==============================================

class SmartProxyRotator:
    """ترکیب مدیریت CPU Stealth و Proxy Rotator"""
    
    def __init__(self, proxy_file=PROXY_FILE):
        self.cpu_stealth = CPUStealth()
        self.proxy_rotator = ProxyRotator(proxy_file)
        self.is_stealth_active = False

    def start_stealth_mode(self):
        """فعال‌سازی حالت مخفی‌سازی مصرف CPU"""
        self.cpu_stealth.start()
        self.is_stealth_active = True
        return self

    def stop_stealth_mode(self):
        """غیرفعال‌سازی حالت مخفی‌سازی مصرف CPU"""
        self.cpu_stealth.stop()
        self.is_stealth_active = False
        return self

    def get_proxy(self):
        """دریافت یک پروکسی تصادفی"""
        return self.proxy_rotator.get_random_proxy()

    def request(self, url, method='GET', headers=None, data=None):
        """ارسال درخواست با پروکسی و مدیریت CPU"""
        return self.proxy_rotator.request_with_retry(url, method, headers, data)

    def multi_request(self, urls, method='GET', headers=None, data=None):
        """ارسال چند درخواست همزمان"""
        return self.proxy_rotator.multi_request(urls, method, headers, data)

# ==============================================
# اجرای اصلی
# ==============================================

def print_banner():
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗
{Fore.CYAN}║  🧠 SMART PROXY ROTATOR + CPU STEALTH                     ║
{Fore.CYAN}║  🔄 Proxy Rotation | 📊 CPU Management | 🛡️ Stealth Mode  ║
{Fore.CYAN}║  Version: 2.0                           By @L0G1_N        ║
{Fore.CYAN}╚══════════════════════════════════════════════════════════════╝
{Style.RESET_ALL}
"""
    print(banner)

def main():
    print_banner()
    
    # ایجاد نمونه از SmartProxyRotator
    rotator = SmartProxyRotator("proxies.txt")
    
    # فعال‌سازی حالت CPU Stealth
    rotator.start_stealth_mode()
    
    try:
        print(f"\n{Fore.YELLOW}[*] Sending test requests...{Style.RESET_ALL}")
        
        # ارسال درخواست‌های تست
        urls = [
            "http://httpbin.org/ip",
            "http://httpbin.org/user-agent",
            "http://httpbin.org/get"
        ]
        
        results = rotator.multi_request(urls)
        
        print(f"\n{Fore.GREEN}[+] Results:{Style.RESET_ALL}")
        for i, res in enumerate(results):
            if res:
                print(f"  {i+1}. {res.text[:80]}...")
            else:
                print(f"  {i+1}. Failed")
        
        print(f"\n{Fore.YELLOW}[*] Running in stealth mode for 30 seconds...{Style.RESET_ALL}")
        time.sleep(30)
        
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}[!] Interrupted by user{Style.RESET_ALL}")
    finally:
        rotator.stop_stealth_mode()
        print(f"\n{Fore.GREEN}[+] Done!{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
