#!/usr/bin/env python3
print("Running script version V20.3")

import subprocess
import random
import string
import time
import requests
from datetime import datetime

MAX_VM = 24
TOKYO_LIMIT = 4
OSAKA_LIMIT = 4

TOKYO = "asia-northeast1-a"
OSAKA = "asia-northeast2-a"

MACHINE = "e2-micro"

TG_BOT_TOKEN="8261404310:AAGG3lmQuTghCNTcDD4Za_6K3sPkbmFXox4"
TG_CHAT_ID="-5232145570"

# ======================

def run(cmd):
    return subprocess.getoutput(cmd)

def rand(n=6):
    return ''.join(random.choices(string.ascii_lowercase+string.digits,k=n))

def vm_name():
    return rand(5)+"-"+rand(6)

def user():
    return rand(8)

def passwd():
    return rand(10)

# ======================

def ensure_firewall(project):

    check = run(f"gcloud compute firewall-rules list --project {project}")

    if "allow-socks" not in check:

        print(f"Enable firewall 1080 for {project}")

        run(f"""
gcloud compute firewall-rules create allow-socks \
--allow tcp:1080 \
--direction INGRESS \
--priority 1000 \
--network default \
--project {project}
""")

# ======================

def safe_count(cmd):

    out = run(cmd+" 2>/dev/null")

    try:
        return int(out.splitlines()[-1])
    except:
        return 0

def count(project):

    tokyo=safe_count(f"""
gcloud compute instances list \
--project {project} \
--filter="zone:{TOKYO}" \
--format="value(name)" | wc -l
""")

    osaka=safe_count(f"""
gcloud compute instances list \
--project {project} \
--filter="zone:{OSAKA}" \
--format="value(name)" | wc -l
""")

    return tokyo,osaka

# ======================

def create_vm(project,zone):

    name=vm_name()
    u=user()
    p=passwd()

    startup=f"""
apt update
apt install dante-server -y

useradd -M {u}
echo "{u}:{p}" | chpasswd

cat > /etc/danted.conf <<EOF
logoutput: stderr
internal: 0.0.0.0 port = 1080
external: eth0
method: username none
user.privileged: root
user.unprivileged: nobody
client pass {{
 from: 0.0.0.0/0 to: 0.0.0.0/0
}}
pass {{
 from: 0.0.0.0/0 to: 0.0.0.0/0
 protocol: tcp udp
}}
EOF

systemctl restart danted

IP=$(curl -s ifconfig.me)

echo "$IP:1080:{u}:{p}" > /root/list.txt
"""

    cmd=f"""
gcloud compute instances create {name} \
--project {project} \
--zone {zone} \
--machine-type {MACHINE} \
--image-family debian-11 \
--image-project debian-cloud \
--metadata startup-script='{startup}'
"""

    out=run(cmd)

    if "error" in out.lower():
        print("Create VM error or zone full")
        return False

    return True

# ======================

def export_proxy(projects):

    print("\nStatus: Dang xuat proxy...\n")

    proxies=[]

    for p in projects:

        data=run(f"gcloud compute instances list --project {p} --format='value(name,zone)'")

        for line in data.splitlines():

            try:

                name,zone=line.split()

                proxy=run(f"""
gcloud compute ssh {name} \
--project {p} \
--zone {zone} \
--command "cat /root/list.txt" \
--quiet
""")

                if ":" in proxy:
                    proxies.append(proxy.strip())

            except:
                pass

    email=run("gcloud config get-value account")

    file=f"{email}.txt"

    with open(file,"w") as f:

        f.write(f"Tổng Số Proxies : {len(proxies)}\n\n")

        date=datetime.now().strftime("%d/%m")

        f.write(f"{date}---- {email}--\n")

        for p in proxies:
            f.write(p+"\n")

    print("Done. Proxy exported.")

    if TG_BOT_TOKEN:

        url=f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendDocument"

        with open(file,"rb") as f:
            requests.post(url,data={
                "chat_id":TG_CHAT_ID,
                "caption":f"{len(proxies)} Proxy đã được tạo"
            },files={"document":f})

# ======================

def main():

    projects=run("gcloud projects list --format='value(projectId)'").splitlines()[:3]

    for p in projects:
        ensure_firewall(p)

    created=0

    try:

        while created < MAX_VM:

            for p in projects:

                tokyo,osaka=count(p)

                if tokyo < TOKYO_LIMIT:

                    print(f"Status: Tao VM Tokyo ({p})")

                    if create_vm(p,TOKYO):
                        created+=1

                elif osaka < OSAKA_LIMIT:

                    print(f"Status: Tao VM Osaka ({p})")

                    if create_vm(p,OSAKA):
                        created+=1

                else:

                    print(f"Status: Project {p} du VM")

                print(f"\nCreated: {created} / {MAX_VM}\n")

                if created >= MAX_VM:
                    break

            time.sleep(2)

    except KeyboardInterrupt:

        print("\nCtrl+C detected")

    export_proxy(projects)

main()
