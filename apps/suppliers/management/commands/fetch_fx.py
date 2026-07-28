"""
Fetch the USD→CAD rate used to convert supplier costs into CAD retail prices.

Runs daily from a systemd timer. Two independent sources are tried, because
this rate feeds automatic retail pricing and a single upstream going quiet is
the failure mode that matters: prices would keep recalculating from a number
nobody had checked.

Nothing is written when both sources fail. The previous rate simply stays, and
ages — `reprice` refuses to run on a rate older than FxRate.STALE_AFTER_HOURS,
so a broken feed stops repricing instead of quietly corrupting it.

    python manage.py fetch_fx
    python manage.py fetch_fx --base USD --quote CAD
    python manage.py fetch_fx --set 1.37      # manual override, e.g. feed down
"""
import json
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from apps.suppliers.models import FxRate

TIMEOUT = 15

# Frankfurter publishes European Central Bank reference rates; open.er-api is an
# unrelated provider. Two different operators, not two endpoints of one — a
# shared outage should not take both out.
SOURCES = [
    ("frankfurter/ECB", "https://api.frankfurter.app/latest?from={base}&to={quote}",
     lambda d, q: d["rates"][q]),
    ("open.er-api", "https://open.er-api.com/v6/latest/{base}",
     lambda d, q: d["rates"][q]),
]


def _fetch(url, pick, quote):
    req = urllib.request.Request(url, headers={"User-Agent": "peptidenet/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.loads(r.read().decode("utf-8"))
    return Decimal(str(pick(data, quote)))


class Command(BaseCommand):
    help = "Fetch and store the USD→CAD exchange rate."

    def add_arguments(self, parser):
        parser.add_argument("--base", default="USD")
        parser.add_argument("--quote", default="CAD")
        parser.add_argument("--set", default="",
                            help="Store this rate by hand instead of fetching.")

    def handle(self, *args, **o):
        base, quote = o["base"].upper(), o["quote"].upper()

        if o["set"]:
            try:
                rate = Decimal(o["set"])
            except InvalidOperation:
                raise CommandError(f"--set {o['set']!r} is not a number.")
            if not (Decimal("0.1") < rate < Decimal("10")):
                raise CommandError(
                    f"--set {rate} is outside the plausible range for a major "
                    f"currency pair. Refusing: this rate drives retail prices.")
            FxRate.objects.create(base=base, quote=quote, rate=rate, source="manual")
            self.stdout.write(self.style.SUCCESS(f"Set {base}/{quote} = {rate} (manual)."))
            return

        errors = []
        for name, tmpl, pick in SOURCES:
            url = tmpl.format(base=base, quote=quote)
            try:
                rate = _fetch(url, pick, quote)
            except (urllib.error.URLError, OSError, KeyError, ValueError,
                    InvalidOperation, TimeoutError) as e:
                errors.append(f"{name}: {type(e).__name__} {e}")
                continue

            # A sanity band. A major pair does not leave this range, so a value
            # outside it means the response shape changed, not that the dollar
            # moved — and acting on it would reprice the whole catalogue.
            if not (Decimal("0.5") < rate < Decimal("5")):
                errors.append(f"{name}: implausible rate {rate}")
                continue

            previous = FxRate.latest(base, quote)
            FxRate.objects.create(base=base, quote=quote, rate=rate, source=name)
            msg = f"{base}/{quote} = {rate} (via {name})"
            if previous:
                move = (rate - previous.rate) / previous.rate * 100
                msg += f"  [previous {previous.rate}, {move:+.2f}%]"
                if abs(move) > 5:
                    self.stdout.write(self.style.WARNING(
                        f"Rate moved {move:+.2f}% since the last fetch — worth a look "
                        f"before the next reprice."))
            self.stdout.write(self.style.SUCCESS(msg))
            return

        previous = FxRate.latest(base, quote)
        detail = "; ".join(errors)
        if previous:
            raise CommandError(
                f"Could not fetch {base}/{quote} from any source ({detail}). "
                f"Keeping the previous rate {previous.rate} from "
                f"{previous.fetched_at:%Y-%m-%d %H:%M} ({previous.age_hours:.0f}h old). "
                f"Repricing stops automatically once that passes "
                f"{FxRate.STALE_AFTER_HOURS}h.")
        raise CommandError(
            f"Could not fetch {base}/{quote} and no previous rate is stored ({detail}). "
            f"Set one by hand with: manage.py fetch_fx --set 1.37")
