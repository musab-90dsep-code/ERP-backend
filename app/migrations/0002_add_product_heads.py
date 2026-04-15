from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='product_heads',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
