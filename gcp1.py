#!/usr/bin/env python3
"""
nano gcp_socks5_multi_auto.py
python3 gcp_socks5_multi_auto.py
"""

import subprocess
import time
import os
import shlex
import random
import string
from typing import List, Tuple, Optional


# =========================
#  HÀM TIỆN ÍCH
# =========================

def run(cmd: List[str], capture_output=False, check=True, retries=3) -> str:
    """Chạy lệnh với retry logic"""
    print(">>>", " ".join(shlex.quote(c) for c in cmd))
    
    for attempt in range(retries):
        try:
            if capture_output:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=60,  # Timeout 60s
                )
                if check and result.returncode != 0:
                    if attempt < retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)  
                        print(f"⚠️ Lỗi, thử lại sau {wait_time:.1f}s... (lần {attempt + 1}/{retries})")
                        time.sleep(wait_time)
                        continue
                    print(result.stderr)
                    raise RuntimeError(f"Lệnh lỗi: {' '.join(cmd)}")
                return result.stdout.strip()
            else:
                result = subprocess.run(cmd, timeout=60)
                if check and result.returncode != 0:
                    if attempt < retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        print(f"⚠️ Lỗi, thử lại sau {wait_time:.1f}s... (lần {attempt + 1}/{retries})")
                        time.sleep(wait_time)
                        continue
                    raise RuntimeError(f"Lệnh lỗi: {' '.join(cmd)}")
                return ""
        except subprocess.TimeoutExpired:
            if attempt < retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"⚠️ Timeout, thử lại sau {wait_time:.1f}s... (lần {attempt + 1}/{retries})")
                time.sleep(wait_time)
                continue
            raise
    
    return ""


# =========================
#   USER / PASS
# =========================

def random_user_pass(user_len: int = 8, pass_len: int = 10) -> Tuple[str, str]:
    """Tạo user/pass random với độ dài khác nhau để tránh pattern"""
    letters = string.ascii_lowercase + string.digits
    user = "u" + "".join(random.choice(letters) for _ in range(user_len - 1))
    pass_chars = string.ascii_letters + string.digits
    pw = "".join(random.choice(pass_chars) for _ in range(pass_len))
    return user, pw


# =========================
#  INSTANCE 
# =========================

def generate_natural_instance_name(region: str, index: int) -> str:
    
    prefixes = [
        "web", "app", "node", "srv", "api", "db", "cache", "proxy", 
        "host", "vm", "cloud", "data", "core", "edge", "gateway",
        "backend", "frontend", "worker", "task", "service"
    ]
    suffixes = [
        "01", "02", "03", "04", "alpha", "beta", "prod", "dev", 
        "test", "main", "east", "west", "north", "south", "01",
        "02", "03", "04", "05", "06", "07", "08"
    ]
    
    format_type = random.choice([1, 2, 3, 4])
    
    if format_type == 1:
        name = f"{random.choice(prefixes)}-{region}-{random.choice(suffixes)}"
    elif format_type == 2:
        name = f"{random.choice(prefixes)}-{region}-{index:02d}"
    elif format_type == 3:
        rand_num = random.randint(100, 999)
        name = f"{random.choice(prefixes)}{rand_num}-{region}"
    else:
        rand_str = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(3))
        name = f"{random.choice(prefixes)}-{region}-{rand_str}"
    
    time.sleep(random.uniform(0.1, 0.5))
    
    return name


# =========================

def write_dante_startup_script(username: str,
                               password: str,
                               port: int,
                               allowed_cidrs: List[str],
                               path: str = "socks5-startup.sh") -> str:
    
    cidr_rules = "\n".join(
        f"client pass {{ from: {cidr} to: 0.0.0.0/0 }}" for cidr in allowed_cidrs
    )
    
    comment = random.choice([
        "# SOCKS5 Proxy Configuration",
        "# Dante Server Setup",
        "# Proxy Server Initialization",
        "# Network Proxy Configuration"
    ])

    script = f"""#!/bin/bash
set -eux

{comment}
# Timestamp: {int(time.time())}

apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y dante-server net-tools

# Lấy tên interface chính
NIC=$(ip -o -4 route show to default | awk '{{print $5}}')

# Tạo user hệ thống
if ! id -u {username} >/dev/null 2>&1; then
    useradd -m {username}
fi
echo "{username}:{password}" | chpasswd

cat >/etc/danted.conf <<EOF
logoutput: syslog

internal: 0.0.0.0 port = {port}
external: $NIC

socksmethod: username
user.notprivileged: nobody

# Cho phép tất cả IP (0.0.0.0/0)
{cidr_rules}

# Quy tắc mặc định: chặn (nhưng ở trên đã pass 0.0.0.0/0)
client block {{ from: 0.0.0.0/0 to: 0.0.0.0/0 }}
socks pass {{ from: 0.0.0.0/0 to: 0.0.0.0/0 }}
EOF

systemctl enable danted
systemctl restart danted

# Thêm delay nhỏ để tránh tất cả instance start cùng lúc
sleep {random.randint(1, 5)}
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    os.chmod(path, 0o755)
    print(f"✔ Đã ghi startup script Dante: {path}")
    return path


# =========================
#  FIREWALL 
# =========================

def ensure_firewall_rule(project_id: str,
                         port: int,
                         fw_name: str,
                         network: str,
                         allowed_cidrs: List[str]):
    """
    Firewall với delay và check trước:
    - Kiểm tra xem rule đã tồn tại chưa
    - Thêm delay random trước khi tạo
    """
    out = run(
        [
            "gcloud",
            "compute",
            "firewall-rules",
            "list",
            f"--project={project_id}",
            f"--filter=name={fw_name}",
            "--format=value(name)",
        ],
        capture_output=True,
        check=False,  
    )
    if out:
        print(f"[{project_id}] Firewall rule '{fw_name}' đã tồn tại.")
        return

    source_ranges = ",".join(allowed_cidrs)
    
    delay = random.uniform(1, 3)
    print(f"[{project_id}] Đợi {delay:.1f}s trước khi tạo firewall rule...")
    time.sleep(delay)

    print(f"[{project_id}] Tạo firewall rule '{fw_name}' (TCP:{port})...")
    run(
        [
            "gcloud",
            "compute",
            "firewall-rules",
            "create",
            fw_name,
            f"--project={project_id}",
            f"--network={network}",
            "--direction=INGRESS",
            "--priority=1000",
            f"--allow=tcp:{port}",
            f"--source-ranges={source_ranges}",
            f"--target-tags={fw_name}",
            "--no-enable-logging",
            "--description=SOCKS5 proxy (open to internet, use responsibly)",
        ]
    )
    print(f"[{project_id}] ✔ Đã tạo firewall rule.")


# =========================
#  QUOTA
# =========================

def check_instance_quota(project_id: str, zone: str, needed: int) -> Tuple[bool, str]:
    """
    Kiểm tra quota instance trước khi tạo
    Trả về (is_ok, message)
    """
    try:
        out = run(
            [
                "gcloud",
                "compute",
                "instances",
                "list",
                f"--project={project_id}",
                f"--zones={zone}",
                "--format=value(name)",
                "--filter=status:RUNNING",
            ],
            capture_output=True,
            check=False,
        )
        running_count = len([l for l in out.splitlines() if l.strip()]) if out else 0
        
        quota_check = run(
            [
                "gcloud",
                "compute",
                "project-info",
                "describe",
                f"--project={project_id}",
                "--format=value(quotas[].limit)",
            ],
            capture_output=True,
            check=False,
        )
        
        if running_count + needed > 20:  
            return False, f"Cảnh báo: Zone {zone} đã có {running_count} instance, sẽ tạo thêm {needed} (tổng: {running_count + needed})"
        
        return True, f"OK: Zone {zone} có {running_count} instance đang chạy, sẽ tạo thêm {needed}"
    except Exception as e:
        print(f"⚠️ Không thể check quota: {e}")
        return True, "Không thể kiểm tra quota, tiếp tục..."


# =========================
#  VM
# =========================

def create_socks5_instance(project_id: str,
                           zone: str,
                           name: str,
                           port: int,
                           username: str,
                           password: str,
                           fw_name: str,
                           allowed_cidrs: List[str],
                           machine_type: str = "e2-micro",
                           image_family: str = "debian-11",
                           image_project: str = "debian-cloud",
                           delay_before: float = 0) -> Optional[str]:
    """

    """
    script_path = write_dante_startup_script(username, password, port, allowed_cidrs)

    if delay_before > 0:
        print(f"[{project_id}] Đợi {delay_before:.1f}s trước khi tạo {name}...")
        time.sleep(delay_before)

    print(f"\n[{project_id}] === TẠO INSTANCE: {name} ({zone}) ===")
    
    try:
        run(
            [
                "gcloud",
                "compute",
                "instances",
                "create",
                name,
                f"--project={project_id}",
                f"--zone={zone}",
                f"--machine-type={machine_type}",
                f"--image-family={image_family}",
                f"--image-project={image_project}",
                f"--tags={fw_name}",
                f"--metadata-from-file=startup-script={script_path}",
                "--no-service-account",
                "--no-scopes",
                "--no-restart-on-failure",
                "--shielded-secure-boot",
                "--shielded-vtpm",
                "--shielded-integrity-monitoring",
                f"--labels=purpose=socks5-proxy,usage=legit-remote-access,created={int(time.time())}",
            ]
        )
        print(f"[{project_id}] ✔ Đã gửi yêu cầu tạo VM '{name}'.")
    except Exception as e:
        print(f"[{project_id}] ❌ Lỗi tạo VM '{name}': {e}")
        return None

    time.sleep(15)  

    ip = None
    for attempt in range(10):  
        try:
            ip = run(
                [
                    "gcloud",
                    "compute",
                    "instances",
                    "describe",
                    name,
                    f"--project={project_id}",
                    f"--zone={zone}",
                    "--format=value(networkInterfaces[0].accessConfigs[0].natIP)",
                ],
                capture_output=True,
                check=False,
            ).strip()
            
            if ip and ip != "None" and len(ip) > 0:
                break
        except Exception as e:
            print(f"⚠️ Lần {attempt + 1}: Chưa có IP, đợi thêm...")
        
        time.sleep(3)  

    if ip and ip != "None":
        print(f"[{project_id}] IP Public của {name}: {ip}")
        return ip
    else:
        print(f"[{project_id}] ⚠️ Không lấy được IP của {name} sau 10 lần thử")
        return None


def get_all_projects(max_projects: int) -> List[str]:
    """Lấy danh sách projects với error handling"""
    try:
        out = run(
            [
                "gcloud",
                "projects",
                "list",
                "--format=value(projectId)",
            ],
            capture_output=True,
        )
        projects = [p.strip() for p in out.splitlines() if p.strip()]
        if max_projects > 0:
            projects = projects[:max_projects]
        return projects
    except Exception as e:
        print(f"❌ Lỗi lấy danh sách projects: {e}")
        return []


# =========================
#  CẤU HÌNH
# =========================

MAX_PROJECTS = 3

TOKYO_ZONES = ["asia-northeast1-a", "asia-northeast1-b", "asia-northeast1-c"]
OSAKA_ZONES = ["asia-northeast2-a", "asia-northeast2-b", "asia-northeast2-c"]

SOCKS_PORT = 1080

NETWORK_NAME = "default"

MIN_DELAY_BETWEEN_INSTANCES = 3  
MAX_DELAY_BETWEEN_INSTANCES = 8  
DELAY_BETWEEN_PROJECTS = 10  


# =========================
#  LUỒNG CHÍNH 
# =========================

def main():
    
    projects = get_all_projects(MAX_PROJECTS)
    if not projects:
        print("❌ Không tìm thấy project nào. Kiểm tra `gcloud projects list`.")
        return

    print("Projects sẽ dùng:", ", ".join(projects))

    socks_user, socks_pass = random_user_pass()
    print(f"\nUSER/PASS RANDOM CHO LẦN CHẠY NÀY:")
    print(f"User : {socks_user}")
    print(f"Pass : {socks_pass}\n")

    allowed_cidrs = ["0.0.0.0/0"]
    print("Allowed CIDRs (Dante + firewall): 0.0.0.0/0  (mở toàn internet)")
    print(f"Tokyo zones (retry a→b→c) : {TOKYO_ZONES}")
    print(f"Osaka zones (retry a→b→c) : {OSAKA_ZONES}")
    print(f"SOCKS port : {SOCKS_PORT}")
    print(f"\n⏱️ DELAY CONFIG:")
    print(f"  - Giữa các instance: {MIN_DELAY_BETWEEN_INSTANCES}-{MAX_DELAY_BETWEEN_INSTANCES}s")
    print(f"  - Giữa các project: {DELAY_BETWEEN_PROJECTS}s")
    print("\n💡 Tip: Nhấn Ctrl+C để dừng script, progress sẽ được lưu tự động")
    try:
        input("\nNhấn Enter để chạy (Ctrl+C để hủy)...")
    except KeyboardInterrupt:
        print("\n\n⚠️ Đã hủy trước khi bắt đầu.")
        return

    all_proxies_by_project = {}

    try:
        for project_idx, project_id in enumerate(projects):
            print(f"\n{'='*60}")
            print(f"PROJECT {project_idx + 1}/{len(projects)}: {project_id}")
            print(f"{'='*60}")
            
            if project_idx > 0:
                print(f"\n⏳ Đợi {DELAY_BETWEEN_PROJECTS}s trước khi xử lý project tiếp theo...")
                try:
                    time.sleep(DELAY_BETWEEN_PROJECTS)
                except KeyboardInterrupt:
                    raise  
            
            fw_name = f"socks-fw-{SOCKS_PORT}"

            print(f"\n[{project_id}] Kiểm tra quota...")
            quota_ok, quota_msg = check_instance_quota(project_id, TOKYO_ZONES[0], 8)
            print(f"[{project_id}] {quota_msg}")
            if not quota_ok:
                response = input(f"[{project_id}] ⚠️ Cảnh báo quota. Tiếp tục? (y/n): ")
                if response.lower() != 'y':
                    print(f"[{project_id}] Bỏ qua project này.")
                    continue

            ensure_firewall_rule(
                project_id=project_id,
                port=SOCKS_PORT,
                fw_name=fw_name,
                network=NETWORK_NAME,
                allowed_cidrs=allowed_cidrs,
            )

            proxies = []

            print(f"\n[{project_id}] Tạo 4 instance Tokyo ...")
            for i in range(1, 5):
                name = generate_natural_instance_name("tokyo", i)
                delay = random.uniform(MIN_DELAY_BETWEEN_INSTANCES, MAX_DELAY_BETWEEN_INSTANCES)
                ip = None
                for zone in TOKYO_ZONES:
                    if ip is not None:
                        break
                    print(f"[{project_id}] Thử zone {zone} cho {name}...")
                    ip = create_socks5_instance(
                        project_id=project_id,
                        zone=zone,
                        name=name,
                        port=SOCKS_PORT,
                        username=socks_user,
                        password=socks_pass,
                        fw_name=fw_name,
                        allowed_cidrs=allowed_cidrs,
                        delay_before=delay if zone == TOKYO_ZONES[0] else 0,
                    )
                    if ip is None and zone != TOKYO_ZONES[-1]:
                        print(f"[{project_id}] Zone {zone} thất bại, thử zone tiếp theo ({TOKYO_ZONES[TOKYO_ZONES.index(zone)+1]})...")
                if ip:
                    proxies.append(f"{ip}:{SOCKS_PORT}:{socks_user}:{socks_pass}")
                
                if i < 4:
                    next_delay = random.uniform(MIN_DELAY_BETWEEN_INSTANCES, MAX_DELAY_BETWEEN_INSTANCES)
                    print(f"[{project_id}] Đợi {next_delay:.1f}s trước instance tiếp theo...")
                    try:
                        time.sleep(next_delay)
                    except KeyboardInterrupt:
                        raise  

            print(f"\n[{project_id}] Đợi {DELAY_BETWEEN_PROJECTS // 2}s trước khi tạo instance Osaka...")
            try:
                time.sleep(DELAY_BETWEEN_PROJECTS // 2)
            except KeyboardInterrupt:
                raise  

            print(f"\n[{project_id}] Tạo 4 instance Osaka ...")
            for i in range(1, 5):
                name = generate_natural_instance_name("osaka", i)
                delay = random.uniform(MIN_DELAY_BETWEEN_INSTANCES, MAX_DELAY_BETWEEN_INSTANCES)
                ip = None
                for zone in OSAKA_ZONES:
                    if ip is not None:
                        break
                    print(f"[{project_id}] Thử zone {zone} cho {name}...")
                    ip = create_socks5_instance(
                        project_id=project_id,
                        zone=zone,
                        name=name,
                        port=SOCKS_PORT,
                        username=socks_user,
                        password=socks_pass,
                        fw_name=fw_name,
                        allowed_cidrs=allowed_cidrs,
                        delay_before=delay if zone == OSAKA_ZONES[0] else 0,
                    )
                    if ip is None and zone != OSAKA_ZONES[-1]:
                        print(f"[{project_id}] Zone {zone} thất bại, thử zone tiếp theo ({OSAKA_ZONES[OSAKA_ZONES.index(zone)+1]})...")
                if ip:
                    proxies.append(f"{ip}:{SOCKS_PORT}:{socks_user}:{socks_pass}")
                
                if i < 4:
                    next_delay = random.uniform(MIN_DELAY_BETWEEN_INSTANCES, MAX_DELAY_BETWEEN_INSTANCES)
                    print(f"[{project_id}] Đợi {next_delay:.1f}s trước instance tiếp theo...")
                    try:
                        time.sleep(next_delay)
                    except KeyboardInterrupt:
                        raise  

            print(f"\n[{project_id}] ==== DANH SÁCH PROXY SOCKS5 (IP:PORT:USER:PASS) ====")
            for p in proxies:
                print(p)

            all_proxies_by_project[project_id] = proxies

            filename = f"{project_id}_socks5_{int(time.time())}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n".join(proxies) + "\n")
            print(f"[{project_id}] ✔ Đã lưu vào file: {filename}")

        all_proxies_flat = []
        for proj_id, proxy_list in all_proxies_by_project.items():
            all_proxies_flat.extend(proxy_list)

        print("\n" + "=" * 60)
        print("==== TẤT CẢ 24 IP (PROXY) - IP:PORT:USER:PASS ====")
        print("=" * 60)
        for proxy in all_proxies_flat:
            print(proxy)
        print("=" * 60)
        print(f"Tổng: {len(all_proxies_flat)} proxy")
        print("=" * 60)

        all_24_file = f"all_24_proxies_{int(time.time())}.txt"
        with open(all_24_file, "w", encoding="utf-8") as f:
            f.write(f"# User: {socks_user} | Pass: {socks_pass}\n")
            f.write(f"# Tổng: {len(all_proxies_flat)} proxy\n\n")
            for proxy in all_proxies_flat:
                f.write(proxy + "\n")
        print(f"\n✔ Đã lưu tất cả {len(all_proxies_flat)} proxy vào: {all_24_file}")

        print("\n✅ Hoàn tất. Chờ 1–3 phút cho Dante start xong rồi hãy dùng SOCKS5.")

    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("⚠️ SCRIPT ĐÃ BỊ DỪNG BỞI USER (Ctrl+C)")
        print("="*60)
        
        if all_proxies_by_project:
            print(f"\n💾 Đang lưu progress đã tạo ({len(all_proxies_by_project)} project)...")
            
            timestamp = int(time.time())
            summary_file = f"interrupted_proxies_{timestamp}.txt"
            
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(f"# Proxies được tạo trước khi script bị dừng\n")
                f.write(f"# User: {socks_user} | Pass: {socks_pass}\n")
                f.write(f"# Timestamp: {timestamp}\n\n")
                
                for proj_id, proxy_list in all_proxies_by_project.items():
                    f.write(f"# Project: {proj_id}\n")
                    for proxy in proxy_list:
                        f.write(proxy + "\n")
                    f.write("\n")
            
            print(f"✅ Đã lưu {sum([len(p) for p in all_proxies_by_project.values()])} proxy vào: {summary_file}")
            
            all_interrupted = []
            for proj_id, proxy_list in all_proxies_by_project.items():
                all_interrupted.extend(proxy_list)
            print("\n==== TẤT CẢ IP ĐÃ TẠO (khi bị dừng) ====")
            for proxy in all_interrupted:
                print(proxy)
            print(f"Tổng: {len(all_interrupted)} proxy\n")
            
            for proj_id, proxy_list in all_proxies_by_project.items():
                if proxy_list:
                    filename = f"{proj_id}_socks5_interrupted_{timestamp}.txt"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write("\n".join(proxy_list) + "\n")
                    print(f"  - {proj_id}: {len(proxy_list)} proxy → {filename}")
        else:
            print("\n⚠️ Chưa có proxy nào được tạo.")
        
        print("\n📋 THÔNG TIN:")
        print(f"  - User: {socks_user}")
        print(f"  - Pass: {socks_pass}")
        print(f"  - Đã xử lý: {len(all_proxies_by_project)}/{len(projects)} project")
        print("\n💡 Bạn có thể chạy lại script để tiếp tục với project còn lại.")
        print("   (Các instance đã tạo sẽ không bị xóa, chỉ tạo thêm instance mới)")


if __name__ == "__main__":
    main()
