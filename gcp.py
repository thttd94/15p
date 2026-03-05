#!/usr/bin/env python3
print("Running script version V19")

import subprocess
import time
import random
import string
import sys
import requests
from datetime import datetime

# =========================
# CONFIG
# =========================

TARGET_PER_ZONE = 4
MAX_PROJECTS = 3

TOKYO = "asia-northeast1-a"
OSAKA = "asia-northeast2-a"

MACHINE = "e2-micro"
IMAGE = "debian-11"

TG_BOT_TOKEN = ""
TG_CHAT_ID = ""

# =========================
# UTILS
# =========================

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except:
        return ""

def randstr(n=8):
    return ''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(n))

# =========================
# TELEGRAM
# =========================

def tg_send_file(file, caption):

    if not TG_BOT_TOKEN:
        return

    url=f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendDocument"

    try:
        requests.post(url, data={"chat_id":TG_CHAT_ID,"caption":caption}, files={"document":open(file,"rb")}, timeout=20)
    except:
        pass

# =========================
# FIREWALL
# =========================

def ensure_firewall(project):

    chk = run(f"gcloud compute firewall-rules describe allow-socks --project {project}")

    if chk:
        return

    subprocess.run(f"""
gcloud compute firewall-rules create allow-socks \
--allow tcp:1080 \
--direction INGRESS \
--priority 1000 \
--network default \
--project {project}
""",shell=True)

# =========================
# COUNT VM
# =========================

def count_vm(project):

    tokyo=0
    osaka=0

    data = run(f"gcloud compute instances list --project {project} --format='value(zone)'")

    for z in data.splitlines():

        if "asia-northeast1" in z:
            tokyo+=1

        if "asia-northeast2" in z:
            osaka+=1

    return tokyo,osaka

# =========================
# CREATE VM
# =========================

def create_vm(project,zone):

    name=f"proxy-{randstr(6)}"
    user=f"u{randstr(6)}"
    pw=randstr(10)

    startup=f"""
#!/bin/bash
apt update -y
apt install -y dante-server curl

useradd -m {user}
echo '{user}:{pw}' | chpasswd

IP=$(curl -s ifconfig.me)

echo "$IP:1080:{user}:{pw}" > /root/list.txt

cat >/etc/danted.conf <<EOF
logoutput: syslog
internal: 0.0.0.0 port = 1080
external: eth0
method: username
user.notprivileged: nobody

client pass {{
 from: 0.0.0.0/0 to: 0.0.0.0/0
 log: connect disconnect error
}}

pass {{
 from: 0.0.0.0/0 to: 0.0.0.0/0
 protocol: tcp udp
}}
EOF

systemctl restart danted
"""

    cmd=f"""
gcloud compute instances create {name} \
--project {project} \
--zone {zone} \
--machine-type {MACHINE} \
--image-family {IMAGE} \
--image-project debian-cloud \
--metadata startup-script='{startup}'
"""

    p=subprocess.run(cmd,shell=True)

    return p.returncode==0

# =========================
# EXPORT PROXY
# =========================

def export_proxy():

    out="list.txt"
    open(out,"w").close()

    projects = run("gcloud projects list --format='value(projectId)'").splitlines()

    total=0

    for p in projects[:MAX_PROJECTS]:

        data = run(f"gcloud compute instances list --project {p} --format='value(name,zone)'")

        for line in data.splitlines():

            name,zone=line.split()

            proxy = run(f"gcloud compute ssh {name} --zone {zone} --project {p} --command 'cat /root/list.txt'")

            if proxy:

                with open(out,"a") as f:
                    f.write(proxy+"\n")

                total+=1

    return total,out

# =========================
# MAIN LOOP
# =========================

def main():

    projects = run("gcloud projects list --format='value(projectId)'").splitlines()[:MAX_PROJECTS]

    created=0

    try:

        while True:

            for p in projects:

                ensure_firewall(p)

                tokyo,osaka = count_vm(p)

                if tokyo < TARGET_PER_ZONE:

                    print(f"Status: Tao VM Tokyo ({p})")

                    ok=create_vm(p,TOKYO)

                    if ok:
                        created+=1

                elif osaka < TARGET_PER_ZONE:

                    print(f"Status: Tao VM Osaka ({p})")

                    ok=create_vm(p,OSAKA)

                    if ok:
                        created+=1

                else:

                    print(f"Status: Project da du VM ({p})")

                print(f"Created: {created} / 24")
                time.sleep(2)

    except KeyboardInterrupt:

        print("\nDang xuat proxy...")

        total,file = export_proxy()

        print("Done. Proxy exported.")

        email = run("gcloud auth list --filter=status:ACTIVE --format='value(account)'")

        now=datetime.now().strftime("%d/%m")

        with open(file,"r+") as f:
            data=f.read()
            f.seek(0)
            f.write(f"Tong So Proxies : {total}\n\n{now}---- {email}--\n"+data)

        tg_send_file(file,f"✅ {total} Proxy da duoc tao")


if __name__=="__main__":
    main()
