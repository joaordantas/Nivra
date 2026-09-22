from __future__ import annotations

import calendar
import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median


RECURRENCE_MIN_OCCURRENCES = 3
RECURRENCE_HIGH_CONFIDENCE_OCCURRENCES = 5
RECURRENCE_MIN_REGULARITY = Decimal("0.80")
RECURRENCE_VALUE_RELATIVE_TOLERANCE = Decimal("0.25")
RECURRENCE_VALUE_ABSOLUTE_TOLERANCE = Decimal("10.00")
RECURRENCE_CHANGE_RELATIVE_THRESHOLD = Decimal("0.20")
RECURRENCE_CHANGE_ABSOLUTE_THRESHOLD = Decimal("10.00")

ANOMALY_GLOBAL_MIN_SAMPLES = 8
ANOMALY_CATEGORY_MIN_SAMPLES = 4
ANOMALY_MIN_AMOUNT = Decimal("50.00")
ANOMALY_GLOBAL_RATIO = Decimal("3.00")
ANOMALY_CATEGORY_RATIO = Decimal("2.50")
ANOMALY_MIN_ROBUST_Z = Decimal("3.50")

_VARIABLE_REFERENCE = re.compile(
    r"\b(?:id|ref|referencia|nsu|auth|aut|terminal|pedido|order)\s*[:#-]?\s*[a-z0-9-]{4,}\b"
)
_DOMAIN_SUFFIX = re.compile(r"\.(?:com(?:\.br)?|net|app)\b")
_MERCHANT_TRAILING_ID = re.compile(r"\b([a-z]{3,})\d{4,}\b")
_LONG_NUMERIC = re.compile(r"\b\d{4,}\b")
_LONG_IDENTIFIER = re.compile(
    r"\b(?=[a-z0-9-]{6,}\b)(?=(?:[a-z0-9-]*\d){2})[a-z0-9-]+\b"
)
_DATE_LIKE = re.compile(r"\b\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b")
_PROVIDER_PREFIX = re.compile(
    r"^(?:compra|pagamento|pgto|debito|credito|pix|ted|doc)\s+(?:em|para|a\s+)?"
)
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _entry_date(entry: dict) -> date:
    value = entry["date"]
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def normalize_financial_description(value: object) -> str:
    """Normaliza descrições sem remover palavras que identificam o estabelecimento."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower().strip()
    text = _DOMAIN_SUFFIX.sub(" ", text)
    text = _DATE_LIKE.sub(" ", text)
    text = _VARIABLE_REFERENCE.sub(" ", text)
    text = _MERCHANT_TRAILING_ID.sub(r"\1", text)
    text = _LONG_NUMERIC.sub(" ", text)
    text = _LONG_IDENTIFIER.sub(" ", text)
    text = _NON_ALPHANUMERIC.sub(" ", text)
    text = _PROVIDER_PREFIX.sub("", text).strip()
    return " ".join(text.split())


def _category_identity(entry: dict) -> str:
    stable_key = entry.get("category_key")
    if stable_key:
        return f"key:{stable_key}"
    if entry.get("category_id") is not None:
        return f"id:{entry['category_id']}"
    return f"name:{normalize_financial_description(entry.get('category'))}"


def _is_month_end(value: date) -> bool:
    return value.day == calendar.monthrange(value.year, value.month)[1]


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    last_day = calendar.monthrange(year, month)[1]
    day = last_day if _is_month_end(value) else min(value.day, last_day)
    return date(year, month, day)


def _add_year(value: date) -> date:
    target_year = value.year + 1
    return date(target_year, value.month, min(value.day, calendar.monthrange(target_year, value.month)[1]))


def _month_distance(first: date, second: date) -> int:
    return (second.year - first.year) * 12 + second.month - first.month


def _calendar_month_match(first: date, second: date) -> bool:
    return _month_distance(first, second) == 1 and (
        abs(first.day - second.day) <= 3
        or (_is_month_end(first) and _is_month_end(second))
    )


def _annual_match(first: date, second: date) -> bool:
    return _month_distance(first, second) == 12 and (
        abs(first.day - second.day) <= 7
        or (_is_month_end(first) and _is_month_end(second))
    )


def _frequency(dates: list[date]) -> tuple[str | None, Decimal, int | None]:
    pairs = list(zip(dates, dates[1:], strict=False))
    if not pairs:
        return None, Decimal("0"), None
    gaps = [(second - first).days for first, second in pairs]
    candidates = [
        ("weekly", sum(abs(gap - 7) <= 2 for gap in gaps), 7),
        ("fortnightly", sum(abs(gap - 14) <= 3 for gap in gaps), 14),
        ("monthly", sum(_calendar_month_match(first, second) for first, second in pairs), None),
        ("approximately_monthly", sum(25 <= gap <= 35 for gap in gaps), round(float(median(gaps)))),
        ("annual", sum(_annual_match(first, second) for first, second in pairs), None),
    ]
    frequency, matches, typical_days = max(candidates, key=lambda item: item[1])
    regularity = Decimal(matches) / Decimal(len(gaps))
    if regularity < RECURRENCE_MIN_REGULARITY:
        return None, regularity, None
    return frequency, regularity, typical_days


def _median_money(values: list[Decimal]) -> Decimal:
    return _money(median(values))


def _values_stable(values: list[Decimal]) -> bool:
    if not values:
        return False
    typical = _median_money(values)
    allowed = max(
        RECURRENCE_VALUE_ABSOLUTE_TOLERANCE,
        typical * RECURRENCE_VALUE_RELATIVE_TOLERANCE,
    )
    return all(abs(value - typical) <= allowed for value in values)


def _value_change(values: list[Decimal], observed_at: date) -> dict | None:
    if len(values) < 4 or not _values_stable(values[:-1]):
        return None
    previous_typical = _median_money(values[:-1])
    if previous_typical <= 0:
        return None
    current = values[-1]
    difference = current - previous_typical
    relative = abs(difference) / previous_typical
    if (
        abs(difference) < RECURRENCE_CHANGE_ABSOLUTE_THRESHOLD
        or relative < RECURRENCE_CHANGE_RELATIVE_THRESHOLD
    ):
        return None
    direction = "increase" if difference > 0 else "decrease"
    percentage = round(float(difference * Decimal("100") / previous_typical), 2)
    return {
        "previous_typical_amount": float(previous_typical),
        "current_amount": float(current),
        "change_percent": percentage,
        "direction": direction,
        "detected_at": observed_at.isoformat(),
        "reason": (
            f"O valor mais recente ficou {abs(percentage):.0f}% "
            f"{'acima' if direction == 'increase' else 'abaixo'} da mediana anterior."
        ),
    }


def _next_occurrence(
    last: date,
    frequency: str,
    typical_days: int | None,
    regularity: Decimal,
) -> date | None:
    if regularity < Decimal("1"):
        return None
    if frequency == "weekly":
        return last + timedelta(days=7)
    if frequency == "fortnightly":
        return last + timedelta(days=14)
    if frequency == "monthly":
        return _add_months(last, 1)
    if frequency == "approximately_monthly" and typical_days is not None:
        return last + timedelta(days=typical_days)
    if frequency == "annual":
        return _add_year(last)
    return None


def detect_recurring_expenses(entries: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for entry in entries:
        normalized = normalize_financial_description(entry.get("description"))
        if (
            entry.get("type") != "saida"
            or entry.get("neutral")
            or entry.get("parcelamento_id") is not None
            or not normalized
        ):
            continue
        groups[(normalized, _category_identity(entry))].append(entry)

    patterns: list[dict] = []
    for (normalized, category_identity), occurrences in groups.items():
        occurrences.sort(key=lambda item: (_entry_date(item), str(item.get("source")), int(item.get("id", 0))))
        if len(occurrences) < RECURRENCE_MIN_OCCURRENCES:
            continue
        dates = [_entry_date(item) for item in occurrences]
        if len(set(dates)) != len(dates):
            continue
        frequency, regularity, typical_days = _frequency(dates)
        if frequency is None:
            continue
        values = [_money(item["amount"]) for item in occurrences]
        change = _value_change(values, dates[-1])
        stable_values = values[:-1] if change is not None else values
        if not _values_stable(stable_values):
            continue

        typical = _median_money(stable_values)
        variation = (
            max(abs(value - typical) for value in stable_values)
            * Decimal("100")
            / typical
            if typical > 0
            else Decimal("0")
        )
        confidence = (
            "high"
            if len(occurrences) >= RECURRENCE_HIGH_CONFIDENCE_OCCURRENCES
            and regularity >= Decimal("0.80")
            and variation <= Decimal("10")
            else "medium"
        )
        next_date = _next_occurrence(dates[-1], frequency, typical_days, regularity)
        descriptions = [str(item.get("description") or "Despesa recorrente") for item in occurrences]
        representative = Counter(descriptions).most_common(1)[0][0]
        reasons = [
            f"{len(occurrences)} ocorrências com descrição e categoria consistentes.",
            f"{round(float(regularity * Decimal('100')))}% dos intervalos seguem a frequência detectada.",
            f"A variação dos valores de referência ficou em até {float(variation):.1f}%.",
        ]
        if next_date is None:
            reasons.append("Os intervalos não são uniformes o suficiente para prever a próxima data.")
        pattern_key = f"{normalized}|{category_identity}|{frequency}"
        patterns.append({
            "pattern_id": hashlib.sha256(pattern_key.encode("utf-8")).hexdigest()[:16],
            "description": representative,
            "normalized_description": normalized,
            "category": str(occurrences[-1].get("category") or "Sem categoria"),
            "category_key": occurrences[-1].get("category_key"),
            "frequency": frequency,
            "occurrence_count": len(occurrences),
            "typical_amount": float(typical),
            "value_variation_percent": round(float(variation), 2),
            "first_occurrence": dates[0].isoformat(),
            "last_occurrence": dates[-1].isoformat(),
            "next_occurrence": next_date.isoformat() if next_date is not None else None,
            "confidence": confidence,
            "reasons": reasons,
            "sources": sorted({str(item.get("source", "manual")) for item in occurrences}),
            "amount_change": change,
            "data_nature": "deterministic_inference",
        })

    return sorted(
        patterns,
        key=lambda item: (
            0 if item["amount_change"] and item["amount_change"]["direction"] == "increase" else 1,
            0 if item["confidence"] == "high" else 1,
            -_money(item["typical_amount"]),
            item["description"].lower(),
        ),
    )


def _baseline(values: list[Decimal]) -> tuple[Decimal, Decimal]:
    center = _median_money(values)
    deviations = [abs(value - center) for value in values]
    return center, _median_money(deviations)


def _is_anomalous(
    amount: Decimal,
    baseline: Decimal,
    mad: Decimal,
    ratio_threshold: Decimal,
) -> tuple[bool, Decimal | None]:
    if baseline <= 0 or amount < ANOMALY_MIN_AMOUNT or amount < baseline * ratio_threshold:
        return False, None
    if mad <= 0:
        return True, None
    robust_z = Decimal("0.6745") * (amount - baseline) / mad
    return robust_z >= ANOMALY_MIN_ROBUST_Z, robust_z


def detect_unusual_expenses(
    entries: list[dict],
    period_start: date,
    period_end: date,
) -> list[dict]:
    expenses = [
        entry
        for entry in entries
        if entry.get("type") == "saida"
        and not entry.get("neutral")
        and entry.get("parcelamento_id") is None
    ]
    candidates = [
        entry for entry in expenses if period_start <= _entry_date(entry) <= period_end
    ]
    unusual: list[dict] = []
    for entry in candidates:
        observed_at = _entry_date(entry)
        previous = [item for item in expenses if _entry_date(item) < observed_at]
        global_values = [_money(item["amount"]) for item in previous]
        category_values = [
            _money(item["amount"])
            for item in previous
            if _category_identity(item) == _category_identity(entry)
        ]
        amount = _money(entry["amount"])

        global_result = False
        global_baseline = global_mad = None
        global_robust_z = None
        if len(global_values) >= ANOMALY_GLOBAL_MIN_SAMPLES:
            global_baseline, global_mad = _baseline(global_values)
            global_result, global_robust_z = _is_anomalous(
                amount, global_baseline, global_mad, ANOMALY_GLOBAL_RATIO
            )

        category_result = False
        category_baseline = category_mad = None
        category_robust_z = None
        if len(category_values) >= ANOMALY_CATEGORY_MIN_SAMPLES:
            category_baseline, category_mad = _baseline(category_values)
            category_result, category_robust_z = _is_anomalous(
                amount, category_baseline, category_mad, ANOMALY_CATEGORY_RATIO
            )
            if not category_result:
                global_result = False

        if not global_result and not category_result:
            continue
        context = "both" if global_result and category_result else "category" if category_result else "global"
        chosen_baseline = category_baseline if category_result else global_baseline
        chosen_mad = category_mad if category_result else global_mad
        chosen_sample = len(category_values) if category_result else len(global_values)
        if chosen_baseline is None or chosen_baseline <= 0:
            continue
        ratio = amount / chosen_baseline
        if context == "category":
            reason = (
                f"Este gasto foi {float(ratio):.1f}× maior que a mediana recente "
                f"da categoria {entry.get('category') or 'Sem categoria'}."
            )
        elif context == "both":
            reason = (
                f"Este gasto foi {float(ratio):.1f}× maior que a mediana da categoria "
                "e também ficou fora do padrão geral."
            )
        else:
            reason = f"Este gasto foi {float(ratio):.1f}× maior que a mediana recente geral."
        unusual.append({
            "id": int(entry["id"]),
            "description": str(entry["description"]),
            "amount": float(amount),
            "date": observed_at.isoformat(),
            "category": str(entry.get("category") or "Sem categoria"),
            "account": str(entry.get("account") or "Sem conta"),
            "source": str(entry.get("source") or "manual"),
            "baseline": float(chosen_baseline),
            "times_baseline": round(float(ratio), 2),
            "context": context,
            "sample_size": chosen_sample,
            "global_baseline": float(global_baseline) if global_baseline is not None else None,
            "category_baseline": float(category_baseline) if category_baseline is not None else None,
            "median_absolute_deviation": float(chosen_mad) if chosen_mad is not None else None,
            "robust_z_score": round(float(category_robust_z or global_robust_z), 2)
            if (category_robust_z is not None or global_robust_z is not None)
            else None,
            "reason": reason,
            "data_nature": "deterministic_inference",
        })

    return sorted(
        unusual,
        key=lambda item: (item["times_baseline"], item["amount"]),
        reverse=True,
    )[:5]
