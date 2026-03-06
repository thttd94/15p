#!/usr/bin/env python3

print("Running script version V24.2")

import subprocess
import time
import random
import string
import sys
import requests
import signal
from datetime import datetime


PORT = 1080

TG_BOT_TOKEN="8261404310:AAGG3lmQuTghCNTcDD4Za_6K3sPkbmFXox4"
TG_CHAT_ID="-5232145570"

API_BASE = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"


TOKYO_ZONES=[
"us-central1-a",
"us-central1-b",
"us-central1-c",
"us-central1-f"
]

OSAKA_ZONES=[
"us-east1-b-d",
"us-east1-b-b",
"us-east1-b-c"
]


VM_PER_REGION=4
PROJECT_LIMIT=3


STOP_REQUEST=False


def handle_ctrlc(sig,frame):

    global STOP_REQUEST

    if not STOP_REQUEST:
        print("\nStopping VM creation, exporting proxy...")
        STOP_REQUEST=True
    else:
        print("\nForce exit")
        sys.exit(0)

signal.signal(signal.SIGINT,handle_ctrlc)



def run(cmd):

    p=subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    return p.returncode,p.stdout.strip(),p.stderr.strip()



# ===== BILLING DETECT =====

def get_billing():

    code,out,err=run([
        "gcloud","billing","accounts","list",
        "--format=value(name)"
    ])

    if not out:
        print("Không tìm thấy billing account")
        sys.exit()

    billing=out.splitlines()[0].split("/")[-1]

    print(f"Billing detected: {billing}")

    return billing



# ===== PROJECT LIST =====

def get_projects_from_billing(billing):

    code,out,err=run([
        "gcloud","beta","billing","projects","list",
        f"--billing-account={billing}",
        "--format=value(projectId)"
    ])

    if not out:
        print("Không tìm thấy project thuộc billing này")
        sys.exit()

    return out.splitlines()



# ===== FIREWALL =====

def ensure_firewall(project):

    code,out,err=run([
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



# ===== ACCOUNT =====

def get_account():

    code,out,err=run([
        "gcloud","config","get-value","account"
    ])

    if out:
        return out

    return "unknown_account"


ACCOUNT_EMAIL=get_account()
OUTPUT_FILE=f"{ACCOUNT_EMAIL}.txt"
TODAY=datetime.now().strftime("%d/%m")



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



# ===== RANDOM =====

def random_user_pass():

    user="u"+"".join(random.choice(string.ascii_lowercase+string.digits) for _ in range(7))
    pw="".join(random.choice(string.ascii_letters+string.digits) for _ in range(10))

    return user,pw


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



# ===== COUNT =====

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



# ===== STARTUP =====

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



# ===== GET IP =====

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
        status[0]=f"Zone {zone} full"

    return False



def try_region(project,zones,status):

    name=random_vm()
    user,pw=random_user_pass()

    for zone in zones:

        ok=create_vm(project,zone,name,user,pw,status)

        if ok:

            time.sleep(8)

            ip=get_ip(project,zone,name)

            if ip:
                return f"{ip}:{PORT}:{user}:{pw}"

    return None



# ===== UI =====

def draw_ui(done,total,tokyo,osaka,status):

    percent=int((done/total)*100) if total else 0

    bar_len=32
    filled=int(bar_len*done/total) if total else 0

    bar="█"*filled+"░"*(bar_len-filled)

    sys.stdout.write("\033[H\033[J")

    print("Tiến trình tạo Proxy ....\n")
    print(f"[{bar}]")
    print(f"\n{percent}%\n")

    print(f"Created: {done} / {total}")
    print(f"Tokyo : {tokyo} / 4")
    print(f"Osaka : {osaka} / 4\n")

    print(f"Status: {status[0]}")



# ===== PROJECT SELECT =====

def select_projects(all_projects):

    print("\n===== CHỌN PROJECT =====\n")
    print("1 - All Projects")
    print("2 - Chọn Project thủ công\n")

    choice=input("Lựa chọn của bạn: ").strip()

    if choice=="1":
        return all_projects

    if choice=="2":

        print("\nDanh sách project:\n")

        for i,p in enumerate(all_projects):
            print(f"{i+1} - {p}")

        sel=input("\nNhập số project (vd: 1,2): ")

        ids=[int(x.strip())-1 for x in sel.split(",") if x.strip().isdigit()]

        selected=[]

        for i in ids:
            if 0<=i<len(all_projects):
                selected.append(all_projects[i])

        if not selected:
            print("Không chọn project hợp lệ")
            sys.exit()

        return selected

    print("Lựa chọn không hợp lệ")
    sys.exit()



# ===== MAIN =====

def main():

    billing=get_billing()

    all_projects=get_projects_from_billing(billing)[:PROJECT_LIMIT]

    projects=select_projects(all_projects)

    proxies=[]
    target=len(projects)*8

    status=["Starting"]

    while len(proxies)<target and not STOP_REQUEST:

        for project in projects:

            if STOP_REQUEST:
                break

            ensure_firewall(project)

            tokyo=count_instances(project,"asia-northeast1")
            osaka=count_instances(project,"asia-northeast2")

            draw_ui(len(proxies),target,tokyo,osaka,status)

            if osaka<VM_PER_REGION:

                status[0]=f"Tạo Osaka ({project})"

                proxy=try_region(project,OSAKA_ZONES,status)

                if proxy:
                    proxies.append(proxy)

            if tokyo<VM_PER_REGION:

                status[0]=f"Tạo Tokyo ({project})"

                proxy=try_region(project,TOKYO_ZONES,status)

                if proxy:
                    proxies.append(proxy)

            time.sleep(0.3)


    print("\nExporting proxy...\n")

    with open(OUTPUT_FILE,"w") as f:

        f.write(f"Tổng Số Proxies : {len(proxies)}\n\n")
        f.write(f"{TODAY}---- {ACCOUNT_EMAIL}--\n")

        for p in proxies:
            f.write(p+"\n")

    tg_send_file(OUTPUT_FILE,f"{len(proxies)} Proxy đã được tạo")


if __name__=="__main__":
    main()
