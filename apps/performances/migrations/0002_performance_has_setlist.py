from django.db import migrations, models


def backfill_has_setlist(apps, schema_editor):
    """기존 데이터 한 번만 정리한다.

    지금까지는 "초대가수" 같은 연예인 공연을 affiliation=None으로 넣는 게
    관례였다 (seed_performances.py 참고). has_setlist가 생기기 전 데이터에는
    이 관례를 그대로 적용해 백필하고, 이후로는 has_setlist를 직접 명시한다.
    """
    Performance = apps.get_model("performances", "Performance")
    Performance.objects.filter(affiliation__isnull=True).update(has_setlist=False)


class Migration(migrations.Migration):
    dependencies = [
        ("performances", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="performance",
            name="has_setlist",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(backfill_has_setlist, migrations.RunPython.noop),
    ]
