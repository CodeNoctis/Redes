import warnings
warnings.filterwarnings(action='ignore', module='.*paramiko.*')

from netmiko import ConnectHandler
import re
from prettytable import PrettyTable as PT
from datetime import datetime
from pathlib import Path

# ===== Helpers =====
def extract_ip(raw_data):
    pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
    ips = re.findall(pattern, raw_data)
    return "\n".join(ips)

def extract_interfaces(raw_data):
    pattern = r'^(?P<intf>\S+)\s+\S+\s+\S+\s+\S+\s+(?P<status>\S+)'
    matches = re.finditer(pattern, raw_data, re.MULTILINE)
    interfaces = [m.group("intf") for m in matches if m.group("status") == "up"]
    return "\n".join(interfaces)

def timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def latest_backup_file(device_dir: Path):
    files = sorted(device_dir.glob("*.txt"))
    return files[-1] if files else None

def sanitize(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "router"

def get_hostname_and_config(conn):
    # 1) Subir a modo privilegiado
    try:
        conn.enable()
    except Exception:
        pass
    if not conn.check_enable_mode():
        raise RuntimeError("No estás en modo privilegiado (#). Revisa 'secret' o el usuario (privilege 15).")

    # 2) Evitar paginación
    try:
        conn.send_command("terminal length 0")
    except Exception:
        pass

    # 3) Obtener la config (intenta variantes)
    full_run = ""
    for cmd in ("show running-config", "show run", "show startup-config", "show start"):
        out = conn.send_command(cmd, strip_prompt=False, strip_command=False)
        if out and "% Invalid input" not in out:
            full_run = out
            break
    if not full_run.strip():
        raise RuntimeError("No se pudo obtener la configuración (show run/start).")

    # 4) Hostname desde el texto o desde el prompt
    m = re.search(r"^hostname\s+(\S+)", full_run, re.MULTILINE)
    if m:
        hostname = m.group(1)
    else:
        prompt = conn.find_prompt() or "router"
        hostname = prompt.rstrip("#>").strip()

    return sanitize(hostname), full_run

def save_backup_if_changed(hostname: str, running: str):
    device_dir = Path("backups") / hostname
    device_dir.mkdir(parents=True, exist_ok=True)
    last_file = latest_backup_file(device_dir)
    if last_file:
        old = last_file.read_text(encoding="utf-8", errors="ignore")
        if old == running:
            print(f"= {hostname}: SIN cambios. Se conserva {last_file.name}")
            return
    ts = timestamp()
    new_file = device_dir / f"{hostname}__{ts}.txt"
    new_file.write_text(running, encoding="utf-8")
    print(f"✔ {hostname}: Backup guardado -> {new_file.name}")
    # borra anteriores para dejar solo el último
    for f in device_dir.glob("*.txt"):
        if f != new_file:
            try:
                f.unlink()
            except Exception:
                pass

# ===== R1 =====
print("*** Creating network Object...")
R1 = {
    'device_type': 'cisco_ios',
    'ip': '192.168.60.140',
    'username': 'admin',
    'password': 'cisco123',
    'secret':  'cisco123',     # para enable
    'fast_cli': True,
    'global_delay_factor': 0.5,
}
print("*** Conecting with the router R1...")
conn = ConnectHandler(**R1)
hostname, raw_data = get_hostname_and_config(conn)
IPs_in_use = extract_ip(raw_data)
interfaces_in_use = extract_interfaces(raw_data)
save_backup_if_changed(hostname, raw_data)
conn.disconnect()

table = PT()
separador = "-----------------"
table.field_names = ["Hostname", "IPs", "Associated Interface"]
table.add_row([hostname, IPs_in_use, interfaces_in_use])
table.add_row([separador, separador, separador])

# ===== R2 =====
print("*** Creating network Object...")
R2 = {
    'device_type': 'cisco_ios',
    'ip': '10.0.5.9',
    'username': 'admin',
    'password': 'cisco123',
    'secret':  'cisco123',
    'fast_cli': True,
    'global_delay_factor': 0.5,
}
print("*** Conecting with the router R2...")
conn = ConnectHandler(**R2)
hostname, raw_data = get_hostname_and_config(conn)
IPs_in_use = extract_ip(raw_data)
interfaces_in_use = extract_interfaces(raw_data)
save_backup_if_changed(hostname, raw_data)
conn.disconnect()
table.add_row([hostname, IPs_in_use, interfaces_in_use])
table.add_row([separador, separador, separador])

# ===== R3 =====
print("*** Creating network Object...")
R3 = {
    'device_type': 'cisco_ios',
    'ip': '10.0.5.10',
    'username': 'admin',
    'password': 'cisco123',
    'secret':  'cisco123',
    'fast_cli': True,
    'global_delay_factor': 0.5,
}
print("*** Conecting with the router R3...")
conn = ConnectHandler(**R3)
hostname, raw_data = get_hostname_and_config(conn)
IPs_in_use = extract_ip(raw_data)
interfaces_in_use = extract_interfaces(raw_data)
save_backup_if_changed(hostname, raw_data)
conn.disconnect()
table.add_row([hostname, IPs_in_use, interfaces_in_use])

# ===== Tabla final =====
print(table)


import subprocess, time
msg = f"Backups {datetime.now():%Y%m%d-%H%M%S}"
subprocess.run(["git","add","backups"], check=False)
subprocess.run(["git","commit","-m", msg], check=False)
subprocess.run(["git","push"], check=False)
