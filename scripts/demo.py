#!/usr/bin/env python3
"""Local demo controller. Python standard library only; applications are Spring/Java."""

import argparse
from collections import Counter, deque
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".demo"
BASE = "http://127.0.0.1:8080"
COMPONENTS = ("1", "2", "3", "gateway")


def port(name):
    return 8080 if name == "gateway" else 8080 + int(name)


def jar(name):
    module = "gateway" if name == "gateway" else "demo-service"
    return ROOT / module / "target" / (module + ".jar")


def pidfile(name):
    return STATE / (name + ".pid")


def owned_pid(name):
    try:
        pid = int(pidfile(name).read_text().strip())
        if pid <= 1:
            return None
        result = subprocess.run(["ps", "-p", str(pid), "-o", "stat=", "-o", "args="],
                                capture_output=True, text=True, check=False)
        if "operation not permitted" in result.stderr.lower() or "permission denied" in result.stderr.lower():
            raise RuntimeError("Khong du quyen doc trang thai process bang ps; chay ngoai sandbox.")
        command = result.stdout.strip()
        if result.returncode == 0 and command and not command.startswith("Z"):
            if str(jar(name)) in command and "--server.port=" + str(port(name)) in command:
                return pid
    except (OSError, ValueError):
        pass
    return None


def fetch(url, request_id=None):
    headers = {"X-Request-Id": request_id or "demo-" + uuid.uuid4().hex[:8]}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=4) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def wait_until(description, predicate, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(0.25)
    raise RuntimeError("Timeout: " + description + ". Xem log trong .demo/")


def eligible():
    status, body = fetch(BASE + "/api/demo/instances")
    if status != 200:
        raise RuntimeError("Khong doc duoc danh sach instance: HTTP " + str(status))
    return {item["instanceId"] for item in body}


def wait_eligible(expected):
    wait_until("gateway nhan danh sach " + str(sorted(expected)), lambda: eligible() == expected)
    print("Gateway eligible:", ", ".join(sorted(expected)) or "(empty)", flush=True)


def build():
    subprocess.run(["mvn", "-B", "-ntp", "package"], cwd=ROOT, check=True)


def launch(name):
    if owned_pid(name):
        print(name + " da chay.", flush=True)
        return False
    if not jar(name).is_file():
        raise RuntimeError("Chua co JAR. Chay ./demo.sh build truoc.")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port(name))) == 0:
            raise RuntimeError("Cong " + str(port(name)) + " dang duoc process khac su dung.")
    STATE.mkdir(exist_ok=True)
    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin" / "java") if java_home else "java"
    command = [java, "-Xms32m", "-Xmx192m", "-XX:ActiveProcessorCount=2", "-jar", str(jar(name)),
               "--server.port=" + str(port(name))]
    if name != "gateway":
        command.append("--demo.instance-id=instance-" + name)
    with (STATE / (name + ".log")).open("a") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    pidfile(name).write_text(str(process.pid))
    print("Starting " + name + " on :" + str(port(name)) + " (PID " + str(process.pid) + ")", flush=True)
    return True


def ready(name):
    checked_legacy = False

    def healthy():
        nonlocal checked_legacy
        if not owned_pid(name):
            raise RuntimeError(name + " da thoat. Xem .demo/" + name + ".log")
        base = "http://127.0.0.1:" + str(port(name))
        try:
            status, body = fetch(base + "/api/actuator/health")
            if status == 200 and body.get("status") == "UP":
                return True
        except (OSError, ValueError, urllib.error.URLError):
            pass
        if not checked_legacy:
            checked_legacy = True
            try:
                status, body = fetch(base + "/actuator/health")
            except (OSError, ValueError, urllib.error.URLError):
                return False
            if status == 200 and body.get("status") == "UP":
                raise RuntimeError(name + " dang chay ban cu voi /actuator/health. "
                                   "Chay ./demo.sh down, ./demo.sh build, roi ./demo.sh up --terminals.")
        return False

    print("Dang cho " + name + " :" + str(port(name)) + "/api/actuator/health ...", flush=True)
    wait_until(name + " san sang", healthy)
    print(name + " san sang.", flush=True)


def stop(name, crash=False):
    pid = owned_pid(name)
    if pid:
        os.kill(pid, signal.SIGKILL if crash else signal.SIGTERM)
        wait_until(name + " dung", lambda: owned_pid(name) is None, timeout=15)
        print(("CRASHED " if crash else "Stopped ") + name, flush=True)
    else:
        print(name + " khong chay.", flush=True)
    pidfile(name).unlink(missing_ok=True)


def up(open_terminals=False):
    if any(not jar(name).is_file() for name in COMPONENTS):
        build()
    started = []
    try:
        for name in COMPONENTS:
            if launch(name):
                started.append(name)
        if open_terminals:
            terminals()
        for name in COMPONENTS:
            ready(name)
        wait_eligible({"instance-1", "instance-2", "instance-3"})
    except BaseException:
        for name in reversed(started):
            stop(name)
        raise
    print("Demo ready: " + BASE + "/api/hello", flush=True)
    print("Xem log: ./demo.sh logs --requests-only (hoac ./demo.sh logs 1)", flush=True)


def logs(target="all", lines=20, follow=True, requests_only=False):
    names = COMPONENTS if target == "all" else (target,)
    readers = {}

    def matches(line):
        return not requests_only or ("requestId=" in line and " handled by " in line)

    def show(name, line):
        if matches(line):
            label = "gateway" if name == "gateway" else "instance-" + name
            print(f"[{label} :{port(name)}] {line.rstrip()}", flush=True)

    def open_log(name, newly_created=False):
        path = STATE / (name + ".log")
        if not path.is_file():
            return
        reader = path.open(encoding="utf-8", errors="replace")
        readers[name] = reader
        if newly_created:
            return
        # Apply the filter before taking the last N lines, so startup/probe logs
        # do not hide recent business requests in --requests-only mode.
        history = (line for line in reader if matches(line))
        if lines:
            for line in deque(history, maxlen=lines):
                show(name, line)
        else:
            reader.seek(0, os.SEEK_END)

    try:
        for name in names:
            open_log(name)
        if not readers:
            print("Chua co log. Chay ./demo.sh up de tao log trong .demo/.", flush=True)
        if not follow:
            return
        print("Dang theo doi log. Ctrl+C de thoat xem log; service van tiep tuc chay.", flush=True)
        while True:
            for name in names:
                if name not in readers:
                    open_log(name, newly_created=True)
                    continue
                reader = readers[name]
                if os.fstat(reader.fileno()).st_size < reader.tell():
                    reader.seek(0)
                for _ in range(1000):
                    line = reader.readline()
                    if not line:
                        break
                    show(name, line)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nDa thoat xem log. Service van tiep tuc chay.", flush=True)
    finally:
        for reader in readers.values():
            reader.close()


def terminals(target="all", lines=20, requests_only=False, dry_run=False):
    names = COMPONENTS if target == "all" else (target,)
    commands = []
    for name in names:
        arguments = [str(ROOT / "demo.sh"), "logs", name, "--lines", str(lines)]
        if requests_only:
            arguments.append("--requests-only")
        commands.append("cd " + shlex.quote(str(ROOT)) + " && " + shlex.join(arguments))
    if dry_run:
        for command in commands:
            print(command, flush=True)
        return
    if sys.platform != "darwin":
        raise RuntimeError("Lenh terminals hien ho tro Terminal.app tren macOS. Dung ./demo.sh logs tren he dieu hanh khac.")
    print("Dang mo " + str(len(commands)) + " cua so Terminal.app xem log ...", flush=True)
    # Pass shell commands as argv, rather than interpolating them into AppleScript.
    script = '''on run argv
    tell application "Terminal"
        activate
        repeat with commandText in argv
            do script (contents of commandText)
        end repeat
    end tell
end run
'''
    result = subprocess.run(["osascript", "-", *commands], input=script,
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError("Khong mo duoc Terminal.app: " + result.stderr.strip())
    print("Da mo " + str(len(commands)) + " cua so Terminal xem log. Ctrl+C chi dung xem log.", flush=True)


def requests(count, interval=0.3, expected=None):
    seen = []
    errors = 0
    batch = uuid.uuid4().hex[:6]
    for index in range(count):
        request_id = batch + "-" + str(index + 1)
        try:
            status, body = fetch(BASE + "/api/hello", request_id)
            if status == 200:
                instance = body["instanceId"]
                seen.append(instance)
                print(f"{index + 1:02d}  HTTP {status}  -> {instance}  port={body['port']}"
                      f"  instanceCount={body['requestCount']}  requestId={body['requestId']}", flush=True)
            else:
                errors += 1
                print(f"{index + 1:02d}  HTTP {status}  -> request failed", flush=True)
        except (OSError, ValueError, urllib.error.URLError) as error:
            errors += 1
            print(f"{index + 1:02d}  ERROR {error}", flush=True)
        if interval and index + 1 < count:
            time.sleep(interval)
    print("Distribution:", json.dumps(dict(sorted(Counter(seen).items()))), "errors=" + str(errors), flush=True)
    if expected is not None:
        if errors or set(seen) != expected:
            raise RuntimeError("FAIL: request loi hoac sai danh sach instance")
        cycle = seen[:len(expected)]
        if len(set(cycle)) != len(expected) or any(value != cycle[i % len(cycle)] for i, value in enumerate(seen)):
            raise RuntimeError("FAIL: khong dung thu tu Round Robin: " + str(seen))
        if len(set(Counter(seen).values())) != 1:
            raise RuntimeError("FAIL: request khong chia deu")
        print("PASS: Round Robin order + equal distribution", flush=True)
    elif errors:
        raise RuntimeError(str(errors) + " request loi (co the dang trong khoang phat hien failure)")


def status():
    for name in COMPONENTS:
        try:
            code, body = fetch("http://127.0.0.1:" + str(port(name)) + "/api/actuator/health")
            health = str(code) + " " + body.get("status", "UNKNOWN")
        except (OSError, ValueError, urllib.error.URLError):
            health = "DOWN / unreachable"
        print(f"{name:8} :{port(name)} {health}", flush=True)
    try:
        print("Gateway eligible:", ", ".join(sorted(eligible())) or "(empty)", flush=True)
    except (OSError, ValueError, RuntimeError, urllib.error.URLError):
        print("Gateway eligible: unavailable", flush=True)


def verify():
    up()
    all_instances = {"instance-1", "instance-2", "instance-3"}
    try:
        print("\n=== Slide 8: 12 requests / 3 instances ===", flush=True)
        requests(12, 0.25, all_instances)
        print("\n=== Slide 9: kill instance-2, wait for health check ===", flush=True)
        stop("2", crash=True)
        wait_eligible({"instance-1", "instance-3"})
        requests(8, 0.25, {"instance-1", "instance-3"})
        print("\n=== Recovery: restart instance-2 ===", flush=True)
        launch("2")
        ready("2")
        wait_eligible(all_instances)
        requests(12, 0.25, all_instances)
        print("\n=== Edge case: all instances down ===", flush=True)
        for name in ("1", "2", "3"):
            stop(name, crash=True)
        wait_eligible(set())
        code, _ = fetch(BASE + "/api/hello")
        if code != 503:
            raise RuntimeError("FAIL: expected HTTP 503, got " + str(code))
        print("PASS: no healthy instance -> HTTP 503", flush=True)
    finally:
        for name in ("1", "2", "3"):
            launch(name)
        for name in ("1", "2", "3"):
            ready(name)
        wait_eligible(all_instances)
    requests(6, 0.25, all_instances)
    print("\nALL CHECKS PASSED. Demo van chay; ./demo.sh down de dung.", flush=True)


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("phai >= 1")
    return number


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("phai >= 0")
    return number


def main():
    parser = argparse.ArgumentParser(description="Spring Round Robin / Failure & Recovery demo")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "down", "status", "verify"):
        sub.add_parser(command)
    up_parser = sub.add_parser("up")
    up_parser.add_argument("--terminals", action="store_true", help="Mo 4 cua so Terminal xem log sau khi khoi dong (macOS)")
    for command in ("start", "stop", "crash"):
        sub.add_parser(command).add_argument("instance", choices=COMPONENTS)
    req = sub.add_parser("requests")
    req.add_argument("count", nargs="?", type=positive, default=12)
    req.add_argument("--interval", type=float, default=0.3)
    log_parser = sub.add_parser("logs", help="Xem log rieng tung instance hoac tat ca")
    log_parser.add_argument("instance", nargs="?", choices=(*COMPONENTS, "all"), default="all")
    log_parser.add_argument("--lines", type=nonnegative, default=20, help="So dong cuoi moi service (mac dinh 20)")
    log_parser.add_argument("--no-follow", action="store_true", help="In log hien tai roi thoat")
    log_parser.add_argument("--requests-only", action="store_true", help="Chi hien dong xu ly request cua backend")
    term_parser = sub.add_parser("terminals", help="Mo cua so Terminal.app xem log (macOS)")
    term_parser.add_argument("instance", nargs="?", choices=(*COMPONENTS, "all"), default="all")
    term_parser.add_argument("--lines", type=nonnegative, default=20)
    term_parser.add_argument("--requests-only", action="store_true")
    term_parser.add_argument("--dry-run", action="store_true", help="Chi in lenh se chay, khong mo cua so")
    args = parser.parse_args()
    if args.command == "build":
        build()
    elif args.command == "up":
        if args.terminals and sys.platform != "darwin":
            parser.error("--terminals chi ho tro macOS")
        up(open_terminals=args.terminals)
    elif args.command == "down":
        for name in reversed(COMPONENTS):
            stop(name)
    elif args.command == "start":
        launch(args.instance)
        ready(args.instance)
    elif args.command in ("stop", "crash"):
        stop(args.instance, crash=args.command == "crash")
    elif args.command == "status":
        status()
    elif args.command == "requests":
        if args.interval < 0:
            parser.error("--interval phai >= 0")
        requests(args.count, args.interval)
    elif args.command == "verify":
        verify()
    elif args.command == "logs":
        logs(args.instance, args.lines, not args.no_follow, args.requests_only)
    elif args.command == "terminals":
        terminals(args.instance, args.lines, args.requests_only, args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError, urllib.error.URLError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)
