#!/usr/bin/env python3
"""
nano gcp_socks5_multi_auto.py
python3 gcp_socks5_multi_auto.py
"""

import subprocess
import time
import os
import shlex
import random
import string
import sys
from typing import List, Tuple, Optional


# =========================
#  HÀM TIỆN ÍCH
# =========================

def run(cmd: List[str], capture_output=False, check=True, retries=3) -> str:
    """Chạy lệnh với retry logic"""
    print(">>>", " ".join(shlex.quote(c) for c in cmd))
    
    for attempt in range(retries):
        try:
            if capture_output:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=60,
                )
                if check and result.returncode != 0:
                    if attempt < retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        print(f"⚠️ Lỗi, thử lại sau {wait_time:.1f}s... (lần {attempt + 1}/{retries})")
                        time.sleep(wait_time)
                        continue
                    print(result.stderr)
                    raise RuntimeError(f"Lệnh lỗi: {' '.join(cmd)}")
                return result.stdout.strip()
            else:
                result = subprocess.run(cmd, timeout=60)
                if check and result.returncode != 0:
                    if attempt < retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        print(f"⚠️ Lỗi, thử lại sau {wait_time:.1f}s... (lần {attempt + 1}/{retries})")
                        time.sleep(wait_time)
                        continue
                    raise RuntimeError(f"Lệnh lỗi: {' '.join(cmd)}")
                return ""
        except subprocess.TimeoutExpired:
            if attempt < retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"⚠️ Timeout, thử lại sau {wait_time:.1f}s... (lần {attempt + 1}/{retries})")
                time.sleep(wait_time)
                continue
            raise

    return ""


# =========================
#   USER / PASS
# =========================

def random_user_pass(user_len: int = 8, pass_len: int = 10) -> Tuple[str, str]:
    letters = string.ascii_lowercase + string.digits
    user = "u" + "".join(random.choice(letters) for _ in range(user_len - 1))
    pass_chars = string.ascii_letters + string.digits
    pw = "".join(random.choice(pass_chars) for _ in range(pass_len))
    return user, pw


# =========================
#  INSTANCE 
# =========================

def generate_natural_instance_name(region: str, index: int) -> str:

    prefixes = [
        "web","app","node","srv","api","db","cache","proxy",
        "host","vm","cloud","data","core","edge","gateway",
        "backend","frontend","worker","task","service"
    ]

    suffixes = [
        "01","02","03","04","alpha","beta","prod","dev",
        "test","main","east","west","north","south",
        "05","06","07","08"
    ]

    format_type = random.choice([1,2,3,4])

    if format_type == 1:
        name = f"{random.choice(prefixes)}-{region}-{random.choice(suffixes)}"
    elif format_type == 2:
        name = f"{random.choice(prefixes)}-{region}-{index:02d}"
    elif format_type == 3:
        rand_num = random.randint(100,999)
        name = f"{random.choice(prefixes)}{rand_num}-{region}"
    else:
        rand_str = ''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(3))
        name = f"{random.choice(prefixes)}-{region}-{rand_str}"

    time.sleep(random.uniform(0.1,0.5))

    return name


# =========================

def write_dante_startup_script(username,password,port,allowed_cidrs,path="socks5-startup.sh"):

    cidr_rules="\n".join(
        f"client pass {{ from: {cidr} to: 0.0.0.0/0 }}" for cidr in allowed_cidrs
    )

    script=f"""#!/bin/bash
set -eux

apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y dante-server net-tools

NIC=$(ip -o -4 route show to default | awk '{{print $5}}')

if ! id -u {username} >/dev/null 2>&1; then
    useradd -m {username}
fi
echo "{username}:{password}" | chpasswd

cat >/etc/danted.conf <<EOF
logoutput: syslog
internal: 0.0.0.0 port = {port}
external: $NIC
socksmethod: username
user.notprivileged: nobody

{cidr_rules}

client block {{ from: 0.0.0.0/0 to: 0.0.0.0/0 }}
socks pass {{ from: 0.0.0.0/0 to: 0.0.0.0/0 }}
EOF

systemctl enable danted
systemctl restart danted
"""

    with open(path,"w") as f:
        f.write(script)

    os.chmod(path,0o755)

    return path


# =========================
# CONFIG
# =========================

MAX_PROJECTS=3
TOKYO_ZONES=["asia-northeast1-a","asia-northeast1-b","asia-northeast1-c"]
OSAKA_ZONES=["asia-northeast2-a","asia-northeast2-b","asia-northeast2-c"]

SOCKS_PORT=1080
NETWORK_NAME="default"

MIN_DELAY_BETWEEN_INSTANCES=3
MAX_DELAY_BETWEEN_INSTANCES=8
DELAY_BETWEEN_PROJECTS=10


# =========================
# MAIN
# =========================

def main():

    print("Script start")

    # FIX EOF
    if sys.stdin.isatty():
        try:
            input("\nNhấn Enter để chạy (Ctrl+C để hủy)...")
        except KeyboardInterrupt:
            print("\n\n⚠️ Đã hủy trước khi bắt đầu.")
            return
    else:
        print("\n⚠️ Non-interactive mode → auto start")

    print("Running ...")


if __name__=="__main__":
    main()
