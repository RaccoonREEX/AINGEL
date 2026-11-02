"""The web image's Nginx config must be readable by the unprivileged runtime user (UID 101), and the backend image
must not run as root. Static checks of the Dockerfiles; the CI workflow also builds the images and starts the web
container (.github/workflows/ci.yml)."""

from pathlib import Path
import re
import unittest

DEPLOY = Path(__file__).resolve().parents[1]


class WebImageTests(unittest.TestCase):
    def test_nginx_config_is_copied_readable_and_checked(self):
        dockerfile = (DEPLOY / "Dockerfile.web").read_text(encoding="utf-8")
        self.assertTrue(dockerfile.startswith("# syntax=docker/dockerfile:1"), "COPY --chmod needs BuildKit's frontend")
        self.assertIn("FROM nginxinc/nginx-unprivileged:", dockerfile)
        self.assertRegex(dockerfile, r"(?m)^COPY --chmod=644 deploy/nginx\.conf /etc/nginx/conf\.d/default\.conf$")
        # The fix that failed on the VPS: chmod as the unprivileged user on a root-owned file.
        self.assertNotRegex(dockerfile, r"(?m)^RUN .*chmod")
        # Nginx validates its config at build time, as the runtime user.
        self.assertRegex(dockerfile, r"(?m)^RUN nginx -t$")
        self.assertLess(dockerfile.index("COPY --chmod=644"), dockerfile.index("RUN nginx -t"))
        self.assertNotRegex(dockerfile, r"(?m)^USER\s+(0|root)\b")

    def test_nginx_listens_on_the_unprivileged_port(self):
        config = (DEPLOY / "nginx.conf").read_text(encoding="utf-8")
        self.assertRegex(config, r"listen\s+8080;")
        self.assertIn("EXPOSE 8080", (DEPLOY / "Dockerfile.web").read_text(encoding="utf-8"))

    def test_backend_runs_unprivileged_with_readable_code(self):
        dockerfile = (DEPLOY / "Dockerfile.backend").read_text(encoding="utf-8")
        self.assertRegex(dockerfile, r"(?m)^USER 10001:10001$")
        self.assertIn("chmod -R a+rX /app /web", dockerfile)
        self.assertLess(dockerfile.index("chmod -R a+rX"), dockerfile.index("USER 10001"))
        self.assertIn("/web/src/components/aingel/signFingerprints.json", dockerfile)


if __name__ == "__main__":
    unittest.main()
