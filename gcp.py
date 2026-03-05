#!/usr/bin/env python3
print("\n===== GCP PROXY SCRIPT V15.1 =====\n")

import subprocess
import random
import string
import sys
from datetime import datetime
import requests

# ================= CONFIG =================

TOKYO_ZONES=[
"asia-northeast1-a",
"asia-northeast1-b",
"asia-northeast1-c"
]

OSAKA_ZONES=[
"asia-northeast2-a",
"asia-northeast2-b",
"asia-northeast2-c"
]

VM_PER_REGION=4
MAX_PROJECT=3
TARGET_TOTAL=24

OUTPUT_FILE="list.txt"

TG_BOT_TOKEN="8261404310:AAGG3lmQuTghCNTcDD4Za_6K3sPkbmFXox4"
TG_CHAT_ID="-5232145570"

# ================= RUN =================

def run(cmd):

    p=subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    return p.stdout.strip()

# ================= UI =================

def draw_ui(done,total,tokyo,osaka,status):

    percent=int((done/total)*100)

    bar_len=30
    filled=int(bar_len*percent/100)

    bar="█"*filled+"░"*(bar_len-filled)

    sys.stdout.write("\033[H\033[J")

    print(f"Created: {done} / {total}")
    print(f"Tokyo : {tokyo} / 4")
    print(f"Osaka : {osaka} / 4\n")

    print("ScriptV15.1: Tiến trình đang thực hiện ...\n")

    print(f"[{bar}]\n")

    print(f" {percent}%\n")

    print(f"Status: {status}")

# ================= FIREWALL =================

def ensure_firewall(project):

    run([
    "gcloud","compute","firewall-rules","create","allow-socks",
    "--project",project,
    "--allow","tcp:1080",
    "--direction","INGRESS",
    "--priority","1000",
    "--network","default",
    "--target-tags","socks"
    ])

# ================= RANDOM =================

names=[
"kenshiro","marvello","norvello","calderon",
"trenwick","raventon","valerion","dreswick"
]

def vm_name():

    a=random.choice(names)
    b=random.choice(names)

    return f"{a}-{b}{random.randint(10,999)}"

def random_user():

    return "u"+''.join(random.choice(string.ascii_lowercase) for _ in range(7))

def random_pass():

    return ''.join(random.choice(string.ascii_letters+string.digits) for _ in range(10))

# ================= EXISTING =================

def existing_vm(project):

    out=run([
    "gcloud","compute","instances","list",
    "--project",project,
    "--filter=tags.items=socks",
    "--format=value(name,zone)"
    ])

    tokyo=0
    osaka=0

    for l in out.splitlines():

        if "asia-northeast1" in l:
            tokyo+=1

        if "asia-northeast2" in l:
            osaka+=1

    return tokyo,osaka

# ================= CREATE VM =================

def create_vm(project,zone,user,pw):

    name=vm_name()

    startup=f"""
#!/bin/bash
apt update -y
apt install dante-server -y

cat > /etc/danted.conf <<EOF
logoutput: syslog
internal: 0.0.0.0 port = 1080
external: eth0
method: username
user.privileged: root
user.unprivileged: nobody
client pass {{
from: 0.0.0.0/0 to: 0.0.0.0/0
}}
pass {{
from: 0.0.0.0/0 to: 0.0.0.0/0
protocol: tcp udp
method: username
}}
EOF

useradd {user}
echo "{user}:{pw}" | chpasswd

systemctl restart danted
systemctl enable danted
"""

    open("startup.sh","w").write(startup)

    out=run([
    "gcloud","compute","instances","create",name,
    "--project",project,
    "--zone",zone,
    "--machine-type","e2-micro",
    "--image-family","debian-11",
    "--image-project","debian-cloud",
    "--metadata-from-file","startup-script=startup.sh",
    "--metadata",f"proxy_user={user},proxy_pass={pw}",
    "--tags","socks"
    ])

    if "ERROR" in out:
        return None

    ip=run([
    "gcloud","compute","instances","describe",name,
    "--project",project,
    "--zone",zone,
    "--format=value(networkInterfaces[0].accessConfigs[0].natIP)"
    ])

    return f"{ip}:1080:{user}:{pw}"

# ================= EXPORT =================

def export_all():

    total=0

    date=datetime.now().strftime("%d/%m")
    email=run(["gcloud","config","get-value","account"])

    with open(OUTPUT_FILE,"w") as f:

        f.write(f"Tổng Số Proxies : {TARGET_TOTAL}\n\n")
        f.write(f"{date}---- {email}--\n")

        projects=run([
        "gcloud","projects","list",
        "--format=value(projectId)"
        ]).splitlines()[:MAX_PROJECT]

        for p in projects:

            inst=run([
            "gcloud","compute","instances","list",
            "--project",p,
            "--filter=tags.items=socks",
            "--format=value(name,zone)"
            ]).splitlines()

            for i in inst:

                parts=i.split()

                if len(parts) != 2:
                    continue

                name,zone=parts

                info=run([
                "gcloud","compute","instances","describe",name,
                "--project",p,
                "--zone",zone,
                "--format=value(networkInterfaces[0].accessConfigs[0].natIP,metadata.items.proxy_user,metadata.items.proxy_pass)"
                ])

                data=info.split()

                if len(data) != 3:
                    continue

                ip,user,pw=data

                f.write(f"{ip}:1080:{user}:{pw}\n")

                total+=1

    return total

# ================= TELEGRAM =================

def tg_send():

    url=f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendDocument"

    files={"document":open(OUTPUT_FILE,"rb")}

    data={
    "chat_id":TG_CHAT_ID,
    "caption":"✅ PROXY CREATED"
    }

    requests.post(url,data=data,files=files)

# ================= MAIN =================

def main():

    projects=run([
    "gcloud","projects","list",
    "--format=value(projectId)"
    ]).splitlines()[:MAX_PROJECT]

    done=0

    try:

        for p in projects:

            ensure_firewall(p)

            tokyo,osaka=existing_vm(p)

            done+=tokyo+osaka

            draw_ui(done,TARGET_TOTAL,tokyo,osaka,"Đang kiểm tra project")

            if tokyo>=4 and osaka>=4:

                draw_ui(done,TARGET_TOTAL,tokyo,osaka,"Project đã đủ VM")

                continue

            for z in TOKYO_ZONES:

                while tokyo<4:

                    user=random_user()
                    pw=random_pass()

                    proxy=create_vm(p,z,user,pw)

                    if proxy:

                        tokyo+=1
                        done+=1

                    draw_ui(done,TARGET_TOTAL,tokyo,osaka,"Tạo VM Tokyo")

                    if tokyo>=4:
                        break

            for z in OSAKA_ZONES:

                while osaka<4:

                    user=random_user()
                    pw=random_pass()

                    proxy=create_vm(p,z,user,pw)

                    if proxy:

                        osaka+=1
                        done+=1

                    draw_ui(done,TARGET_TOTAL,tokyo,osaka,"Tạo VM Osaka")

                    if osaka>=4:
                        break

        draw_ui(TARGET_TOTAL,TARGET_TOTAL,4,4,"Đang xuất proxy...")

        export_all()

        tg_send()

        print("\nDone. Proxy exported.")

    except KeyboardInterrupt:

        print("\nStop requested → exporting proxy...")

        export_all()

        tg_send()

if __name__=="__main__":
    main()
