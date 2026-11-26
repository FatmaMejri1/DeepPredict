import csv
import gzip
import json
import random
from collections import defaultdict
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from infrastructure.models import Resource, ResourceType
from monitoring.models import Metric

PROCESSED = settings.BASE_DIR.parent / "ai-service" / "data" / "processed"
SOURCE = "backblaze_replay"


def parse_day(text):
    return datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=dt_timezone.utc)


def to_number(text):
    if text is None or text == "":
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return None if value != value else value      # NaN -> None


class Command(BaseCommand):
    help = ("Load a sample of real Backblaze drives (Resource + one Metric per day) so the "
            "app has data to show. Safe to run again: existing days are skipped.")

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(PROCESSED / "st12000nm0008_2026q1q2_clean.csv.gz"))
        parser.add_argument("--fail-dates", default=str(PROCESSED / "fail_dates.csv"))
        parser.add_argument("--failed", type=int, default=30, help="how many failed drives")
        parser.add_argument("--healthy", type=int, default=270, help="how many healthy drives")
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--from-date", default=None, help="YYYY-MM-DD, first day to load")
        parser.add_argument("--to-date", default=None,
                            help="YYYY-MM-DD, last day to load. Run again with a later date "
                                 "to replay the next days, like a live feed.")

    def handle(self, *args, **options):
        csv_path = Path(options["csv"])
        fail_path = Path(options["fail_dates"])
        for path in (csv_path, fail_path):
            if not path.exists():
                raise CommandError(f"{path} not found")
        cfg = json.loads((Path(settings.AI_ARTIFACTS_DIR) / "config.json").read_text(encoding="utf-8"))
        feature_cols = cfg["feature_cols"]
        from_date, to_date = options["from_date"], options["to_date"]

        failed_on = {}
        with open(fail_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                failed_on[row["serial_number"]] = row["fail_date"][:10]

        self.stdout.write("Pass 1: listing the drives ...")
        serials = set()
        with gzip.open(csv_path, "rt", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            i_serial = header.index("serial_number")
            for row in reader:
                serials.add(row[i_serial])

        rng = random.Random(options["seed"])
        failed_all = sorted(s for s in serials if s in failed_on)
        healthy_all = sorted(s for s in serials if s not in failed_on)
        chosen_failed = rng.sample(failed_all, min(options["failed"], len(failed_all)))
        chosen_healthy = rng.sample(healthy_all, min(options["healthy"], len(healthy_all)))
        chosen = set(chosen_failed) | set(chosen_healthy)
        self.stdout.write(f"Chosen: {len(chosen_failed)} failed + {len(chosen_healthy)} healthy drives")

        self.stdout.write("Pass 2: reading their history ...")
        wanted = ["date", "serial_number", "model", "capacity_bytes"] + feature_cols
        missing = [c for c in wanted if c not in header]
        if missing:
            raise CommandError(f"columns missing in the CSV: {missing}")
        idx = {c: header.index(c) for c in wanted}

        meta, rows_by_serial = {}, defaultdict(list)
        with gzip.open(csv_path, "rt", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                serial = row[idx["serial_number"]]
                if serial not in chosen:
                    continue
                meta.setdefault(serial, (row[idx["model"]], row[idx["capacity_bytes"]]))
                day = row[idx["date"]][:10]
                if (from_date and day < from_date) or (to_date and day > to_date):
                    continue
                rows_by_serial[serial].append(row)

        before = Metric.objects.filter(source=SOURCE).count()
        with transaction.atomic():
            resources = {}
            for serial in sorted(chosen):
                if serial not in meta:
                    continue
                drive_model, capacity = meta[serial]
                attrs = {"drive_model": drive_model, "capacity_bytes": to_number(capacity), "demo": True}
                if serial in failed_on:
                    attrs["demo_failed_on"] = failed_on[serial]   # demo only: the real outcome
                resource, _ = Resource.objects.get_or_create(
                    identifier=serial,
                    defaults={"name": f"Disk {serial}", "resource_type": ResourceType.DISK,
                              "attributes": attrs})
                resources[serial] = resource

            batch = []
            for serial, rows in rows_by_serial.items():
                resource = resources[serial]
                for row in rows:
                    batch.append(Metric(
                        resource=resource,
                        timestamp=parse_day(row[idx["date"]]),
                        values={c: to_number(row[idx[c]]) for c in feature_cols},
                        source=SOURCE))
                    if len(batch) >= 5000:
                        Metric.objects.bulk_create(batch, ignore_conflicts=True)
                        batch = []
            if batch:
                Metric.objects.bulk_create(batch, ignore_conflicts=True)

        after = Metric.objects.filter(source=SOURCE).count()
        self.stdout.write(self.style.SUCCESS(
            f"Done: {len(resources)} drives, {after - before} new metric rows ({after} in total)."))