# Units Meta bills outside tokens: SAM images, Voice seconds of audio and web searches. Adds columns only.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assistance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(model_name="metausage", name="images", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="metausage", name="audio_seconds", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="metausage", name="web_searches", field=models.PositiveIntegerField(default=0)),
    ]
