"""SPH timetable widgets based on the sph-ha timetable cards."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from typing import Any

from ..const import PADDING, DisplayConfig, Widget, WidgetType


_CHANGE_LABELS = {
    "Betr": "Betreuung",
    "Vertr": "Vertretung",
    "Entf": "Entfall",
    "Taus": "Tausch",
    "Freis": "Freistunde",
    "Raum": "Raumänderung",
    "Statt-Vertretung": "Statt-Vertretung",
    "Paus": "Pausenaufsicht",
    "SES": "Sonderunterricht",
    "Vtr. ohne Lehrer": "Vertretung ohne Lehrer",
}
_WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")


def _norm(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .translate(str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"}))
    )


def _class_name(value: str) -> str:
    return re.sub(r"^-|-+$", "", re.sub(r"[^a-z0-9]+", "-", _norm(value)))


def _find_entity(states: dict[str, Any], widget: Widget) -> dict[str, Any] | None:
    entity_id = str(widget.get("entity") or widget.get("sensor") or "")
    if entity_id:
        return states.get(entity_id)
    child = _norm(widget.get("child"))
    for entity_id, state in states.items():
        attrs = state.get("attributes", {}) if isinstance(state, dict) else {}
        if not child or _norm(attrs.get("kind_kürzel") or attrs.get("kind")) == child:
            if isinstance(attrs.get("eigener_plan"), list) or isinstance(attrs.get("tage"), list):
                return state
    return None


def _source_days(attrs: dict[str, Any]) -> list[list[dict[str, Any]]]:
    raw = attrs.get("eigener_plan")
    if not isinstance(raw, list):
        raw = attrs.get("tage")
    if not isinstance(raw, list):
        return []
    # Both sph-ha versions use a list of five day arrays. The newer
    # sensor can also expose objects containing a day field.
    if raw and all(isinstance(item, dict) for item in raw):
        grouped: dict[int, list[dict[str, Any]]] = {}
        for item in raw:
            d = item.get("day")
            if isinstance(d, int):
                grouped.setdefault(d, []).append(item)
        if grouped:
            return [grouped.get(i, []) for i in range(7)]
    return [list(day) if isinstance(day, list) else [] for day in raw]


def _active(lesson: dict[str, Any], week: str) -> bool:
    badge = lesson.get("badge")
    if badge in (None, "") or not week:
        return True
    values = badge if isinstance(badge, list) else re.split(r"[,;/|]+", str(badge))
    return any(str(v).strip().upper() == week.upper() for v in values)


def _teacher(value: Any, teachers: dict[str, Any]) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    for key, val in teachers.items():
        if str(key).strip().lower() == raw.lower():
            return str(val)
    return raw


def _entries(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            if value.get("fach") or value.get("subject"):
                if value.get("stunde") or value.get("datum") or value.get("art") or value.get("vertreter"):
                    result.append(value)
            for item in value.values():
                walk(item)

    walk(attrs)
    return result


def _period_matches(value: Any, lesson: dict[str, Any]) -> bool:
    if not value or not lesson:
        return True
    numbers = [int(x) for x in re.findall(r"\d+", str(value)) if 0 < int(x) < 20]
    index = int(lesson.get("index") or 0)
    if not numbers:
        return True
    if len(numbers) == 2 and re.search(r"[-–—]", str(value)):
        return numbers[0] <= index <= numbers[1]
    return index in numbers


def _date_matches(item: dict[str, Any], target: date, day_index: int) -> bool:
    raw = str(item.get("datum") or "").strip().lower()
    if not raw:
        return False
    wd = _WEEKDAYS.index(raw.capitalize()) if raw.capitalize() in _WEEKDAYS else -1
    if wd >= 0:
        return wd == day_index
    match = re.match(r"(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?", raw)
    if not match:
        return False
    if int(match.group(1)) != target.day or int(match.group(2)) != target.month:
        return False
    year = match.group(3)
    return not year or int(year) in (target.year, target.year % 100)


def _class_matches(item: dict[str, Any], child_class: str) -> bool:
    if not child_class or not item.get("klasse"):
        return False
    return any(_norm(x) == _norm(child_class) for x in re.split(r"[,;/|]+", str(item["klasse"])))


def _substitute(lesson: dict[str, Any], day_index: int, monday: date, ctx: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
    base = {
        "start": str(lesson.get("start") or ""),
        "end": str(lesson.get("end") or ""),
        "index": int(lesson.get("index") or 0),
        "subject": str(lesson.get("fach") or lesson.get("subject") or "Unterricht"),
        "teacher": _teacher(lesson.get("teacher"), ctx["teachers"]),
        "room": str(lesson.get("room") or ""),
        "badge": "",
        "change_class": "",
        "cancelled": False,
    }
    entries = ctx["entries"]
    if not entries or not lesson.get("subject"):
        return base
    target = monday + timedelta(days=day_index)
    candidates = [
        item for item in entries
        if _class_matches(item, ctx["child_class"])
        and _date_matches(item, target, day_index)
        and _period_matches(item.get("stunde"), lesson)
        and _norm(item.get("fach_original") or item.get("subject_original") or item.get("fach") or item.get("subject")) == _norm(lesson.get("subject"))
    ]
    if not candidates:
        return base
    item = candidates[0]
    art = str(item.get("art") or "").strip()
    low = _norm(art)
    cancelled = any(x in low for x in ("entfall", "ausfall", "frei"))
    changed = str(item.get("fach") or item.get("subject") or lesson.get("fach") or lesson.get("subject") or "")
    original = str(item.get("fach_original") or item.get("subject_original") or lesson.get("subject") or lesson.get("fach") or "")
    fachwechsel = not cancelled and _norm(changed) != _norm(original)
    label = "Fachwechsel" if fachwechsel else (_CHANGE_LABELS.get(art, art or "Vertretung"))
    base.update(
        subject=base["subject"] if cancelled else aliases.get(_norm(changed), changed),
        teacher=_teacher(item.get("vertreter") or item.get("lehrer_nach") or item.get("teacher"), ctx["teachers"]) or base["teacher"],
        room=str(item.get("raum") or item.get("room") or base["room"]),
        badge=label,
        change_class=_class_name(label),
        cancelled=cancelled,
    )
    return base


def _prepare(widget: Widget, config: DisplayConfig, *, mode: str) -> dict[str, object]:
    states = config.get("states", {})
    entity = _find_entity(states, widget)
    attrs = entity.get("attributes", {}) if entity else {}
    days = _source_days(attrs)
    week = str(attrs.get("wochenkennung") or "").strip().upper()
    monday = date.today() - timedelta(days=date.today().weekday())
    teachers: dict[str, Any] = {}
    for state_id, state in states.items():
        if state_id == "sensor.kfg_kollegium":
            teachers = state.get("attributes", {}).get("lehrer", {}) or {}
            break
    ctx = {"entries": _entries(states.get("sensor.vertretungsplan", {}).get("attributes", {})), "teachers": teachers, "child_class": str(attrs.get("klasse") or widget.get("klasse") or "")}
    aliases: dict[str, str] = {}
    for day in days:
        for lesson in day:
            if lesson.get("subject") and lesson.get("fach") and _norm(lesson["subject"]) != _norm(lesson["fach"]):
                aliases[_norm(lesson["subject"])] = str(lesson["fach"])
    if mode == "today":
        indices = [date.today().weekday()] if date.today().weekday() < len(days) else []
    else:
        count = max(1, min(int(widget.get("days", 5)), 7))
        start = 0 if mode == "week" else date.today().weekday()
        indices = [i for i in range(start, min(start + count, len(days), 7))]
    day_rows: list[dict[str, object]] = []
    for i in indices:
        target = monday + timedelta(days=i)
        lessons = [_substitute(l, i, monday, ctx, aliases) for l in days[i] if _active(l, week)]
        day_rows.append({"index": i, "name": _WEEKDAYS[i], "date": target.strftime("%d.%m.%Y"), "week": week, "lessons": lessons})
    width = config["width"] if mode == "grid" else int(widget.get("w", config["width"] - int(widget.get("x", PADDING))))
    x = 0 if mode == "grid" else int(widget.get("x", PADDING))
    return {"w": width, "h": int(widget.get("h", 0)), "x": x, "days": day_rows, "has_entity": bool(entity), "empty_text": "Kein passender Stundenplan gefunden." if not entity else "Kein Unterricht"}


def _build_sph_stundenplan_context(widget: Widget, config: DisplayConfig) -> dict[str, object]:
    return _prepare(widget, config, mode="week")


def _build_sph_stundenplan_tag_context(widget: Widget, config: DisplayConfig) -> dict[str, object]:
    return _prepare(widget, config, mode="today")


def _build_sph_stundenplan_grid_context(widget: Widget, config: DisplayConfig) -> dict[str, object]:
    return _prepare(widget, config, mode="grid")
