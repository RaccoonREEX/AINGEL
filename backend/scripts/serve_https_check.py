"""Isolated HTTPS Django for the Android test RealDjangoHttpsCsrfTest (never production).

Creates a throwaway self-signed certificate for 127.0.0.1/localhost and a throwaway SQLite database in a temporary
folder, migrates it, and serves this code with Daphne over TLS on 127.0.0.1:<port> (AI in mock mode: nothing reaches
Meta). Prints the instrumentation arguments for the phone, which reaches it through `adb reverse tcp:<port> tcp:<port>`.
Stop it with Ctrl+C; the folder is deleted.

  python scripts/serve_https_check.py [--port 8443]
"""

import argparse
import base64
import datetime
import ipaddress
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

BACKEND = Path(__file__).resolve().parents[1]


def certificate(folder):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "aingel-https-check")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    (folder / "key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (folder / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode("ascii")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix="aingel-https-check-"))
    try:
        der = certificate(folder)
        env = {**os.environ, "DJANGO_SETTINGS_MODULE": "https_check_settings", "AINGEL_HTTPS_CHECK_DB": str(folder / "check.sqlite3"),
               "PYTHONPATH": os.pathsep.join(filter(None, [str(BACKEND / "scripts"), os.environ.get("PYTHONPATH")])),
               "DJANGO_SECRET_KEY": secrets.token_urlsafe(48), "AINGEL_ENV": "local", "AINGEL_AI_MODE": "mock"}
        env.pop("MODEL_API_KEY", None)
        subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=BACKEND, env=env, check=True, capture_output=True)
        # Daphne's endpoint syntax needs forward slashes and escaped colons in Windows paths.
        def endpoint_path(path):
            return str(path).replace("\\", "/").replace(":", "\\:")
        endpoint = f"ssl:{args.port}:interface=127.0.0.1:privateKey={endpoint_path(folder / 'key.pem')}:certKey={endpoint_path(folder / 'cert.pem')}"
        print(f"https://127.0.0.1:{args.port}/ ready. On the phone: adb reverse tcp:{args.port} tcp:{args.port}", flush=True)
        print(f"-e aingelHttpsBackend https://127.0.0.1:{args.port}/ -e aingelHttpsCa {der}", flush=True)
        return subprocess.call([sys.executable, "-m", "daphne", "-e", endpoint, "config.asgi:application"], cwd=BACKEND, env=env)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
