#!/usr/bin/env python3
print("Running script version V16")

import subprocess
import random
import string
import time
from datetime import datetime

# =========================
# CONFIG
# =========================

TOKYO_ZONES = ["asia-northeast1-a","asia-northeast1-b","asia-northeast1-c"]
OSAKA_ZONES = ["asia-northeast2-a","asia-northeast2-b","asia-northeast2-c"]

TOKYO_TARGET = 4
OSAKA_TARGET = 4

MAX_PROJECT = 3

MACHINE = "e2-micro"
IMAGE = "debian-11"
IMAGE_PROJECT = "debian-cloud"

SCRIPT_VERSION = "ScriptV16"
OUTPUT_FILE = "list.txt"

# =========================
# UTILS
# =========================

def run(cmd):
    return subprocess.check_output(cmd,shell=True,text=True).strip()

def rand(n):
    return ''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(n))

def draw(done,total,status):
    percent = int(done/total*100) if total else 0
    bar = "█"*int(percent/4)+"░"*(25-int(percent/4))
    print("\033c",end="")
    print(f"Created: {done} / {total}")
    print(f"\n{SCRIPT_VERSION}: Tiến trình đang thực hiện ...\n")
    print("["+bar+"]")
    print(f"\n{percent}%\n")
    print("Status:",status)

# =========================
# FIREWALL
# =========================

def ensure_firewall(project):

    try:
        run(f"gcloud compute firewall-rules describe allow-socks --project {project}")
        return
    except:
        pass

    try:
        run(
        f"gcloud compute firewall-rules create allow-socks "
        f"--allow tcp:1080 "
        f"--direction=INGRESS "
        f"--priority=1000 "
        f"--network=default "
        f"--project {project}"
        )
    except:
        pass


# =========================
# VM COUNT
# =========================

def count_vm(project):

    out = run(f"gcloud compute instances list --project {project} --format='value(zone)'")

    tokyo=0
    osaka=0

    for z in out.splitlines():

        if "asia-northeast1" in z:
            tokyo+=1
        if "asia-northeast2" in z:
            osaka+=1

    return tokyo,osaka


# =========================
# CREATE VM
# =========================

def create_vm(project,zone):

    name = rand(8)
    user = "u"+rand(7)
    pw = rand(10)

    startup=f"""#!/bin/bash
apt update
apt install -y dante-server

cat > /etc/danted.conf <<EOF
logoutput: syslog
internal: 0.0.0.0 port = 1080
external: eth0
method: username
user.notprivileged: nobody

client pass {{
 from: 0.0.0.0/0 to: 0.0.0.0/0
 log: connect disconnect
}}

pass {{
 from: 0.0.0.0/0 to: 0.0.0.0/0
 protocol: tcp udp
 log: connect disconnect
}}
EOF

useradd {user}
echo "{user}:{pw}" | chpasswd

systemctl restart danted
systemctl enable danted
"""

    with open("startup.sh","w") as f:
        f.write(startup)

    cmd=f"""
gcloud compute instances create {name} \
--project {project} \
--zone {zone} \
--machine-type {MACHINE} \
--image-family {IMAGE} \
--image-project {IMAGE_PROJECT} \
--metadata proxy_user={user},proxy_pass={pw} \
--metadata-from-file startup-script=startup.sh
"""

    try:
        run(cmd)
        return True
    except:
        return False


# =========================
# EXPORT PROXY
# =========================

def export_all(projects):

    out=open(OUTPUT_FILE,"w")

    for p in projects:

        try:
            vm=run(f"gcloud compute instances list --project {p} --format='value(name,zone)'")
        except:
            continue

        for line in vm.splitlines():

            parts=line.split()

            if len(parts)!=2:
                continue

            name,zone=parts

            try:

                ip=run(f"gcloud compute instances describe {name} --zone {zone} --project {p} --format='value(networkInterfaces[0].accessConfigs[0].natIP)'")

                user=run(f"gcloud compute instances describe {name} --zone {zone} --project {p} --format='value(metadata.items.proxy_user)'")

                pw=run(f"gcloud compute instances describe {name} --zone {zone} --project {p} --format='value(metadata.items.proxy_pass)'")

                if ip and user and pw:
                    out.write(f"{ip}:1080:{user}:{pw}\n")

            except:
                pass

    out.close()


# =========================
# MAIN
# =========================

def main():

    projects=run("gcloud projects list --format='value(projectId)'").splitlines()[:MAX_PROJECT]

    total_target = MAX_PROJECT*(TOKYO_TARGET+OSAKA_TARGET)

    created=0

    for p in projects:

        ensure_firewall(p)

        tokyo,osaka=count_vm(p)

        created+=tokyo+osaka

    draw(created,total_target,"Đang kiểm tra VM")

    for p in projects:

        tokyo,osaka=count_vm(p)

        while tokyo<TOKYO_TARGET:

            draw(created,total_target,f"Tạo VM Tokyo ({p})")

            for z in TOKYO_ZONES:

                if create_vm(p,z):

                    tokyo+=1
                    created+=1
                    break

            if tokyo>=TOKYO_TARGET:
                break

        while osaka<OSAKA_TARGET:

            draw(created,total_target,f"Tạo VM Osaka ({p})")

            for z in OSAKA_ZONES:

                if create_vm(p,z):

                    osaka+=1
                    created+=1
                    break

            if osaka>=OSAKA_TARGET:
                break

    draw(created,total_target,"Đang xuất proxy...")

    export_all(projects)

    print("\nDone. Proxy exported.")

if __name__=="__main__":
    main()
