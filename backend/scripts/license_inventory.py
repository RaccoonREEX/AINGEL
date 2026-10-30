"""Generate docs/THIRD_PARTY_INVENTORY.md from the installed dependencies.

Sources: web/package-lock.json (+ each package.json), the Android release runtime classpath
(`gradlew :app:dependencies` output saved to .local/android_deps_raw.txt) with licences read from the
POM files in the local Gradle cache, and the Python packages of backend/requirements.lock.txt read
with importlib.metadata. A licence that cannot be read from metadata is reported, never guessed silently.

Usage (from the repository root):
    android\\gradlew.bat -p android :app:dependencies --configuration releaseRuntimeClasspath > .local\\android_deps_raw.txt
    .venv\\Scripts\\python.exe backend\\scripts\\license_inventory.py
"""

import glob
import importlib.metadata as metadata
import json
import os
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Projects whose licence is published by the project itself but whose POM is not in the local cache.
KNOWN_APACHE_GROUPS = ("androidx.", "com.google.auto.value", "com.google.guava", "com.squareup.", "org.jetbrains", "org.jspecify")


def npm_rows():
    lock = json.loads((ROOT / "web" / "package-lock.json").read_text(encoding="utf-8"))
    rows = []
    for path, meta in lock["packages"].items():
        if not path.startswith("node_modules/"):
            continue
        manifest = ROOT / "web" / path / "package.json"
        licence = meta.get("license")
        if not licence and manifest.exists():
            licence = json.loads(manifest.read_text(encoding="utf-8")).get("license")
        rows.append((path[len("node_modules/"):], meta.get("version", ""), licence or "NO ENCONTRADA",
                     "desarrollo (no se distribuye)" if meta.get("dev") else "se distribuye en la web"))
    return sorted(rows)


def pom_licence(cache, group, artifact, version, depth=0):
    poms = glob.glob(os.path.join(cache, group, artifact, version, "*", "*.pom"))
    if not poms:
        return None
    text = Path(poms[0]).read_text(encoding="utf-8", errors="replace")
    names = re.findall(r"<license>\s*<name>([^<]+)</name>", text)
    if names:
        return ", ".join(sorted({n.strip() for n in names}))
    parent = re.search(r"<parent>.*?<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>\s*<version>([^<]+)</version>", text, re.S)
    return pom_licence(cache, *parent.groups(), depth + 1) if parent and depth < 3 else None


def android_rows():
    raw_path = ROOT / ".local" / "android_deps_raw.txt"
    if not raw_path.exists():
        return []
    raw = raw_path.read_text(encoding="utf-8", errors="replace")
    deps = set()
    for match in re.finditer(r"--- ([\w.\-]+):([\w.\-]+)(?::([\w.\-]+))?(?: -> ([\w.\-]+))?", raw):
        group, artifact, version, resolved = match.groups()
        if resolved or version:
            deps.add((group, artifact, resolved or version))
    cache = os.path.expanduser("~/.gradle/caches/modules-2/files-2.1")
    rows = []
    for group, artifact, version in sorted(deps):
        licence = pom_licence(cache, group, artifact, version)
        if not licence:
            licence = ("Apache-2.0 (publicada por el proyecto; POM no presente en la caché local, verificar)"
                       if group.startswith(KNOWN_APACHE_GROUPS) else "NO ENCONTRADA")
        rows.append((f"{group}:{artifact}", version, licence, "se distribuye en el APK"))
    return rows


def python_rows():
    names = []
    for line in (ROOT / "backend" / "requirements.lock.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-")):
            names.append(re.split(r"[=<>\[ ;]", line)[0])
    rows = []
    for name in names:
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            rows.append((name, "?", "no instalado", "servidor"))
            continue
        meta = dist.metadata
        licence = meta.get("License-Expression") or ""
        if not licence or len(licence) > 60:
            classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
            licence = ", ".join(classifiers) or (meta.get("License") or "").splitlines()[0][:60]
        rows.append((name, dist.version, licence.strip() or "NO ENCONTRADA", "servidor (no se distribuye a clientes)"))
    return rows


def table(rows):
    lines = ["| Paquete | Versión | Licencia declarada | Uso |", "|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    return "\n".join(lines)


def main():
    npm, android, python = npm_rows(), android_rows(), python_rows()
    review = [r for r in npm + android + python if any(k in r[2] for k in ("NO ENCONTRADA", "verificar", "Proprietary", "SAM", "MPL"))]
    doc = f"""# Inventario de dependencias de terceros

Generado el {date.today().isoformat()} con `backend/scripts/license_inventory.py` a partir de los ficheros de
bloqueo y los metadatos instalados. Indica la licencia **declarada** por cada paquete; no es una auditoría
legal completa. Los avisos y textos de licencia que exigen las licencias deben acompañar a cada distribución
(ver `THIRD_PARTY_NOTICES.md`).

## Requieren revisión

{table(review) if review else "Ninguno."}

## Web (npm)

{table(npm)}

## Android (classpath de ejecución de release)

{table(android) if android else "Sin datos: generar antes `.local/android_deps_raw.txt` (ver cabecera del script)."}

## Servidor (Python)

{table(python)}
"""
    (ROOT / "docs" / "THIRD_PARTY_INVENTORY.md").write_text(doc, encoding="utf-8")
    print(f"npm {len(npm)} · android {len(android)} · python {len(python)} · revisar {len(review)}")


if __name__ == "__main__":
    main()
