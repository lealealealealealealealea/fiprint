#!/usr/bin/env python3

"""
Tiny authenticated print-upload server.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote, urlparse, parse_qs
import atexit
import base64
import cgi
import hashlib
import hmac
import json
import os
import secrets
import shlex
import shutil
import struct
import subprocess
import threading
import time


def load_dotenv(path=".env"):
    env_path = Path(path)

    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def env_str(name, default):
    return os.environ.get(name, default)


def env_int(name, default):
    raw = os.environ.get(name, "")

    if not raw:
        return default

    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer")


load_dotenv()


UPLOAD_DIR = Path(env_str("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

TOTP_SECRET_FILE = Path(env_str("TOTP_SECRET_FILE", "./totp_secret.txt"))

SSH_HOST = env_str("SSH_HOST", "undefined@62.84.185.97")
PUBLIC_IP = env_str("PUBLIC_IP", "62.84.185.97")
REMOTE_PORT = env_str("REMOTE_PORT", "9000")
REMOTE_BIND = env_str("REMOTE_BIND", "0.0.0.0")

MAX_FILE_SIZE = env_int("MAX_FILE_SIZE_MB", 50) * 1024 * 1024
MAX_SAVED_FILES = env_int("MAX_SAVED_FILES", 20)

TOTP_ISSUER = env_str("TOTP_ISSUER", "PrintUploadServer")
TOTP_ACCOUNT = env_str("TOTP_ACCOUNT", "local-printer")

DEFAULT_PRINTER = env_str("DEFAULT_PRINTER", "copy4c")

SAFE_VALUE_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "._=:+,-"
)

ALLOWED_BOOLEAN = {
    "True",
    "False",
}


def load_or_create_totp_secret():
    if TOTP_SECRET_FILE.exists():
        return TOTP_SECRET_FILE.read_text().strip()

    raw = secrets.token_bytes(20)
    secret = base64.b32encode(raw).decode().replace("=", "")

    TOTP_SECRET_FILE.write_text(secret + "\n")
    os.chmod(TOTP_SECRET_FILE, 0o600)

    return secret


TOTP_SECRET = load_or_create_totp_secret()


def hotp(secret, counter, digits=6):
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)

    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()

    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF

    return str(code % (10 ** digits)).zfill(digits)


def current_totp():
    return hotp(TOTP_SECRET, int(time.time()) // 30)


def verify_totp(token, window=1):
    token = str(token).strip()

    if not token.isdigit() or len(token) != 6:
        return False

    current_counter = int(time.time()) // 30

    for offset in range(-window, window + 1):
        expected = hotp(TOTP_SECRET, current_counter + offset)
        if hmac.compare_digest(token, expected):
            return True

    return False


def otpauth_url():
    label = quote(f"{TOTP_ISSUER}:{TOTP_ACCOUNT}", safe="")
    issuer = quote(TOTP_ISSUER, safe="")
    secret = quote(TOTP_SECRET, safe="")

    return (
        f"otpauth://totp/{label}"
        f"?secret={secret}"
        f"&issuer={issuer}"
        f"&algorithm=SHA1"
        f"&digits=6"
        f"&period=30"
    )


def print_totp_qr():
    url = otpauth_url()

    try:
        import qrcode
    except ImportError:
        print("QR code unavailable. Install with:")
        print("  pip install qrcode")
        print()
        print("Use this otpauth URL instead:")
        print(url)
        print()
        return

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    matrix = qr.get_matrix()

    print("Scan this QR code with your authenticator app:")
    print()

    BLACK = "\033[40m  \033[0m"
    WHITE = "\033[47m  \033[0m"

    for row in matrix:
        print("".join(BLACK if cell else WHITE for cell in row))

    print()
    print("Manual setup secret:")
    print(f"  {TOTP_SECRET}")
    print()
    print("otpauth URL:")
    print(f"  {url}")
    print()


def safe_upload_path(filename):
    name = os.path.basename(filename)

    if not name:
        raise ValueError("empty filename")

    path = UPLOAD_DIR / name

    upload_root = UPLOAD_DIR.resolve()
    resolved_path = path.resolve()

    if upload_root not in resolved_path.parents and resolved_path != upload_root:
        raise ValueError("invalid filename")

    return path


def cleanup_old_uploads():
    files = [p for p in UPLOAD_DIR.iterdir() if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    for old_file in files[MAX_SAVED_FILES:]:
        try:
            old_file.unlink()
            print("deleted old file:", old_file)
        except Exception as e:
            print("could not delete old file:", old_file, e)


def get_upload_stats():
    files = [p for p in UPLOAD_DIR.iterdir() if p.is_file()]
    total_bytes = sum(p.stat().st_size for p in files)
    newest = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:MAX_SAVED_FILES]

    return {
        "upload_dir": str(UPLOAD_DIR.resolve()),
        "file_count": len(files),
        "max_saved_files": MAX_SAVED_FILES,
        "total_bytes": total_bytes,
        "files": [
            {
                "name": p.name,
                "size": p.stat().st_size,
                "mtime": int(p.stat().st_mtime),
            }
            for p in newest
        ],
    }


def get_form_value(form, field, default=""):
    return form.getfirst(field, default).strip()


def validate_safe_value(field, value, max_len=120):
    if not value:
        raise ValueError(f"{field} is required")

    if len(value) > max_len:
        raise ValueError(f"{field} is too long")

    if not set(value) <= SAFE_VALUE_CHARS:
        raise ValueError(f"bad {field}: {value}")


def validate_bool(field, value):
    if value not in ALLOWED_BOOLEAN:
        raise ValueError(f"bad {field}: {value}")


def add_lp_option(cmd, name, value):
    validate_safe_value(name, value)
    cmd.extend(["-o", f"{name}={value}"])


def build_lp_command(form, path):
    printer = get_form_value(form, "printer", DEFAULT_PRINTER)
    validate_safe_value("printer", printer)

    cmd = ["lp", "-d", printer]

    copies_raw = get_form_value(form, "copies", "1")

    try:
        copies = int(copies_raw)
    except ValueError:
        raise ValueError("copies must be a number")

    if copies < 1 or copies > 50:
        raise ValueError("copies must be between 1 and 50")

    if copies != 1:
        cmd.extend(["-n", str(copies)])

    media = get_form_value(form, "media")
    if media:
        add_lp_option(cmd, "media", media)

    sides = get_form_value(form, "sides")
    if sides:
        add_lp_option(cmd, "sides", sides)

    page_ranges = get_form_value(form, "page_ranges")
    if page_ranges:
        validate_safe_value("page_ranges", page_ranges)

        if not set(page_ranges) <= set("0123456789,-"):
            raise ValueError("bad page_ranges")

        cmd.extend(["-P", page_ranges])

    input_slot = get_form_value(form, "input_slot")
    if input_slot:
        add_lp_option(cmd, "InputSlot", input_slot)

    color_reprod = get_form_value(form, "color_reprod")
    if color_reprod:
        add_lp_option(cmd, "KMColorreprod1", color_reprod)

    eco = get_form_value(form, "eco")
    if eco:
        add_lp_option(cmd, "KCEcoprint", eco)

    gloss = get_form_value(form, "gloss")
    if gloss:
        validate_bool("gloss", gloss)
        add_lp_option(cmd, "KCGlossmode", gloss)

    overprint = get_form_value(form, "overprint")
    if overprint:
        validate_bool("overprint", overprint)
        add_lp_option(cmd, "Overprint", overprint)

    cmd.append(str(path))
    return cmd


class Handler(BaseHTTPRequestHandler):
    def send_text(self, status, text):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(text.encode())

    def send_json(self, status, data):
        body = json.dumps(data, indent=2, sort_keys=True)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write((body + "\n").encode())

    def shutdown_after_response(self):
        def stop():
            time.sleep(0.2)
            server.shutdown()

        threading.Thread(target=stop, daemon=True).start()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            ssh_alive = ssh.poll() is None

            self.send_json(200 if ssh_alive else 503, {
                "ok": ssh_alive,
                "ssh_tunnel_alive": ssh_alive,
            })
            return

        if parsed.path == "/status":
            query = parse_qs(parsed.query)
            token = query.get("token", [""])[0]

            if not verify_totp(token):
                time.sleep(1)
                self.send_text(401, "unauthorized\n")
                return

            ssh_alive = ssh.poll() is None

            self.send_json(200 if ssh_alive else 503, {
                "ok": ssh_alive,
                "public_url": f"http://{PUBLIC_IP}:{REMOTE_PORT}",
                "local_port": local_port,
                "ssh_tunnel_alive": ssh_alive,
                "default_printer": DEFAULT_PRINTER,
                "value_rule": "letters, numbers, dot, underscore, equals, colon, plus, comma, dash",
                "max_file_size": MAX_FILE_SIZE,
                "max_saved_files": MAX_SAVED_FILES,
                "supported_fields": [
                    "token",
                    "action",
                    "file",
                    "existing_file",
                    "text",
                    "printer",
                    "copies",
                    "media",
                    "sides",
                    "page_ranges",
                    "input_slot",
                    "color_reprod",
                    "eco",
                    "gloss",
                    "overprint",
                ],
                "actions": [
                    "print",
                    "stop",
                ],
                "uploads": get_upload_stats(),
            })
            return

        self.send_text(404, "not found\n")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))

        if content_length > MAX_FILE_SIZE + 1024 * 1024:
            self.send_text(413, "file too large\n")
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type"),
                "CONTENT_LENGTH": self.headers.get("Content-Length"),
            },
        )

        if not verify_totp(form.getfirst("token", "")):
            time.sleep(1)
            self.send_text(401, "unauthorized\n")
            return

        action = get_form_value(form, "action", "print")

        if action == "stop":
            self.send_text(200, "stopping\n")
            self.shutdown_after_response()
            return

        if action != "print":
            self.send_text(400, "bad action\n")
            return

        text = get_form_value(form, "text")
        existing_file = get_form_value(form, "existing_file")

        path = None
        uploaded_new_file = False

        if "file" in form and getattr(form["file"], "filename", None):
            f = form["file"]

            try:
                path = safe_upload_path(f.filename)
            except ValueError as e:
                self.send_text(400, f"bad filename: {e}\n")
                return

            with path.open("wb") as out:
                shutil.copyfileobj(f.file, out)

            file_size = path.stat().st_size

            if file_size > MAX_FILE_SIZE:
                path.unlink(missing_ok=True)
                self.send_text(413, "file too large\n")
                return

            uploaded_new_file = True

        elif existing_file:
            try:
                path = safe_upload_path(existing_file)
            except ValueError as e:
                self.send_text(400, f"bad existing_file: {e}\n")
                return

            if not path.exists() or not path.is_file():
                self.send_text(404, "existing_file not found\n")
                return

            file_size = path.stat().st_size

        else:
            self.send_text(400, "send either file or existing_file\n")
            return

        try:
            cmd = build_lp_command(form, path)
        except ValueError as e:
            self.send_text(400, f"bad print option: {e}\n")
            return

        print("text:", text)
        print("file:", path)
        print("size:", file_size)
        print("uploaded_new_file:", uploaded_new_file)
        print("command:", shlex.join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            cleanup_old_uploads()

            response = (
                f"file: {path}\n"
                f"uploaded_new_file: {uploaded_new_file}\n"
                f"size: {file_size}\n"
                f"command: {shlex.join(cmd)}\n"
                f"exit_code: {result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}\n"
            )

            self.send_text(200 if result.returncode == 0 else 500, response)

        except subprocess.TimeoutExpired:
            cleanup_old_uploads()
            self.send_text(504, "lp command timed out\n")

        except Exception as e:
            cleanup_old_uploads()
            self.send_text(500, f"error running lp: {e}\n")


server = HTTPServer(("127.0.0.1", 0), Handler)
local_port = server.server_address[1]

ssh = subprocess.Popen([
    "ssh",
    "-N",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=2",
    "-R", f"{REMOTE_BIND}:{REMOTE_PORT}:127.0.0.1:{local_port}",
    SSH_HOST,
])

atexit.register(ssh.terminate)

print()
print("TOTP setup")
print("----------")
print(f"secret: {TOTP_SECRET}")
print(f"current token: {current_totp()}")
print()

print_totp_qr()

print("Server")
print("------")
print(f"local:  http://127.0.0.1:{local_port}")
print(f"public: http://{PUBLIC_IP}:{REMOTE_PORT}")
print()
print("Health:")
print(f"curl http://{PUBLIC_IP}:{REMOTE_PORT}/health")
print()
print("Status:")
print(f"curl 'http://{PUBLIC_IP}:{REMOTE_PORT}/status?token=123456'")
print()
print("Stop:")
print(f'curl -X POST http://{PUBLIC_IP}:{REMOTE_PORT} -F "token=123456" -F "action=stop"')
print()
print("Usage is documented in README.md")
print()

try:
    server.serve_forever()
finally:
    ssh.terminate()
