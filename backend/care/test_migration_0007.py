from datetime import time, timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

BEFORE = [("care", "0006_profile_consents")]
AFTER = [("care", "0007_subject_consent")]


class SubjectConsentMigrationTests(TransactionTestCase):
    """0007 only adds: existing data stays as it was, nothing is inferred, nothing is enabled."""

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        self.migrate(executor_leaf())

    def test_existing_profiles_wait_for_an_explicit_confirmation_and_keep_their_data(self):
        old = self.migrate(BEFORE)
        User = old.get_model("auth", "User")
        Profile, Membership = old.get_model("care", "Profile"), old.get_model("care", "Membership")
        Routine, Memory = old.get_model("care", "Routine"), old.get_model("care", "Memory")
        owner = User.objects.create(username="legacy-owner")
        carer = User.objects.create(username="legacy-carer")
        legacy = {"camera": True, "microphone": True, "meta_data": True, "version": "2026-10-29", "granted_by": "legacy-owner"}
        # One profile even says, in free text, who set it up: that must not decide anything.
        first = Profile.objects.create(owner=owner, display_name="Uno", support_notes="Relación de quien configura: Hija.",
                                       allergies="Penicilina", consents=legacy, communication={"addressing": "formal"})
        second = Profile.objects.create(owner=carer, display_name="Dos", consents=legacy)
        Membership.objects.create(profile=first, user=carer, relationship="Hija")
        Routine.objects.create(profile=first, category="medication", title="Pastilla", at=time(8), weekdays=[0, 1], created_by=owner)
        Memory.objects.create(profile=first, entity="llaves", location="mesa", observed_at=timezone.now(), recorded_by=owner,
                              expires_at=timezone.now() + timedelta(days=30))

        new = self.migrate(AFTER)
        Profile = new.get_model("care", "Profile")
        for profile in Profile.objects.all():
            self.assertEqual(profile.subject_status, "pending_confirmation")  # never inferred
            self.assertIsNone(profile.subject_user_id)
            self.assertEqual(profile.consent_epoch, 0)
            self.assertEqual(profile.consents, legacy)  # kept as history
        kept = Profile.objects.get(pk=first.pk)
        self.assertEqual((kept.display_name, kept.support_notes, kept.allergies, kept.communication),
                         ("Uno", "Relación de quien configura: Hija.", "Penicilina", {"addressing": "formal"}))
        self.assertEqual(new.get_model("care", "Membership").objects.count(), 1)
        self.assertEqual(new.get_model("care", "Routine").objects.count(), 1)
        self.assertEqual(new.get_model("care", "Memory").objects.count(), 1)
        self.assertEqual(new.get_model("care", "ConsentGrant").objects.count(), 0)  # no permission granted by migration
        self.assertEqual(new.get_model("care", "AccountPolicy").objects.count(), 0)  # nobody declared adult for them
        self.assertEqual(Profile.objects.get(pk=second.pk).owner_id, carer.pk)


def executor_leaf():
    executor = MigrationExecutor(connection)
    return executor.loader.graph.leaf_nodes()
