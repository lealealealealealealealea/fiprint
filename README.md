# fiprint

Small authenticated print server for forwarding uploads to `lp`.

## Files

```text
main.py
run.sh
.env.example
.gitignore
README.md
```

Local files created at runtime:

```text
.env
totp_secret.txt
uploads/
```

Do not commit local runtime files.

## Install system requirements

```bash
sudo apt install git screen python3 openssh-client cups-client
```

Optional, for terminal QR setup:

```bash
pip install qrcode
```

If `qrcode` is not installed, the script prints the manual TOTP setup URL instead.

## One-command start or update

```bash
curl -fsSL https://raw.githubusercontent.com/lealealealealealealealea/fiprint/main/run.sh | bash
```

This clones or updates the repo in:

```text
~/.print-upload-server
```

Then it starts `main.py` in a background `screen` session.

Attach to the running session:

```bash
screen -r print-upload-server
```

Detach without stopping:

```text
Ctrl-a then d
```

## Restart

```bash
curl -fsSL https://raw.githubusercontent.com/lealealealealealealealea/fiprint/main/run.sh | bash -s -- restart
```

## Stop using run.sh

```bash
curl -fsSL https://raw.githubusercontent.com/lealealealealealealealea/fiprint/main/run.sh | bash -s -- stop
```

## Stop using HTTP request

This requires a valid TOTP token.

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "action=stop"
```

Replace `123456` with the current code from your authenticator app.

The request returns:

```text
stopping
```

Then the server shuts down.

## Configuration

Copy the example config:

```bash
cd ~/.print-upload-server
cp .env.example .env
nano .env
```

Example `.env`:

```bash
SSH_HOST=user@203.0.113.10
PUBLIC_IP=203.0.113.10
REMOTE_PORT=9000
REMOTE_BIND=0.0.0.0

DEFAULT_PRINTER=copy4c
UPLOAD_DIR=./uploads
TOTP_SECRET_FILE=./totp_secret.txt

MAX_FILE_SIZE_MB=50
MAX_SAVED_FILES=20

TOTP_ISSUER=fiprint
TOTP_ACCOUNT=local-printer
```

`203.0.113.10` is only an example address. Put the real server IP in your local `.env`.

## First run

On first run, the script creates:

```text
totp_secret.txt
```

It prints:

```text
secret
current token
otpauth URL
terminal QR code if qrcode is installed
local URL
public URL
```

Scan the QR code or use the `otpauth://` URL in your authenticator app.

## Health

No authentication required.

```bash
curl http://62.84.185.97:9000/health
```

Example:

```json
{
  "ok": true,
  "ssh_tunnel_alive": true
}
```

## Status

Requires a valid TOTP token.

```bash
curl "http://62.84.185.97:9000/status?token=123456"
```

## Upload and print

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "action=print" \
  -F "printer=copy4c" \
  -F "copies=1" \
  -F "media=A4" \
  -F "file=@document.pdf"
```

`action=print` is optional because it is the default action.

## Print an already uploaded file

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "existing_file=document.pdf" \
  -F "printer=copy4c" \
  -F "copies=3"
```

The file must exist in:

```text
./uploads
```

## Supported request fields

Authentication:

```text
token
```

Action:

```text
action=print
action=stop
```

File input, choose one:

```text
file
existing_file
```

Print options:

```text
printer
copies
media
sides
page_ranges
input_slot
color_reprod
eco
gloss
overprint
```

Optional log-only note:

```text
text
```

## Print option mapping

```text
printer       -> lp -d <printer>
copies        -> lp -n <copies>
media         -> -o media=<value>
sides         -> -o sides=<value>
page_ranges   -> -P <value>
input_slot    -> -o InputSlot=<value>
color_reprod  -> -o KMColorreprod1=<value>
eco           -> -o KCEcoprint=<value>
gloss         -> -o KCGlossmode=<value>
overprint     -> -o Overprint=<value>
```

## Value rules

Most option values may contain:

```text
letters
numbers
.
_
=
:
+
,
-
```

Spaces, quotes, slashes, pipes, and semicolons are rejected.

`copies` must be between `1` and `50`.

`page_ranges` may contain only digits, commas, and dashes.

`gloss` and `overprint` must be:

```text
True
False
```

## Examples

A3:

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "printer=copy4c" \
  -F "media=A3" \
  -F "input_slot=PF730B" \
  -F "file=@poster.pdf"
```

Duplex:

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "printer=copy4c" \
  -F "media=A4" \
  -F "sides=two-sided-long-edge" \
  -F "file=@document.pdf"
```

Page range:

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "printer=copy4c" \
  -F "page_ranges=1-4" \
  -F "file=@document.pdf"
```

## Remote SSH server

The public SSH server must allow remote forwarding.

In `/etc/ssh/sshd_config`:

```text
AllowTcpForwarding yes
GatewayPorts yes
```

Then restart SSH:

```bash
sudo systemctl restart ssh
```

## If port forwarding fails

Check whether the port is already used on the public server:

```bash
sudo ss -ltnp | grep ':9000'
```

If an old tunnel is stuck, kill that process or choose another `REMOTE_PORT` in `.env`.

## Security notes

This is a public print endpoint. Keep these private:

```text
.env
totp_secret.txt
SSH keys
uploaded files
logs with tokens
```

Prefer putting HTTPS and rate limiting in front of it if exposed publicly.
