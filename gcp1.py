#!/usr/bin/env python3

import subprocess
import time
import random
import string
import sys
import requests
from datetime import datetime


# ===== CONFIG =====

PORT = 1080

TG_BOT_TOKEN="8261404310:AAGG3lmQuTghCNTcDD4Za_6K3sPkbmFXox4"
TG_CHAT_ID="-5232145570"

API_BASE = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"


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

VM_PER_REGION = 4
PROJECT_LIMIT = 3


# ===== RUN COMMAND =====

def run(cmd):

    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    return p.returncode,p.stdout.strip(),p.stderr.strip()


# ===== FIREWALL =====

def ensure_firewall(project):

    code,out,err = run([
        "gcloud","compute","firewall-rules","list",
        f"--project={project}",
        "--filter=name=allow-socks",
        "--format=value(name)"
    ])

    if out.strip():
        return

    run([
        "gcloud","compute","firewall-rules","create","allow-socks",
        f"--project={project}",
        "--allow=tcp:1080",
        "--direction=INGRESS",
        "--priority=1000",
        "--network=default"
    ])


# ===== GET GCLOUD ACCOUNT =====

def get_gcloud_account():

    code,out,err = run([
        "gcloud",
        "config",
        "get-value",
        "account"
    ])

    if out:
        return out.strip()

    return "unknown_account"


ACCOUNT_EMAIL = get_gcloud_account()
OUTPUT_FILE = f"{ACCOUNT_EMAIL}.txt"

TODAY = datetime.now().strftime("%d/%m")


# ===== TELEGRAM =====

def tg_send_file(filepath,caption):

    try:

        with open(filepath,"rb") as f:

            requests.post(
                f"{API_BASE}/sendDocument",
                data={
                    "chat_id":TG_CHAT_ID,
                    "caption":caption
                },
                files={"document":f},
                timeout=30
            )

    except:
        pass


# ===== RANDOM USER PASS =====

def random_user_pass():

    user="u"+"".join(random.choice(string.ascii_lowercase+string.digits) for _ in range(7))

    pw="".join(random.choice(string.ascii_letters+string.digits) for _ in range(10))

    return user,pw


# ===== RANDOM VM NAME =====

def random_vm():

    first=[
    "kenshiro","raventon","hartwell","delvinar","calderon",
    "trenwick","marvello","brenford","alverton","norvello"
    ]

    second=[
    "eto","kor","lex","tor","ziv",
    "nex","var","zen","tal","vex"
    ]

    number=random.randint(100,999)

    return f"{random.choice(first)}-{random.choice(second)}{number}"


# ===== COUNT INSTANCES =====

def count_instances(project,region):

    code,out,err=run([
        "gcloud","compute","instances","list",
        f"--project={project}",
        "--format=value(zone)"
    ])

    zones=out.splitlines()

    count=0

    for z in zones:
        if region in z:
            count+=1

    return count


# ===== SOCKS STARTUP SCRIPT =====

def write_dante(user,pw):

    script=f"""#!/bin/bash

apt-get update -y
apt-get install -y dante-server

NIC=$(ip -o -4 route show to default | awk '{{print $5}}')

useradd -m {user}
echo "{user}:{pw}" | chpasswd

cat >/etc/danted.conf <<EOF

logoutput: syslog

internal: 0.0.0.0 port = {PORT}
external: $NIC

socksmethod: username

user.notprivileged: nobody

client pass {{
from: 0.0.0.0/0 to: 0.0.0.0/0
}}

socks pass {{
from: 0.0.0.0/0 to: 0.0.0.0/0
}}

EOF

systemctl restart danted
systemctl enable danted
"""

    with open("startup.sh","w") as f:
        f.write(script)

    return "startup.sh"


# ===== GET VM IP =====

def get_ip(project,zone,name):

    code,out,err=run([
        "gcloud","compute","instances","describe",name,
        f"--project={project}",
        f"--zone={zone}",
        "--format=value(networkInterfaces[0].accessConfigs[0].natIP)"
    ])

    return out


# ===== CREATE VM =====

def create_vm(project,zone,name,user,pw,status):

    status[0]=f"Tạo VM {zone}"

    script=write_dante(user,pw)

    code,out,err=run([
        "gcloud","compute","instances","create",name,
        f"--project={project}",
        f"--zone={zone}",
        "--machine-type=e2-micro",
        "--image-family=debian-11",
        "--image-project=debian-cloud",
        f"--metadata-from-file=startup-script={script}",
        "--tags=socks"
    ])

    if code==0:
        return True

    if "ZONE_RESOURCE_POOL_EXHAUSTED" in err:
        status[0]=f"Zone {zone} hết tài nguyên"
    else:
        status[0]="Lỗi tạo VM"

    return False


# ===== TRY REGION =====

def try_region(project,region,zones,status):

    name=random_vm()
    user,pw=random_user_pass()

    for zone in zones:

        ok=create_vm(project,zone,name,user,pw,status)

        if ok:

            status[0]="VM tạo xong"

            time.sleep(8)

            status[0]="Đang lấy IP"

            ip=get_ip(project,zone,name)

            if ip:

                status[0]="Proxy sẵn sàng"

                return f"{ip}:{PORT}:{user}:{pw}"

    status[0]="Region không tạo được VM"

    return None


# ===== UI =====

def draw_ui(done,total,tokyo,osaka,status,frame):

    if total==0:
        percent=0
        filled=0
    else:
        percent=int((done/total)*100)
        bar_length=32
        filled=int(bar_length*done/total)

    bar_length=32
    bar="█"*filled+"░"*(bar_length-filled)

    spinner=["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

    spin=spinner[frame%len(spinner)]

    sys.stdout.write("\033[H")
    sys.stdout.write("\033[J")

    print("Tiến trình tạo Proxy ....\n")

    print(f"[{bar}]")
    print(f"\n                {percent}%\n")

    print(f"Created: {done} / {total}")
    print(f"Tokyo : {tokyo} / 4")
    print(f"Osaka : {osaka} / 4\n")

    print(f"Status: {status[0]} {spin}")

    sys.stdout.flush()


# ===== MAIN =====

def main():

    code,out,err=run([
        "gcloud","projects","list",
        "--format=value(projectId)"
    ])

    projects=out.splitlines()

    if not projects:
        print("Không tìm thấy project GCP.")
        return

    projects=projects[:PROJECT_LIMIT]

    proxies=[]

    target=len(projects)*VM_PER_REGION*2

    frame=0
    status=["Khởi động"]

    while len(proxies)<target:

        for project in projects:

            ensure_firewall(project)

            tokyo=count_instances(project,"asia-northeast1")
            osaka=count_instances(project,"asia-northeast2")

            draw_ui(len(proxies),target,tokyo,osaka,status,frame)

            frame+=1

            if tokyo<VM_PER_REGION:

                status[0]="Tạo proxy Tokyo"

                proxy=try_region(project,"tokyo",TOKYO_ZONES,status)

                if proxy:
                    proxies.append(proxy)

            elif osaka<VM_PER_REGION:

                status[0]="Tạo proxy Osaka"

                proxy=try_region(project,"osaka",OSAKA_ZONES,status)

                if proxy:
                    proxies.append(proxy)

            else:

                status[0]="Project đủ VM"

            time.sleep(0.2)

    status[0]="Hoàn thành"

    draw_ui(len(proxies),target,4,4,status,frame)

    print("\n\nDanh sách proxy:\n")

    for p in proxies:
        print(p)

    with open(OUTPUT_FILE,"w") as f:

        f.write(f"Tổng Số Proxies : {len(proxies)}\n\n")
        f.write(f"{TODAY}---- {ACCOUNT_EMAIL}--\n")

        for p in proxies:
            f.write(p+"\n")

    tg_send_file(OUTPUT_FILE,f"{len(proxies)} Proxy đã được tạo")


if __name__=="__main__":
    main()
