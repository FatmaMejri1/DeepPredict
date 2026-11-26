from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Disabled: Backblaze data is reserved for model training and evaluation."

    def handle(self, *args, **options):
        raise CommandError(
            "Backblaze training data must not be loaded into operational monitoring records. "
            "Upload telemetry collected from monitored drives instead."
        )
