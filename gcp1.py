#!/usr/bin/env python3

print("Running script version V25")

import subprocess
import time
import random
import string
import sys
import requests
import signal
from datetime import datetime


HELP_TEXT="""
Hướng dẫn Nếu chọn reg Auto:
Ctrl + C : ấn 1 lần Dừng và xuất List
Ctrl + C : ấn 2 lần Dừng hẳn tiến trình
"""

PORT = 1080

TG_BOT_TOKEN="8532753583:AAEAmeyGi1y8u3kLmOWLCe26zoGMBRca8Fg"
TG_CHAT_ID="-10034421144011"

TG_BOT_TOKEN_2="8261404310:AAGG3lmQuTghCNTcDD4Za_6K3sPkbmFXox4"
TG_CHAT_ID_2="-5232145570"

API_BASE=f"https://api.telegram.org/bot{TG_BOT_TOKEN}"
API_BASE_2=f"https://api.telegram.org/bot{TG_BOT_TOKEN_2}"


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

    if not out:
        print("Không tìm thấy project")
        sys.exit()

    return out.splitlines()



def select_projects(all_projects):

    print("\n===== CHỌN PROJECT =====\n")

    print("1 - All Projects")
    print("2 - Chọn Project thủ công\n")

    print(HELP_TEXT)

    choice=input("Lựa chọn (Enter=1): ").strip()

    if choice=="" or choice=="1":
        return all_projects

    if choice=="2":

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

    return all_projects



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

    return out or "unknown"

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

    user="u"+''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(7))
    pw=''.join(random.choice(string.ascii_letters+string.digits) for _ in range(10))

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



def write_dante(user,pw):

    s=f"""#!/bin/bash
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

    open("startup.sh","w").write(s)

    return "startup.sh"



def get_ip(project,zone,name):

    code,out,err=run([
        "gcloud","compute","instances","describe",name,
        f"--project={project}",
        f"--zone={zone}",
        "--format=value(networkInterfaces[0].accessConfigs[0].natIP)"
    ])

    return out



def create_vm(project,zone):

    name=random_vm()
    user,pw=random_user_pass()

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

    ip=get_ip(project,zone,name)

    if ip:
        return f"{ip}:{PORT}:{user}:{pw}"

    return None



def main():

    mode=select_mode()

    all_projects=get_projects()

    projects=select_projects(all_projects)

    proxies=[]

    while True:

        for project in projects:

            if STOP_REQUEST:
                break

            ensure_firewall(project)

            for z in REGION1_ZONES:

                if count_instances(project,REGION1_NAME)>=VM_PER_REGION:
                    break

                p=create_vm(project,z)

                if p:
                    proxies.append(p)

            for z in REGION2_ZONES:

                if count_instances(project,REGION2_NAME)>=VM_PER_REGION:
                    break

                p=create_vm(project,z)

                if p:
                    proxies.append(p)

        if mode==1:
            break

        if STOP_REQUEST:
            break


    print("\nExporting proxy...\n")

    with open(OUTPUT_FILE,"w") as f:

        f.write(f"Tổng Số Proxies : {len(proxies)}\n\n")
        f.write(f"{TODAY}---- {ACCOUNT_EMAIL}--\n")

        for p in proxies:
            f.write(p+"\n")

    tg_send_file(OUTPUT_FILE,f"{len(proxies)} Proxy đã được tạo")


if __name__=="__main__":
    main()
