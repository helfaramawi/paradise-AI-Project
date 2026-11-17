"""Deterministic contractual deadline computation.

A deadline is only marked ``determined`` when the period, the day type and the trigger date are all
explicit. Anything assumed is recorded in ``uncertainty_notes`` — the engine never silently infers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

ENGINE_VERSION = "deadline-1.1"


@dataclass
class Calendar:
    weekend_days: list[int] = field(default_factory=lambda: [4, 5])  # Fri, Sat (Egypt)
    holidays: set[date] = field(default_factory=set)

    def is_working_day(self, d: date) -> bool:
        return d.weekday() not in self.weekend_days and d not in self.holidays

    @classmethod
    def from_org(cls, weekend_days: list[int] | None, holidays: list[str] | None) -> Calendar:
        hol = set()
        for h in holidays or []:
            try:
                hol.add(date.fromisoformat(h))
            except ValueError:
                continue
        return cls(list(weekend_days if weekend_days is not None else [4, 5]), hol)


def add_days(start: date, days: int, day_type: str, cal: Calendar) -> date:
    if day_type != "working":
        return start + timedelta(days=days)
    d, counted = start, 0
    while counted < days:
        d += timedelta(days=1)
        if cal.is_working_day(d):
            counted += 1
    return d


def working_days_between(a: date, b: date, cal: Calendar) -> int:
    step = 1 if b >= a else -1
    d, n = a, 0
    while d != b:
        d += timedelta(days=step)
        if cal.is_working_day(d):
            n += step
    return n


@dataclass
class DeadlineResult:
    due_date: date | None
    certainty: str  # determined|estimated|ambiguous|undetermined
    notes: list[dict]
    calculation: dict


def compute(trigger_date: date | None, trigger_is_confirmed: bool, days: int | None, day_type: str | None,
            cal: Calendar, *, alternatives: list[int] | None = None, trigger_wording: str | None = None) -> DeadlineResult:
    notes: list[dict] = []
    if days is None:
        return DeadlineResult(None, "undetermined", [{
            "code": "no_period", "en": "No explicit time period was found in the applicable clause.",
            "ar": "لم يتم العثور على مدة زمنية صريحة في البند المنطبق."}], {})
    if trigger_date is None:
        return DeadlineResult(None, "undetermined", [{
            "code": "no_trigger", "en": "The triggering date is unknown; record the event/awareness date.",
            "ar": "تاريخ بدء احتساب المدة غير معروف؛ يرجى تسجيل تاريخ الحدث أو العلم به."}], {"days": days})
    if alternatives:
        days = min([days, *alternatives])
    certainty = "determined"
    effective_type = day_type or "unspecified"
    if effective_type == "unspecified":
        certainty = "estimated"
        effective_type = "calendar"
        notes.append({"code": "day_type_assumed",
                      "en": "The clause does not state calendar or working days; calendar days were used (the "
                            "shorter, conservative reading). Check the contract's definition of 'day'.",
                      "ar": "لم يحدد البند ما إذا كانت الأيام تقويمية أم أيام عمل؛ تم احتسابها أيامًا تقويمية "
                            "(القراءة الأحوط). راجع تعريف \"اليوم\" في العقد."})
    if not trigger_is_confirmed:
        certainty = "estimated" if certainty == "determined" else certainty
        notes.append({"code": "trigger_assumed",
                      "en": "The period was counted from the recorded event date. If the clause runs from the date "
                            "the contractor became (or should have become) aware, confirm that date.",
                      "ar": "تم احتساب المدة من تاريخ الحدث المسجل. إذا كان البند يحتسب المدة من تاريخ علم المقاول "
                            "(أو وجوب علمه) فيجب تأكيد هذا التاريخ."})
    if alternatives and len(set(alternatives)) > 1:
        certainty = "ambiguous"
        notes.append({"code": "conflicting_periods",
                      "en": f"Different periods apply in related clauses ({', '.join(str(a) for a in sorted(set(alternatives)))} days); "
                            "the shortest was used. Legal review required.",
                      "ar": f"توجد مدد مختلفة في بنود ذات صلة ({'، '.join(str(a) for a in sorted(set(alternatives)))} يوم)؛ "
                            "تم استخدام الأقصر. مطلوب مراجعة قانونية."})
    due = add_days(trigger_date, days, effective_type, cal)
    calc = {"trigger_date": trigger_date.isoformat(), "days": days, "day_type_used": effective_type,
            "day_type_stated": day_type or "unspecified", "trigger_wording": trigger_wording,
            "weekend_days": cal.weekend_days, "holidays_considered": len(cal.holidays),
            "formula": f"{trigger_date.isoformat()} + {days} {effective_type} days = {due.isoformat()}",
            "engine": ENGINE_VERSION}
    return DeadlineResult(due, certainty, notes, calc)
