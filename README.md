# Print Upload Server

Tiny authenticated file upload server that forwards a public port through SSH and prints uploaded files with `lp`.

## What it does

- Starts a local HTTP server on `127.0.0.1` using a random free port.
- Opens an SSH reverse tunnel to a public server.
- Accepts `POST` requests at the configured public URL.
- Requires a 6-digit TOTP code from an authenticator app.
- Provides:
  - public health check: `GET /health`
  - authenticated status: `GET /status?token=123456`
- Saves uploaded files into `./uploads`.
- Can print either:
  - a newly uploaded file, or
  - an already saved file from `./uploads`.
- Keeps only the newest uploaded files.
- Runs `lp` with structured request fields.
- Does not accept raw `lp_args`.

## Files

```text
main.py
README.md
.env.example
.env
totp_secret.txt
uploads/
run.sh
```

`.env`, `totp_secret.txt`, and `uploads/` are local runtime files and should not be committed.

## Install

```bash
sudo apt install cups-client openssh-client git python3 python3-pip
pip install qrcode
```

The `qrcode` package is optional, but recommended. Without it, the script prints the `otpauth://` URL instead of a terminal QR code.

## One-command install / update / run

After publishing this repo on GitHub, edit `run.sh` and set:

```bash
REPO_URL="https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME.git"
```

Then your colleague can run:

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME/main/run.sh | bash
```

This will:

- clone the repo into `~/.print-upload-server` if missing
- update it with `git pull` if already installed
- create `.env` from `.env.example` if missing
- install the `qrcode` Python package
- run `main.py`

A safer inspect-first version:

```bash
curl -fsSLO https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME/main/run.sh
less run.sh
bash run.sh
```

## Remote SSH server requirements

On the public server, SSH must allow remote forwarding.

Edit:

```bash
sudo nano /etc/ssh/sshd_config
```

Make sure these are enabled:

```text
AllowTcpForwarding yes
GatewayPorts yes
```

Restart SSH:

```bash
sudo systemctl restart ssh
```

## Configure

Copy the example env file:

```bash
cp .env.example .env
```

Edit it:

```bash
nano .env
```

Example:

```bash
SSH_HOST=undefined@62.84.185.97
PUBLIC_IP=62.84.185.97
REMOTE_PORT=9000
REMOTE_BIND=0.0.0.0

DEFAULT_PRINTER=copy4c
UPLOAD_DIR=./uploads
TOTP_SECRET_FILE=./totp_secret.txt

MAX_FILE_SIZE_MB=50
MAX_SAVED_FILES=20

TOTP_ISSUER=PrintUploadServer
TOTP_ACCOUNT=local-printer
```

### SSH_HOST

This is the SSH login used to open the reverse tunnel.

Example:

```bash
SSH_HOST=lea@62.84.185.97
```

### PUBLIC_IP

Used only for printed instructions and examples.

Example:

```bash
PUBLIC_IP=62.84.185.97
```

### REMOTE_PORT

Public port on the remote server.

Example:

```bash
REMOTE_PORT=9000
```

### DEFAULT_PRINTER

Printer used when the request does not include `printer`.

Example:

```bash
DEFAULT_PRINTER=copy4c
```

Printer names are not limited to a fixed list.

They may contain only:

```text
letters
numbers
.
_
-
```

Examples:

```text
copy4c
copy2a
lj4c
office_printer
printer-1
printer.local
```

## Run

```bash
python3 main.py
```

On first run, the script creates:

```text
totp_secret.txt
```

It then prints:

- TOTP secret
- current TOTP token for testing
- `otpauth://` URL
- terminal QR code
- local URL
- public URL
- health/status curl examples

Scan the QR code with an authenticator app such as:

- Google Authenticator
- Aegis
- Bitwarden
- 1Password
- Authy

## Reset TOTP

To generate a new TOTP secret:

```bash
rm totp_secret.txt
python3 main.py
```

Then scan the new QR code.

## Health check

The health check does not require authentication.

```bash
curl http://62.84.185.97:9000/health
```

Example response:

```json
{
  "ok": true,
  "ssh_tunnel_alive": true
}
```

## Status check

The status endpoint requires a current TOTP token.

```bash
curl "http://62.84.185.97:9000/status?token=123456"
```

Replace `123456` with the current code from your authenticator app.

The status response includes:

- public URL
- local port
- SSH tunnel status
- default printer
- supported request fields
- upload directory info
- saved file list
- max file size
- max saved files

## Upload and print

Replace `123456` with the current code from your authenticator app.

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "printer=copy4c" \
  -F "media=A4" \
  -F "copies=1" \
  -F "file=@document.pdf"
```

## Print an already uploaded file

This avoids uploading the same file again.

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "printer=copy4c" \
  -F "media=A4" \
  -F "copies=3" \
  -F "existing_file=document.pdf"
```

The file must already exist inside:

```text
./uploads
```

## A3 example

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "printer=copy4c" \
  -F "media=A3" \
  -F "input_slot=PF730B" \
  -F "file=@poster.pdf"
```

This generates something like:

```bash
lp -d copy4c -o media=A3 -o InputSlot=PF730B uploads/poster.pdf
```

## Duplex example

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "printer=copy4c" \
  -F "media=A4" \
  -F "sides=two-sided-long-edge" \
  -F "file=@document.pdf"
```

This generates something like:

```bash
lp -d copy4c -o media=A4 -o sides=two-sided-long-edge uploads/document.pdf
```

## Page range example

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "printer=copy4c" \
  -F "page_ranges=1-4" \
  -F "file=@document.pdf"
```

This generates something like:

```bash
lp -d copy4c -P 1-4 uploads/document.pdf
```

## Gloss / color-ish example

```bash
curl -X POST http://62.84.185.97:9000 \
  -F "token=123456" \
  -F "printer=copy4c" \
  -F "media=A3" \
  -F "input_slot=PF730B" \
  -F "color_reprod=Textphoto" \
  -F "eco=Level1" \
  -F "gloss=True" \
  -F "overprint=True" \
  -F "file=@poster.pdf"
```

This generates something like:

```bash
lp -d copy4c \
  -o media=A3 \
  -o InputSlot=PF730B \
  -o KMColorreprod1=Textphoto \
  -o KCEcoprint=Level1 \
  -o KCGlossmode=True \
  -o Overprint=True \
  uploads/poster.pdf
```

## Supported request fields

### Required

```text
token
```

Current 6-digit TOTP code.

### File input

Send one of these:

```text
file
existing_file
```

`file` uploads a new file.

`existing_file` prints a file already saved in `./uploads`.

### Print fields

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

### Metadata field

```text
text
```

`text` is optional. It is only printed in the server terminal log and is not passed to `lp`.

## Field behavior

### printer

Maps to:

```bash
lp -d <printer>
```

Default comes from `.env`:

```bash
DEFAULT_PRINTER=copy4c
```

Allowed characters:

```text
letters, numbers, dot, underscore, dash
```

Examples:

```text
copy4c
copy2a
lj4c
office_printer
printer-1
printer.local
```

### copies

Maps to:

```bash
lp -n <copies>
```

Allowed range:

```text
1-50
```

Example:

```bash
-F "copies=3"
```

### media

Maps to:

```bash
-o media=<value>
```

Examples:

```text
A4
A3
A5
Letter
10x15cm
```

### sides

Maps to:

```bash
-o sides=<value>
```

Examples:

```text
one-sided
two-sided-long-edge
two-sided-short-edge
```

### page_ranges

Maps to:

```bash
-P <value>
```

Examples:

```text
1
1-4
1,3,5-8
```

Only digits, commas, and dashes are accepted.

### input_slot

Maps to:

```bash
-o InputSlot=<value>
```

Examples:

```text
tray1
tray2
PF730A
PF730B
SomeTray_1
```

### color_reprod

Maps to:

```bash
-o KMColorreprod1=<value>
```

Examples:

```text
Textphoto
Vivid
Colortable
Publications
CustomMode
```

### eco

Maps to:

```bash
-o KCEcoprint=<value>
```

Examples:

```text
Off
Level1
Level2
Level3
Level5
```

### gloss

Maps to:

```bash
-o KCGlossmode=<value>
```

Allowed values:

```text
True
False
```

### overprint

Maps to:

```bash
-o Overprint=<value>
```

Allowed values:

```text
True
False
```

## Flexible option values

The script does not have fixed allow-lists for:

```text
media
sides
input_slot
color_reprod
eco
```

These values may be any value made from:

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

Spaces, slashes, quotes, semicolons, pipes, and shell-like characters are rejected.

This means these are accepted:

```text
A3
A4
PF730B
two-sided-short-edge
Textphoto
Level1
SomeTray_1
10x15cm
CustomMode
```

But these are rejected:

```text
bad value with spaces
../../file
"value"
value;rm
value|cmd
```

## Generated lp command

The script builds a command as a Python list and runs it with:

```python
subprocess.run(cmd, shell=False)
```

Example generated command:

```bash
lp -d copy4c -n 2 -o media=A4 -o sides=two-sided-long-edge uploads/document.pdf
```

It never uses `shell=True`.

It never accepts raw `lp_args`.

## Upload limit

Configured in `.env`:

```bash
MAX_FILE_SIZE_MB=50
```

Larger files are rejected.

## Saved file cleanup

Configured in `.env`:

```bash
MAX_SAVED_FILES=20
```

Only the newest files in `./uploads` are kept.

Older files are deleted automatically after requests.

## Security notes

This is safer than accepting raw `lp_args`, but it is still a public print endpoint.

Recommended:

- Put HTTPS in front of the public server.
- Keep `.env` private.
- Keep `totp_secret.txt` private.
- Limit public access by firewall if possible.
- Use a dedicated low-privilege user for running the script.
- Keep the structured option list small.
- Watch the terminal output for printed commands and errors.

## Common errors

### unauthorized

The TOTP token is missing, expired, or incorrect.

Generate a fresh code from your authenticator app.

### file too large

The uploaded file is over the configured limit.

### existing_file not found

The filename does not exist in `./uploads`.

### bad print option

One of the submitted fields has a value that failed validation.

Most commonly:

- unsupported characters
- invalid boolean
- invalid page range
- copies outside `1-50`

### lp command timed out

The `lp` command did not finish within 60 seconds.
