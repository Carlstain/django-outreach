from django.db import migrations


def scrub_failure_details(apps, schema_editor):
    ProspectEvent = apps.get_model("outreach", "ProspectEvent")
    ProspectEvent.objects.filter(kind="mail_failed").update(detail="")


class Migration(migrations.Migration):

    dependencies = [
        ('outreach', '0008_failure_kind'),
    ]

    operations = [
        migrations.RunPython(scrub_failure_details, migrations.RunPython.noop),
    ]
