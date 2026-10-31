"""Exercise the actual Dockerfile Daphne flags with a throwaway ASGI app."""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request


class DaphneLoggingTests(unittest.TestCase):
    def test_web_nginx_has_access_logging_disabled(self):
        config = (Path(__file__).resolve().parents[1] / "nginx.conf").read_text(encoding="utf-8")
        # A later location-level override could re-enable it; reject all other
        # access_log directives in this small single-server configuration.
        directives = re.findall(r"(?m)^\s*access_log\s+([^;]+);", config)
        self.assertEqual(directives, ["off"])

    def test_no_access_uri_but_operational_errors_remain(self):
        dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile.backend"
        command = next(line[4:] for line in dockerfile.read_text(encoding="utf-8").splitlines() if line.startswith("CMD "))
        args = json.loads(command)
        self.assertEqual(args[0], "daphne")
        self.assertNotIn("--access-log", args)
        self.assertEqual(args[args.index("--verbosity") + 1], "0")
        # Reserve an ephemeral local-only port, then let Daphne bind it.
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]
        args[args.index("-b") + 1] = "127.0.0.1"
        args[args.index("-p") + 1] = str(port)
        args[-1] = "privacy_probe:app"
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "privacy_probe.py").write_text(
                "import logging\n"
                "async def app(scope, receive, send):\n"
                "    logging.getLogger('aingel.probe').error('OPERATIONAL_ERROR_PROBE')\n"
                "    await send({'type': 'http.response.start', 'status': 200, 'headers': []})\n"
                "    await send({'type': 'http.response.body', 'body': b'ok'})\n",
                encoding="utf-8",
            )
            env = {**os.environ, "PYTHONPATH": tmp + os.pathsep + os.environ.get("PYTHONPATH", "")}
            process = subprocess.Popen([sys.executable, "-m", "daphne", *args[1:]], cwd=tmp, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                url = f"http://127.0.0.1:{port}/api/probe/?private=SYNTHETIC_SECRET_QUERY_MARKER"
                deadline = time.monotonic() + 15
                while True:
                    try:
                        with urllib.request.urlopen(url, timeout=1) as response:
                            self.assertEqual(response.read(), b"ok")
                        break
                    except (urllib.error.URLError, TimeoutError):
                        if process.poll() is not None or time.monotonic() >= deadline:
                            self.fail("Daphne did not become available")
                        time.sleep(0.1)
            finally:
                process.terminate()
                stdout, stderr = process.communicate(timeout=10)
            output = (stdout + stderr).decode("utf-8", errors="replace")
            self.assertNotIn("SYNTHETIC_SECRET_QUERY_MARKER", output)
            self.assertNotIn("/api/probe/", output)
            self.assertNotIn("127.0.0.1", output)
            self.assertIn("OPERATIONAL_ERROR_PROBE", output)


if __name__ == "__main__":
    unittest.main()
