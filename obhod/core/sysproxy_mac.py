"""Системный прокси macOS через networksetup: HTTP- и HTTPS-прокси на каждой включённой сетевой службе.

Обычно администратору хватает прав без пароля. Если networksetup отказал, те же команды повторяются одним
скриптом через osascript «with administrator privileges» — macOS один раз спросит пароль.
"""
import re
import shlex
import subprocess

BYPASS = ["localhost", "127.0.0.1", "*.local", "169.254/16", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
KINDS = ("webproxy", "securewebproxy")  # HTTP и HTTPS; mixed-inbound sing-box понимает оба


def _run(args):
    r = subprocess.run(["networksetup", *args], capture_output=True, text=True, timeout=20)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def services(run=_run):
    """Включённые сетевые службы: Wi-Fi, Ethernet… Строка со звёздочкой — служба выключена."""
    code, out = run(["-listallnetworkservices"])
    if code:
        raise OSError("networksetup не ответил: " + out.strip())
    return [line.strip() for line in out.splitlines()[1:] if line.strip() and not line.startswith("*")]


def _parse_proxy(text):
    get = lambda key: (re.search(rf"^{key}:\s*(.*)$", text, re.M) or [None, ""])[1].strip()
    port = get("Port")
    return {"enabled": get("Enabled").lower() == "yes", "server": get("Server"), "port": int(port) if port.isdigit() else 0}


def _parse_bypass(text):
    if "aren't any" in text or "There aren" in text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def read(run=_run):
    state = {}
    for svc in services(run):
        entry = {kind: _parse_proxy(run([f"-get{kind}", svc])[1]) for kind in KINDS}
        entry["bypass"] = _parse_bypass(run(["-getproxybypassdomains", svc])[1])
        state[svc] = entry
    return state


def commands(values):
    """Команды networksetup, которые приводят службы к values (формат как у read())."""
    cmds = []
    for svc, entry in values.items():
        for kind in KINDS:
            p = entry[kind]
            if p["server"]:
                cmds.append([f"-set{kind}", svc, p["server"], str(p["port"])])
            cmds.append([f"-set{kind}state", svc, "on" if p["enabled"] else "off"])
        cmds.append(["-setproxybypassdomains", svc, *(entry["bypass"] or ["Empty"])])
    return cmds


def write(values, run=_run, elevate=None):
    failed = [c for c in commands(values) if run(c)[0]]
    if failed:
        (elevate or _elevated)(failed)


def _elevated(cmds):
    script = " && ".join("networksetup " + " ".join(shlex.quote(a) for a in c) for c in cmds)
    escaped = script.replace("\\", "\\\\").replace('"', '\\"')  # строка внутри AppleScript в двойных кавычках
    applescript = f'do shell script "{escaped}" with administrator privileges'
    r = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise OSError("не удалось изменить прокси macOS: " + (r.stderr or r.stdout).strip())


def proxied(port, run=_run):
    entry = {kind: {"enabled": True, "server": "127.0.0.1", "port": port} for kind in KINDS}
    entry["bypass"] = list(BYPASS)
    return {svc: dict(entry) for svc in services(run)}
