#!/usr/bin/env python3
print("Running script version V19.4")

import subprocess
import random
import string
import time
import sys
import requests
from datetime import datetime

# =========================
# CONFIG
# =========================

MAX_VM = 24
TOKYO_LIMIT = 4
OSAKA_LIMIT = 4

TOKYO_ZONE = "asia-northeast1-a"
OSAKA_ZONE = "asia-northeast2-a"

MACHINE = "e2-micro"

TG_BOT_TOKEN = "8261404310:AAGG3lmQuTghCNTcDD4Za_6K3sPkbmFXox4"
TG_CHAT_ID = "-5232145570"

# =========================
# TELEGRAM
# =========================

def tg_send_file(file_path, caption):
    if not TG_BOT_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendDocument"

    with open(file_path,"rb") as f:
        requests.post(url,data={
            "chat_id":TG_CHAT_ID,
            "caption":caption
        },files={"document":f})

# =========================
# UTILS
# =========================

def run(cmd):
    return subprocess.getoutput(cmd)

def random_name():
    return ''.join(random.choices(string.ascii_lowercase+string.digits,k=6))+"-"+''.join(random.choices(string.ascii_lowercase+string.digits,k=6))

def random_user():
    return ''.join(random.choices(string.ascii_lowercase,k=8))

def random_pass():
    return ''.join(random.choices(string.ascii_letters+string.digits,k=10))

# =========================
# FIREWALL
# =========================

def ensure_firewall(project):

    check=run(f"gcloud compute firewall-rules describe allow-socks --project {project}")

    if "not found" in check.lower():

        print("Enable firewall 1080")

        run(f"""
gcloud compute firewall-rules create allow-socks \
--allow tcp:1080 \
--network default \
--direction INGRESS \
--priority 1000 \
--project {project}
""")

# =========================
# CREATE VM
# =========================

def create_vm(project,zone):

    name=random_name()
    user=random_user()
    password=random_pass()

    startup=f"""
apt update
apt install dante-server -y

cat > /etc/danted.conf <<EOF
logoutput: stderr
internal: 0.0.0.0 port = 1080
external: eth0
method: username none
user.privileged: root
user.unprivileged: nobody
user.libwrap: nobody
client pass {{
 from: 0.0.0.0/0 to: 0.0.0.0/0
 log: error
}}
pass {{
 from: 0.0.0.0/0 to: 0.0.0.0/0
 protocol: tcp udp
}}
EOF

useradd -M {user}
echo "{user}:{password}" | chpasswd

systemctl restart danted
"""

    cmd=f"""
gcloud compute instances create {name} \
--project {project} \
--zone {zone} \
--machine-type {MACHINE} \
--image-family debian-11 \
--image-project debian-cloud \
--metadata proxy_user={user},proxy_pass={password},startup-script='{startup}'
"""

    out=run(cmd)

    if "error" in out.lower():
        return False

    return True

# =========================
# COUNT VM
# =========================

def count_vm(project):

    tokyo=run(f"gcloud compute instances list --project {project} --filter='zone:({TOKYO_ZONE})' --format='value(name)' | wc -l")
    osaka=run(f"gcloud compute instances list --project {project} --filter='zone:({OSAKA_ZONE})' --format='value(name)' | wc -l")

    return int(tokyo),int(osaka)

# =========================
# EXPORT PROXY
# =========================

def export_proxy(projects):

    print("\nStatus: Dang xuat proxy...\n")

    proxies=[]

    for p in projects:

        data=run(f"""
gcloud compute instances list \
--project {p} \
--format='value(name,zone)'
""")

        for line in data.splitlines():

            try:
                name,zone=line.split()

                ip=run(f"""
gcloud compute instances describe {name} \
--zone {zone} \
--project {p} \
--format='value(networkInterfaces[0].accessConfigs[0].natIP)'
""")

                user=run(f"""
gcloud compute instances describe {name} \
--zone {zone} \
--project {p} \
--format='value(metadata.items.proxy_user)'
""")

                password=run(f"""
gcloud compute instances describe {name} \
--zone {zone} \
--project {p} \
--format='value(metadata.items.proxy_pass)'
""")

                if ip and user and password:

                    proxies.append(f"{ip}:1080:{user}:{password}")

            except:
                pass

    file_name="list.txt"

    with open(file_name,"w") as f:

        f.write(f"Tong So Proxies : {len(proxies)}\n\n")

        date=datetime.now().strftime("%d/%m")

        email=run("gcloud config get-value account")

        f.write(f"{date}---- {email}--\n")

        for p in proxies:
            f.write(p+"\n")

    print("Done. Proxy exported.")

    tg_send_file(file_name,f"✅ {len(proxies)} Proxy da duoc tao")

# =========================
# MAIN
# =========================

def main():

    projects=run("gcloud projects list --format='value(projectId)'").splitlines()[:3]

    created=0

    try:

        while created < MAX_VM:

            for p in projects:

                ensure_firewall(p)

                tokyo,osaka=count_vm(p)

                if tokyo < TOKYO_LIMIT:

                    print(f"Status: Tao VM Tokyo ({p})")

                    ok=create_vm(p,TOKYO_ZONE)

                    if ok:
                        created+=1

                elif osaka < OSAKA_LIMIT:

                    print(f"Status: Tao VM Osaka ({p})")

                    ok=create_vm(p,OSAKA_ZONE)

                    if ok:
                        created+=1

                print(f"\nCreated: {created} / {MAX_VM}\n")

                if created >= MAX_VM:
                    break

            time.sleep(2)

    except KeyboardInterrupt:

        print("\nCtrl+C detected")

    export_proxy(projects)

main()
