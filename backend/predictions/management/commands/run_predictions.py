from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Max

from infrastructure.models import Resource, ResourceType
from monitoring.models import Metric

from predictions.services import InferenceError, NotEnoughHistory, predict_resource


def parse_date(text, option):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise CommandError(f"{option} must look like 2026-06-15")


class Command(BaseCommand):
    help = "Score the drives with the AI service and save the predictions."

    def add_arguments(self, parser):
        parser.add_argument("--as-of", default=None,
                            help="YYYY-MM-DD: score as if this were today (replay the past)")
        parser.add_argument("--since", default=None,
                            help="YYYY-MM-DD: also score on every Nth day from this date "
                                 "up to --as-of (or the last day of data). Builds the history "
                                 "shown in the risk chart.")
        parser.add_argument("--every", type=int, default=7, help="days between two scorings (with --since)")
        parser.add_argument("--resource", default=None, help="only this drive (its serial number)")
        parser.add_argument("--limit", type=int, default=None, help="only the first N drives")

    def handle(self, *args, **options):
        as_of = parse_date(options["as_of"], "--as-of") if options["as_of"] else None

        dates = [as_of]                       # [None] means: the latest readings
        if options["since"]:
            start = parse_date(options["since"], "--since")
            latest = Metric.objects.aggregate(m=Max("timestamp"))["m"]
            if latest is None:
                raise CommandError("No readings in the database. Run load_demo_drives first.")
            end = as_of or latest.date()
            step = max(options["every"], 1)
            dates, day = [], start
            while day < end:
                dates.append(day)
                day += timedelta(days=step)
            dates.append(end)                 # always finish on the last day

        resources = Resource.objects.filter(resource_type=ResourceType.DISK, is_active=True).order_by("identifier")
        if options["resource"]:
            resources = resources.filter(identifier=options["resource"])
        if options["limit"]:
            resources = resources[: options["limit"]]
        resources = list(resources)

        done = skipped = too_early = errors = 0
        for day in dates:                     # oldest first, so the final status is the latest
            for resource in resources:
                try:
                    result = predict_resource(resource, as_of=day)
                except NotEnoughHistory:
                    too_early += 1
                    continue
                except InferenceError as exc:
                    errors += 1
                    self.stderr.write(f"{resource.identifier}: {exc}")
                    if done == 0 and errors >= 3:
                        raise CommandError("Stopping: the AI service does not answer. Is it running?")
                    continue
                if result is None:
                    skipped += 1
                else:
                    done += 1

        self.stdout.write(self.style.SUCCESS(
            f"Scored on {len(dates)} date(s) | predicted: {done} | already up to date: {skipped} | "
            f"not enough history: {too_early} | errors: {errors}"))
        counts = Resource.objects.filter(resource_type=ResourceType.DISK).values("status").annotate(n=Count("id"))
        self.stdout.write("Status of the drives: " + ", ".join(f"{c['status']}={c['n']}" for c in counts))
