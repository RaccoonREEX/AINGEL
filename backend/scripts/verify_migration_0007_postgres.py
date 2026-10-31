"""Checks migration care.0007 on an ISOLATED PostgreSQL, never production.

What it does, with synthetic data only:
 1. Production code (0006) creates the schema and a representative data set: accounts, profiles with legacy consents,
    family memberships, invitations, routines and checks, messages, memories, audit events, MFA and a family face.
 2. Backup with pg_dump.
 3. This branch migrates to 0007: every pre-existing row and column must be unchanged, every profile must be
    "pending_confirmation", and no consent, adult declaration or invitation may be created (nothing implicit).
 4. Idempotency: a second migrate applies nothing and changes nothing.
 5. Rollback to 0006 and forward again: same data.
 6. Restore the backup into a new database: same data as before the migration; then migrate it too.
 7. Compatibility: production code keeps reading and writing on the migrated database (rolling deploy or rollback of
    the code without reversing the migration); its new rows get the database defaults.

Usage (from backend/, with psycopg available and pg_dump/pg_restore of the same major version as the server):
  git archive <production commit> backend | tar -x -C <dir>
  AINGEL_CHECK_DB_HOST=127.0.0.1 AINGEL_CHECK_DB_PORT=55432 AINGEL_CHECK_DB_USER=aingel_check \
    python scripts/verify_migration_0007_postgres.py --production-backend <dir>/backend --pg-bin <postgres bin dir>
Only databases named aingel_check_* are created or dropped. A host other than loopback needs --isolated-host, which
states that it is a throwaway server.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg
from psycopg import sql

BACKEND = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
MIGRATED_DB, RESTORED_DB = "aingel_check_migration", "aingel_check_restore"
# Tables the migration itself legitimately writes to.
BOOKKEEPING = {"django_migrations", "django_content_type", "auth_permission"}
NEW_TABLES = ("care_accountpolicy", "care_consentgrant", "care_subjectinvite")

SEED = r'''
from datetime import date, time, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from care.models import AuditEvent, FamilyFace, Invitation, Membership, Memory, Message, MFADevice, Profile, Routine, RoutineCheck

now = timezone.now()
users = [get_user_model().objects.create_user(username=f"check-person-{i}", password="check-only-not-a-secret") for i in range(8)]
categories = ["sleep", "wake", "medicine", "bathroom", "meal", "water", "appointment", "other"]
legacy = [{"camera": True, "microphone": True, "meta_data": True}, {"camera": True, "microphone": False, "meta_data": False},
          {"camera": False, "microphone": True, "meta_data": True, "version": "2026-10-29", "granted_by": "check-person-2"}, {}, {"meta_data": True}]
for i in range(5):
    profile = Profile.objects.create(
        owner=users[i], display_name=f"Persona ficticia {i}", locale=["es-EC", "en-US"][i % 2],
        allergies=["", "alergia ficticia"][i % 2],
        support_notes=["Apoyos indicados: visual. Esta cuenta es mía.", "Apoyos indicados: cognitivo", "Notas ficticias", "", "Mi perfil propio"][i],
        emergency_contact=["", "Contacto ficticio 000"][i % 2], preferences={"large_text": i % 2 == 0, "voice_output": True},
        communication=[{}, {"pace": "slow", "addressing": "formal"}, {"preferred_name": "Ficticio"}, {}, {"detail": "detailed"}][i],
        face_recognition_enabled=i == 0, consents=legacy[i])
    for j, helper in enumerate(users[5:7]):
        member = Membership.objects.create(profile=profile, user=helper, relationship=["hija", "hijo"][j],
                                           can_configure=j == 0, can_view_memories=i % 2 == 0, face_consent_epoch=j)
        if i == 0 and j == 0:
            FamilyFace.objects.create(member=member, display_name="Familiar ficticio", embedding_encrypted="check-not-a-real-embedding",
                                      expires_at=now + timedelta(days=90))
    Invitation.objects.create(profile=profile, target=users[7], token_hash=f"{i:064d}", relationship="amiga", expires_at=now + timedelta(days=2))
    for k in range(3):
        routine = Routine.objects.create(profile=profile, category=categories[(i + k) % 8], title=f"Rutina ficticia {i}-{k}",
                                         at=time(7 + k, 15), weekdays=[1, 3, 5], instructions="Con agua" if k == 1 else "",
                                         active=k != 2, created_by=users[i])
        RoutineCheck.objects.create(routine=routine, date=date(2026, 10, 1 + k), actor=users[5])
    Message.objects.create(profile=profile, author=users[5], body=f"Mensaje ficticio para {i}", locale="es-EC")
    Memory.objects.create(profile=profile, entity="llaves", location="mesa de la entrada", observed_at=now - timedelta(hours=i),
                          recorded_by=users[i], note="nota ficticia", expires_at=now + timedelta(days=30))
    AuditEvent.objects.create(profile=profile, actor=users[i], action="check.seed", resource_id=str(i))
MFADevice.objects.create(user=users[0], secret_encrypted="check-not-a-secret", enabled=True, last_counter=5, recovery_hashes=["x"], epoch=2)
print("seeded", Profile.objects.count())
'''

# Production code on the migrated database: it must keep working (no column it does not know may block it).
PRODUCTION_WRITES = r'''
from datetime import time, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from care.models import Memory, Profile, Routine
user = get_user_model().objects.create_user(username="check-after-migration", password="check-only-not-a-secret")
profile = Profile.objects.create(owner=user, display_name="Creado por la versión anterior", consents={"camera": True})
Routine.objects.create(profile=profile, category="water", title="Agua", at=time(10), created_by=user)
Memory.objects.create(profile=profile, entity="gafas", location="sofá", observed_at=timezone.now(), recorded_by=user,
                      expires_at=timezone.now() + timedelta(days=1))
print("profiles", Profile.objects.count(), "read", len([p.display_name for p in Profile.objects.all()]))
'''

BRANCH_READS = r'''
from care.models import Profile
p = Profile.objects.get(display_name="Creado por la versión anterior")
print(p.subject_status, p.consent_epoch, p.subject_user_id)
'''


def connect(database):
    return psycopg.connect(dbname=database, host=os.environ.get("AINGEL_CHECK_DB_HOST", "127.0.0.1"),
                           port=os.environ.get("AINGEL_CHECK_DB_PORT", "55432"), user=os.environ.get("AINGEL_CHECK_DB_USER", "aingel_check"),
                           password=os.environ.get("AINGEL_CHECK_DB_PASSWORD", ""), autocommit=True)


def recreate(name):
    assert name.startswith("aingel_check_")
    with connect("postgres") as db:
        db.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
        db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def drop(name):
    assert name.startswith("aingel_check_")
    with connect("postgres") as db:
        db.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


def manage(code, database, *args):
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "postgres_check_settings", "AINGEL_CHECK_DB": database,
           "PYTHONPATH": os.pathsep.join(filter(None, [str(SCRIPTS), os.environ.get("PYTHONPATH")])),
           "DJANGO_SECRET_KEY": "check-only-" + "x" * 60, "AINGEL_ENV": "local", "AINGEL_AI_MODE": "mock"}
    result = subprocess.run([sys.executable, "manage.py", *args], cwd=code, env=env, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(f"manage.py {' '.join(args[:2])} failed in {code}:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def columns(database):
    with connect(database) as db:
        rows = db.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public' "
                          "ORDER BY table_name, ordinal_position").fetchall()
    found = {}
    for table, column in rows:
        found.setdefault(table, []).append(column)
    return found


def snapshot(database, layout):
    """Row count and a hash of every row, per table, over the columns that existed before the migration."""
    result = {}
    with connect(database) as db:
        for table, names in layout.items():
            if table in BOOKKEEPING:
                continue
            query = sql.SQL("SELECT count(*), md5(coalesce(string_agg(r::text, '|' ORDER BY r::text), '')) FROM (SELECT {} FROM {}) r").format(
                sql.SQL(", ").join(map(sql.Identifier, names)), sql.Identifier(table))
            result[table] = list(db.execute(query).fetchone())
    return result


def new_state(database):
    with connect(database) as db:
        profiles = db.execute("SELECT count(*), count(*) FILTER (WHERE subject_status <> 'pending_confirmation' OR consent_epoch <> 0 "
                              "OR subject_user_id IS NOT NULL) FROM care_profile").fetchone()
        created = {t: db.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(t))).fetchone()[0] for t in NEW_TABLES}
        defaults = db.execute("SELECT column_name, column_default FROM information_schema.columns WHERE table_name = 'care_profile' "
                              "AND column_name IN ('subject_status', 'consent_epoch') ORDER BY column_name").fetchall()
    return {"profiles": profiles[0], "profiles_not_pending": profiles[1], "rows_in_new_tables": created,
            "database_defaults": {name: default for name, default in defaults}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-backend", type=Path, required=True)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--isolated-host", action="store_true")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    if os.environ.get("AINGEL_ENV") == "production":
        raise SystemExit("Refusing to run with AINGEL_ENV=production")
    host = os.environ.get("AINGEL_CHECK_DB_HOST", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost", "::1") and not args.isolated_host:
        raise SystemExit("Non-loopback host: pass --isolated-host only for a throwaway server")
    with connect("postgres") as db:
        server = db.execute("SHOW server_version").fetchone()[0]
    report = {"server_version": server, "production_code": str(args.production_backend), "checks": {}}
    checks = report["checks"]

    recreate(MIGRATED_DB)
    manage(args.production_backend, MIGRATED_DB, "migrate", "--noinput")
    manage(args.production_backend, MIGRATED_DB, "shell", "-c", SEED)
    layout = columns(MIGRATED_DB)
    before = snapshot(MIGRATED_DB, layout)
    report["rows_before"] = {table: count for table, (count, _) in before.items() if count}

    backup = Path(tempfile.mkdtemp()) / "before-0007.dump"
    env = {**os.environ, "PGPASSWORD": os.environ.get("AINGEL_CHECK_DB_PASSWORD", "")}
    common = ["-h", host, "-p", os.environ.get("AINGEL_CHECK_DB_PORT", "55432"), "-U", os.environ.get("AINGEL_CHECK_DB_USER", "aingel_check")]
    subprocess.run([str(args.pg_bin / "pg_dump"), *common, "-Fc", "-f", str(backup), MIGRATED_DB], check=True, env=env)

    manage(BACKEND, MIGRATED_DB, "migrate", "--noinput")
    checks["data_unchanged_after_0007"] = snapshot(MIGRATED_DB, layout) == before
    state = new_state(MIGRATED_DB)
    report["after_0007"] = state
    checks["all_profiles_pending_confirmation"] = state["profiles"] == before["care_profile"][0] and state["profiles_not_pending"] == 0
    checks["no_implicit_authorizations"] = all(count == 0 for count in state["rows_in_new_tables"].values())

    second = manage(BACKEND, MIGRATED_DB, "migrate", "--noinput")
    manage(BACKEND, MIGRATED_DB, "migrate", "--check")
    checks["second_migrate_applies_nothing"] = "No migrations to apply" in second and snapshot(MIGRATED_DB, layout) == before

    manage(BACKEND, MIGRATED_DB, "migrate", "care", "0006", "--noinput")
    checks["rollback_to_0006_keeps_data"] = snapshot(MIGRATED_DB, layout) == before
    manage(BACKEND, MIGRATED_DB, "migrate", "--noinput")
    checks["forward_again_keeps_data"] = snapshot(MIGRATED_DB, layout) == before and new_state(MIGRATED_DB)["profiles_not_pending"] == 0

    recreate(RESTORED_DB)
    subprocess.run([str(args.pg_bin / "pg_restore"), *common, "--no-owner", "-d", RESTORED_DB, str(backup)], check=True, env=env)
    checks["backup_restores_identical_data"] = snapshot(RESTORED_DB, layout) == before
    manage(BACKEND, RESTORED_DB, "migrate", "--noinput")
    checks["restored_backup_migrates_identically"] = snapshot(RESTORED_DB, layout) == before and new_state(RESTORED_DB)["profiles_not_pending"] == 0

    try:
        # The last line: the shell may print a banner first.
        report["production_code_on_0007"] = manage(args.production_backend, MIGRATED_DB, "shell", "-c", PRODUCTION_WRITES).strip().splitlines()[-1]
        report["branch_reads_that_row"] = manage(BACKEND, MIGRATED_DB, "shell", "-c", BRANCH_READS).strip().splitlines()[-1]
        checks["production_code_works_on_0007"] = report["branch_reads_that_row"] == "pending_confirmation 0 None"
    except SystemExit as error:
        report["production_code_on_0007"] = str(error)[-600:]
        checks["production_code_works_on_0007"] = False

    backup.unlink()
    if not args.keep:
        drop(MIGRATED_DB)
        drop(RESTORED_DB)
    report["passed"] = all(checks.values())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
