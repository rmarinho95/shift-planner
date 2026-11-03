"""Schichtplan für das IT-Service Desk.

Der Generator hält diese Regeln ein:

- 100 % Pensum: höchstens 2 Homeoffice-Tage. 80 %: höchstens 1. Ab 60 %: keines.
- Homeoffice ist nicht fix. Es wird zufällig auf Dienstag bis Donnerstag verteilt.
  Ein Wunschtag kann einen bestimmten Tag festlegen.
- Ein Ferien- oder Freier-Tag in der Woche senkt das Kontingent auf höchstens 1.
  Zwei solche Tage: in dieser Woche kein Homeoffice.
- Montag- und Freitag-Homeoffice rotieren. Wer den Tag schon hatte, bekommt ihn
  erst wieder, wenn alle anderen Berechtigten ihn einmal hatten.
- Dieselbe Rotation gilt für Frühschicht und Spätschicht am Freitag.
- Ein Mittwoch mit Teammeeting ist Präsenzpflicht: kein Homeoffice.
- Teilzeit bekommt so viele freie Tage, wie das Pensum vorgibt.
  Wer keine Schicht arbeitet, plant Bürotage selbst (Flex).
- Bei mehr als zwei Personen bleiben mindestens zwei im Dienst, bevor weiter
  Homeoffice vergeben wird.
"""

from __future__ import annotations

import json
import random
import calendar
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


FONT = "Segoe UI"
BG = "#F4F5F7"
CARD = "#FFFFFF"
INK = "#1C1C1E"
MUTED = "#6B7280"
LINE = "#E6E8EC"
SOFT = "#F7F7F8"

DATA_PATH = Path(__file__).with_name("shift_planner_data.json")
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
PENSUM_VALUES = ["100%", "80%", "60%", "40%", "20%"]
WISH_TYPES = ["Frühschicht", "Spätschicht", "Homeoffice"]
FAIR_KEYS = ("ho_monday", "ho_friday", "frueh_friday", "spaet_friday")
ABSENT = {"Ferien", "Homeoffice", "Teilzeit (Frei)"}

COLOR_CONFIG = {
    "Frühschicht": {"bg": "#E4F5EA", "fg": "#14532D", "short": "Früh", "legend": "Früh · 07:30–16:30"},
    "Spätschicht": {"bg": "#FEF3C7", "fg": "#92400E", "short": "Spät", "legend": "Spät · 08:30–17:30"},
    "Homeoffice": {"bg": "#E0F2FE", "fg": "#075985", "short": "Homeoffice", "legend": "Homeoffice"},
    "Plant Arbeitszeiten selber": {"bg": "#F3E8FF", "fg": "#6B21A8", "short": "Flex", "legend": "Flex · eigene Zeiten"},
    "Teilzeit (Frei)": {"bg": "#F3F4F6", "fg": "#374151", "short": "Frei", "legend": "Frei"},
    "Ferien": {"bg": "#EDE9FE", "fg": "#5B21B6", "short": "Ferien", "legend": "Ferien"},
}

SAMPLE_EMPLOYEES = [
    {"name": "Anna", "pensum": 100, "fixed_off": None, "no_shift": False},
    {"name": "Ben", "pensum": 80, "fixed_off": None, "no_shift": False},
    {"name": "Clara", "pensum": 60, "fixed_off": None, "no_shift": False},
    {"name": "David", "pensum": 100, "fixed_off": None, "no_shift": True},
]


def empty_history():
    return {key: [] for key in FAIR_KEYS}


def weekdays_of(year, week):
    monday = date.fromisocalendar(year, week, 1)
    return [monday + timedelta(days=i) for i in range(5)]


def is_vacation(name, day, vacations):
    return any(v["emp"] == name and v["start"] <= day <= v["end"] for v in vacations)


def ho_cap(pensum, absences):
    """Höchstzahl Homeoffice-Tage in einer Woche."""
    if pensum == 100:
        cap = 2
    elif pensum == 80:
        cap = 1
    else:
        cap = 0
    if absences >= 2:
        return 0
    if absences == 1:
        return min(cap, 1)
    return cap


def eligible_names(key, employees):
    names = set()
    for emp in employees:
        if key in ("ho_monday", "ho_friday") and emp["pensum"] not in (100, 80):
            continue
        if key in ("frueh_friday", "spaet_friday") and emp["no_shift"]:
            continue
        if key in ("ho_friday", "frueh_friday", "spaet_friday") and emp["fixed_off"] == 4:
            continue
        if key == "ho_monday" and emp["fixed_off"] == 0:
            continue
        names.add(emp["name"])
    return names


def open_round(events, eligible):
    """Personen, die in der laufenden Runde den Tag schon hatten.

    Eine Runde ist zu Ende, sobald jede berechtigte Person einmal vorkommt.
    Danach beginnt die nächste Runde bei null.
    """
    eligible = set(eligible)
    current = set()
    if not eligible:
        return current
    for _day, _seq, name in sorted(events, key=lambda item: (item[0], item[1])):
        if name not in eligible:
            continue
        current.add(name)
        if eligible <= current:
            current = set()
    return current


def generate_schedule(
    employees,
    wishes,
    vacations,
    teammeetings,
    start,
    end,
    history=None,
    next_seq=1,
    rng=None,
):
    """Erzeugt den Plan. Die Eingaben werden nicht verändert."""
    rng = rng if rng is not None else random.Random()
    employees = [dict(emp) for emp in employees]
    if end < start:
        return {"error": "Das Enddatum liegt vor dem Startdatum."}

    work_days = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            work_days.append(cursor)
        cursor += timedelta(days=1)
    if not work_days:
        return {"error": "Im gewählten Zeitraum liegt kein Arbeitstag (Montag bis Freitag)."}

    buckets = {}
    order = []
    for day in work_days:
        key = day.isocalendar()[:2]
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(day)
    weeks = [(key, buckets[key]) for key in order]

    meeting_set = set(teammeetings)
    wish_map = {(w["emp"], w["date"]): w["type"] for w in wishes}
    names = [emp["name"] for emp in employees]
    plan = {name: {} for name in names}
    shift_counts = {name: {"Frühschicht": 0, "Spätschicht": 0} for name in names}
    eligible = {key: eligible_names(key, employees) for key in FAIR_KEYS}

    events = {key: [] for key in FAIR_KEYS}
    known_names = set(names)
    for key in FAIR_KEYS:
        for item in (history or {}).get(key, []):
            if item["name"] not in known_names:
                continue
            day = item["date"] if isinstance(item["date"], date) else date.fromisoformat(item["date"])
            if start <= day <= end:
                continue
            events[key].append((day, int(item["seq"]), item["name"]))

    seq = next_seq
    unfulfilled = []
    warnings = []

    def allows(key, name):
        if name not in eligible[key]:
            return False
        return name not in open_round(events[key], eligible[key])

    def add_event(key, day, name):
        nonlocal seq
        if name not in eligible[key]:
            return
        events[key].append((day, seq, name))
        seq += 1

    def office_count(day):
        count = 0
        for emp in employees:
            if plan[emp["name"]].get(day) not in ABSENT:
                count += 1
        return count

    def can_take_ho(day):
        if len(employees) <= 2:
            return True
        return office_count(day) > 2

    def place_ho(emp, day):
        name = emp["name"]
        plan[name][day] = "Homeoffice"
        if day.weekday() == 0:
            add_event("ho_monday", day, name)
        elif day.weekday() == 4:
            add_event("ho_friday", day, name)

    def place_shift(emp, day, shift):
        name = emp["name"]
        plan[name][day] = shift
        shift_counts[name][shift] += 1
        if day.weekday() == 4:
            add_event("frueh_friday" if shift == "Frühschicht" else "spaet_friday", day, name)

    bridge = set()
    for emp in employees:
        name = emp["name"]
        for index, day in enumerate(work_days):
            if is_vacation(name, day, vacations):
                continue
            if index > 0 and is_vacation(name, work_days[index - 1], vacations):
                bridge.add((name, day))
            if index < len(work_days) - 1 and is_vacation(name, work_days[index + 1], vacations):
                bridge.add((name, day))

    for (year, week), week_days in weeks:
        pinned = set()
        full_week = weekdays_of(year, week)

        for day in week_days:
            for emp in employees:
                if is_vacation(emp["name"], day, vacations):
                    plan[emp["name"]][day] = "Ferien"

        for day in week_days:
            for emp in employees:
                name = emp["name"]
                if day in plan[name]:
                    continue
                if emp["fixed_off"] is not None and day.weekday() == emp["fixed_off"]:
                    plan[name][day] = "Teilzeit (Frei)"

        caps = {}
        ho_count = defaultdict(int)
        for emp in employees:
            name = emp["name"]
            explicit = set()
            for day in full_week:
                if is_vacation(name, day, vacations):
                    explicit.add(day)
                elif emp["fixed_off"] is not None and day.weekday() == emp["fixed_off"]:
                    explicit.add(day)

            target_off = (100 - emp["pensum"]) // 20
            needed = max(0, target_off - len(explicit))
            if needed:
                empty_days = [day for day in week_days if day not in plan[name]]
                wish_days = {day for day in empty_days if (name, day) in wish_map}
                quiet = [day for day in empty_days if day not in wish_days and day not in meeting_set]
                avoid_wishes = [day for day in empty_days if day not in wish_days]
                if len(quiet) >= needed:
                    pool = quiet
                elif len(avoid_wishes) >= needed:
                    pool = avoid_wishes
                else:
                    pool = empty_days
                take = min(needed, len(pool))
                for day in rng.sample(pool, take):
                    plan[name][day] = "Teilzeit (Frei)"

            absences = len(explicit) + sum(
                1 for day in week_days if plan[name].get(day) == "Teilzeit (Frei)" and day not in explicit
            )
            caps[name] = ho_cap(emp["pensum"], absences)

        for day in week_days:
            for emp in employees:
                name = emp["name"]
                wish = wish_map.get((name, day))
                if not wish:
                    continue
                current = plan[name].get(day)
                if current in ("Ferien", "Teilzeit (Frei)"):
                    unfulfilled.append(
                        f"{name}, {day.strftime('%d.%m.%Y')}: {wish} liegt auf einem freien Tag oder in den Ferien."
                    )
                    continue
                if wish == "Homeoffice":
                    if day in meeting_set:
                        unfulfilled.append(
                            f"{name}, {day.strftime('%d.%m.%Y')}: Homeoffice fällt auf ein Teammeeting."
                        )
                        continue
                    if ho_count[name] >= caps[name]:
                        unfulfilled.append(
                            f"{name}, {day.strftime('%d.%m.%Y')}: Homeoffice-Kontingent dieser Woche ist ausgeschöpft."
                        )
                        continue
                    place_ho(emp, day)
                    ho_count[name] += 1
                    pinned.add((name, day))
                elif wish in ("Frühschicht", "Spätschicht"):
                    if emp["no_shift"]:
                        unfulfilled.append(
                            f"{name}, {day.strftime('%d.%m.%Y')}: {wish} ist nicht möglich, die Person plant Zeiten selbst."
                        )
                        continue
                    place_shift(emp, day, wish)

        for _pass in range(2):
            order_emps = [emp for emp in employees if ho_count[emp["name"]] < caps[emp["name"]]]
            rng.shuffle(order_emps)
            for emp in order_emps:
                name = emp["name"]
                if ho_count[name] >= caps[name]:
                    continue
                pool = []
                for day in week_days:
                    if day.weekday() not in (1, 2, 3):
                        continue
                    if day in plan[name] or day in meeting_set:
                        continue
                    if not can_take_ho(day):
                        continue
                    pool.append(day)
                if not pool:
                    continue
                best = min((0 if (name, day) in bridge else 1) for day in pool)
                pool = [day for day in pool if (0 if (name, day) in bridge else 1) == best]
                place_ho(emp, rng.choice(pool))
                ho_count[name] += 1

        def ensure_rotation(day, key):
            if day is None or day in meeting_set:
                return
            if any(plan[emp["name"]].get(day) == "Homeoffice" for emp in employees):
                return
            waiting = [emp for emp in employees if allows(key, emp["name"])]
            ranked = []
            for emp in waiting:
                name = emp["name"]
                if day in plan[name] or not can_take_ho(day):
                    continue
                spare = caps[name] - ho_count[name]
                movable = [
                    src for src in week_days
                    if plan[name].get(src) == "Homeoffice"
                    and src.weekday() not in (0, 4)
                    and (name, src) not in pinned
                ]
                if spare > 0:
                    ranked.append((0, rng.random(), emp, None))
                elif movable:
                    ranked.append((1, rng.random(), emp, movable))
            if not ranked:
                return
            ranked.sort(key=lambda item: (item[0], item[1]))
            _priority, _roll, emp, movable = ranked[0]
            if movable:
                src = rng.choice(movable)
                del plan[emp["name"]][src]
                plan[emp["name"]][day] = "Homeoffice"
                if day.weekday() == 0:
                    add_event("ho_monday", day, emp["name"])
                elif day.weekday() == 4:
                    add_event("ho_friday", day, emp["name"])
            else:
                place_ho(emp, day)
                ho_count[emp["name"]] += 1

        friday = next((day for day in week_days if day.weekday() == 4), None)
        monday = next((day for day in week_days if day.weekday() == 0), None)
        ensure_rotation(friday, "ho_friday")
        ensure_rotation(monday, "ho_monday")

        for day in week_days:
            for emp in employees:
                if emp["no_shift"] and day not in plan[emp["name"]]:
                    plan[emp["name"]][day] = "Plant Arbeitszeiten selber"

            on_site = [
                emp for emp in employees
                if not emp["no_shift"] and plan[emp["name"]].get(day) not in ABSENT
            ]
            unassigned = [emp["name"] for emp in on_site if day not in plan[emp["name"]]]
            count_on_site = len(on_site)
            already_early = sum(1 for emp in on_site if plan[emp["name"]].get(day) == "Frühschicht")
            if count_on_site >= 2:
                desired_early = min(max((count_on_site + 1) // 2, 1), count_on_site - 1)
            elif count_on_site == 1:
                desired_early = 1
            else:
                desired_early = 0
            early_left = min(max(0, desired_early - already_early), len(unassigned))
            late_left = len(unassigned) - early_left
            is_friday = day.weekday() == 4
            remaining = list(unassigned)

            def fair_penalty(person, key):
                if not is_friday:
                    return 0
                return 0 if allows(key, person) else 1

            while remaining and (early_left or late_left):
                fresh_early = [person for person in remaining if fair_penalty(person, "frueh_friday") == 0]
                fresh_late = [person for person in remaining if fair_penalty(person, "spaet_friday") == 0]
                if early_left and not late_left:
                    take_early = True
                elif late_left and not early_left:
                    take_early = False
                else:
                    take_early = len(fresh_early) <= len(fresh_late)

                if take_early:
                    pool = fresh_early or remaining
                    pool = sorted(
                        pool,
                        key=lambda person: (
                            fair_penalty(person, "frueh_friday"),
                            shift_counts[person]["Frühschicht"] - shift_counts[person]["Spätschicht"],
                            rng.random(),
                        ),
                    )
                    chosen = pool[0]
                    emp = next(item for item in employees if item["name"] == chosen)
                    place_shift(emp, day, "Frühschicht")
                    early_left -= 1
                else:
                    pool = fresh_late or remaining
                    pool = sorted(
                        pool,
                        key=lambda person: (
                            fair_penalty(person, "spaet_friday"),
                            shift_counts[person]["Spätschicht"] - shift_counts[person]["Frühschicht"],
                            rng.random(),
                        ),
                    )
                    chosen = pool[0]
                    emp = next(item for item in employees if item["name"] == chosen)
                    place_shift(emp, day, "Spätschicht")
                    late_left -= 1
                remaining.remove(chosen)

            early_now = sum(1 for emp in on_site if plan[emp["name"]].get(day) == "Frühschicht")
            late_now = sum(1 for emp in on_site if plan[emp["name"]].get(day) == "Spätschicht")
            flex_here = any(plan[emp["name"]].get(day) == "Plant Arbeitszeiten selber" for emp in employees)
            if count_on_site == 0 and not flex_here:
                warnings.append(f"{day.strftime('%d.%m.%Y')}: niemand im Dienst.")
            elif count_on_site >= 2 and (early_now == 0 or late_now == 0):
                warnings.append(f"{day.strftime('%d.%m.%Y')}: Früh- und Spätschicht sind nicht beide besetzt.")

    history_out = {}
    for key in FAIR_KEYS:
        history_out[key] = [
            {"date": day.isoformat(), "name": name, "seq": event_seq}
            for day, event_seq, name in sorted(events[key], key=lambda item: (item[0], item[1]))
        ]

    return {
        "plan": plan,
        "weeks": weeks,
        "warnings": warnings,
        "unfulfilled": unfulfilled,
        "history": history_out,
        "next_seq": seq,
    }


def load_state(path=DATA_PATH):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.loads(handle.read())


def save_state(state, path=DATA_PATH):
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def parse_stored_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


class CalendarDatePicker(tk.Frame):
    """Kleiner Kalender. Eingabe im Format TT.MM.JJJJ."""

    def __init__(self, parent, initial_date=None, bg=CARD):
        super().__init__(parent, bg=bg)
        self.selected_date = initial_date or date.today()
        self.popup = None
        self.view_year = self.selected_date.year
        self.view_month = self.selected_date.month

        self.entry = ttk.Entry(self, width=12, style="App.TEntry")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.insert(0, self.selected_date.strftime("%d.%m.%Y"))

        self.button = tk.Button(
            self, text="▾", command=self.toggle_popup,
            bg=bg, fg=INK, activebackground=SOFT, activeforeground=INK,
            relief="flat", bd=0, padx=6, pady=1, cursor="hand2",
            font=(FONT, 10), highlightthickness=1, highlightbackground=LINE,
        )
        self.button.pack(side="left", padx=(4, 0))

    def get_date(self):
        text = self.entry.get().strip()
        for fmt in ("%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def set_date(self, value):
        self.selected_date = value
        self.entry.delete(0, tk.END)
        self.entry.insert(0, value.strftime("%d.%m.%Y"))

    def toggle_popup(self):
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()
            self.popup = None
            return
        current = self.get_date() or date.today()
        self.view_year = current.year
        self.view_month = current.month
        self.popup = tk.Toplevel(self)
        self.popup.wm_overrideredirect(True)
        self.popup.attributes("-topmost", True)
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height() + 4
        self.popup.geometry(f"+{x}+{y}")
        self.render_calendar()

    def render_calendar(self):
        for child in self.popup.winfo_children():
            child.destroy()
        shell = tk.Frame(self.popup, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        shell.pack()
        header = tk.Frame(shell, bg=CARD)
        header.pack(fill="x", padx=8, pady=(8, 2))
        tk.Button(
            header, text="‹", command=self.prev_month, bg=CARD, fg=INK,
            relief="flat", bd=0, cursor="hand2", font=(FONT, 12),
        ).pack(side="left")
        tk.Label(
            header, text=f"{MONTHS[self.view_month - 1]} {self.view_year}",
            bg=CARD, fg=INK, font=(FONT, 10, "bold"),
        ).pack(side="left", expand=True)
        tk.Button(
            header, text="›", command=self.next_month, bg=CARD, fg=INK,
            relief="flat", bd=0, cursor="hand2", font=(FONT, 12),
        ).pack(side="right")

        grid = tk.Frame(shell, bg=CARD)
        grid.pack(padx=8, pady=4)
        for column, name in enumerate(["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]):
            tk.Label(grid, text=name, bg=CARD, fg=MUTED, font=(FONT, 8), width=3).grid(row=0, column=column)

        today = date.today()
        selected = self.get_date()
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(self.view_year, self.view_month)
        for row, week in enumerate(weeks, start=1):
            for column, day in enumerate(week):
                in_month = day.month == self.view_month
                if day == selected:
                    bg, fg = INK, "#FFFFFF"
                elif day == today:
                    bg, fg = SOFT, INK
                else:
                    bg, fg = CARD, INK if in_month else "#C4C4C8"
                tk.Button(
                    grid, text=str(day.day), bg=bg, fg=fg, relief="flat", bd=0,
                    width=3, font=(FONT, 9, "bold" if day in (today, selected) else "normal"),
                    command=lambda chosen=day: self.select_day(chosen),
                ).grid(row=row, column=column, padx=1, pady=1)

        tk.Button(
            shell, text="Heute", command=lambda: self.select_day(today),
            bg=CARD, fg=INK, relief="flat", bd=0, cursor="hand2",
            font=(FONT, 9), pady=6,
        ).pack(fill="x")

    def prev_month(self):
        if self.view_month == 1:
            self.view_month = 12
            self.view_year -= 1
        else:
            self.view_month -= 1
        self.render_calendar()

    def next_month(self):
        if self.view_month == 12:
            self.view_month = 1
            self.view_year += 1
        else:
            self.view_month += 1
        self.render_calendar()

    def select_day(self, value):
        self.set_date(value)
        if self.popup:
            self.popup.destroy()
            self.popup = None


class ShiftPlannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Schichtplan")
        self.root.geometry("1320x900")
        self.root.minsize(1180, 760)
        self.root.configure(bg=BG)
        self._configure_style()

        self.employees = []
        self.wishes = []
        self.vacations = []
        self.teammeetings = []
        self.history = empty_history()
        self.next_seq = 1
        self.last_weeks = None
        self.last_plan = None
        self.last_warnings = []

        self.status_var = tk.StringVar(value="Bereit.")
        self._build_ui()
        self._load()

    def _configure_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("App.TEntry", fieldbackground=CARD, bordercolor=LINE, lightcolor=LINE, padding=4)
        style.configure(
            "App.TCombobox",
            fieldbackground=CARD,
            background=CARD,
            bordercolor=LINE,
            lightcolor=LINE,
            arrowcolor=INK,
            padding=4,
        )
        style.map("App.TCombobox", fieldbackground=[("readonly", CARD)])
        style.configure("Card.TCheckbutton", background=CARD, foreground=INK, font=(FONT, 9))

    def _build_ui(self):
        status = tk.Label(
            self.root, textvariable=self.status_var, anchor="w",
            bg="#EFEFF1", fg=MUTED, font=(FONT, 9), padx=18, pady=7,
        )
        status.pack(side="bottom", fill="x")

        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True, padx=22, pady=16)

        tk.Label(outer, text="Schichtplan", bg=BG, fg=INK, font=(FONT, 22)).pack(anchor="w")
        tk.Label(
            outer,
            text="IT-Service Desk  ·  Homeoffice nach Pensum, Ferien und fairer Montag-/Freitag-Rotation",
            bg=BG, fg=MUTED, font=(FONT, 10),
        ).pack(anchor="w", pady=(2, 12))

        period = tk.Frame(outer, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        period.pack(fill="x")
        inner = tk.Frame(period, bg=CARD)
        inner.pack(fill="x", padx=16, pady=12)
        tk.Label(inner, text="Zeitraum", bg=CARD, fg=INK, font=(FONT, 10, "bold")).pack(side="left")
        tk.Label(inner, text="Von", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(16, 6))
        self.dp_start = CalendarDatePicker(inner, date.today())
        self.dp_start.pack(side="left")
        tk.Label(inner, text="Bis", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(14, 6))
        self.dp_end = CalendarDatePicker(inner, date.today() + timedelta(days=27))
        self.dp_end.pack(side="left")
        tk.Label(
            inner, text="Geplant wird Montag bis Freitag.",
            bg=CARD, fg=MUTED, font=(FONT, 9),
        ).pack(side="right")

        cards = tk.Frame(outer, bg=BG)
        cards.pack(fill="x", pady=(12, 0))
        for column in range(4):
            cards.grid_columnconfigure(column, weight=1, uniform="card")

        self._build_employee_card(cards)
        self._build_wish_card(cards)
        self._build_vacation_card(cards)
        self._build_meeting_card(cards)

        actions = tk.Frame(outer, bg=BG)
        actions.pack(fill="x", pady=(14, 0))
        self._button(actions, "Plan generieren", self.generate_plan, "primary").pack(side="left")
        self._button(actions, "PDF exportieren", self.export_pdf, "secondary").pack(side="left", padx=(8, 0))
        self._button(actions, "Eingaben zurücksetzen", self.reset_inputs, "danger").pack(side="left", padx=(8, 0))

        legend = tk.Frame(outer, bg=BG)
        legend.pack(fill="x", pady=(12, 0))
        tk.Label(legend, text="Legende", bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(0, 8))
        for key in COLOR_CONFIG:
            info = COLOR_CONFIG[key]
            tk.Label(
                legend, text=info["legend"], bg=info["bg"], fg=info["fg"],
                font=(FONT, 8), padx=8, pady=3,
            ).pack(side="left", padx=(0, 6))

        self.result = tk.Frame(outer, bg=BG)
        self.result.pack(fill="both", expand=True, pady=(12, 0))
        self._show_empty_state()

    def _button(self, parent, text, command, kind):
        if kind == "primary":
            bg, fg, active = INK, "#FFFFFF", "#3F3F46"
            border = INK
        elif kind == "danger":
            bg, fg, active = CARD, "#B91C1C", "#FEF2F2"
            border = LINE
        else:
            bg, fg, active = CARD, INK, SOFT
            border = LINE
        return tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=fg, activebackground=active, activeforeground=fg,
            relief="flat", bd=0, padx=14, pady=8, cursor="hand2",
            font=(FONT, 10), highlightthickness=1,
            highlightbackground=border, highlightcolor=border,
        )

    def _card(self, parent, column, title, subtitle):
        card = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        tk.Label(card, text=title, bg=CARD, fg=INK, font=(FONT, 11, "bold")).pack(anchor="w", padx=14, pady=(12, 0))
        tk.Label(
            card, text=subtitle, bg=CARD, fg=MUTED, font=(FONT, 8),
            wraplength=250, justify="left",
        ).pack(anchor="w", padx=14, pady=(2, 8))
        body = tk.Frame(card, bg=CARD)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        return body

    def _field(self, parent, text):
        return tk.Label(parent, text=text, bg=CARD, fg=MUTED, font=(FONT, 8))

    def _listbox(self, parent):
        box = tk.Listbox(
            parent, height=4, activestyle="none", exportselection=False,
            bg=CARD, fg=INK, selectbackground=INK, selectforeground="#FFFFFF",
            relief="flat", bd=0, highlightthickness=1, highlightbackground=LINE,
            font=(FONT, 9),
        )
        return box

    def _build_employee_card(self, parent):
        body = self._card(parent, 0, "Mitarbeiter", "Name und Pensum werden auf diesem PC gespeichert.")
        self._field(body, "Name").grid(row=0, column=0, sticky="w")
        self.ent_name = ttk.Entry(body, width=18, style="App.TEntry")
        self.ent_name.grid(row=0, column=1, sticky="ew", pady=2)
        self.ent_name.bind("<Return>", lambda _event: self.add_employee())

        self._field(body, "Pensum").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.cmb_pensum = ttk.Combobox(body, values=PENSUM_VALUES, width=16, state="readonly", style="App.TCombobox")
        self.cmb_pensum.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        self.cmb_pensum.current(0)
        self.cmb_pensum.bind("<<ComboboxSelected>>", lambda _event: self._update_pensum_hint())

        self.pensum_hint = tk.Label(body, text="", bg=CARD, fg=MUTED, font=(FONT, 8), wraplength=250, justify="left")
        self.pensum_hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(3, 0))
        self._update_pensum_hint()

        self._field(body, "Fixer freier Tag").grid(row=3, column=0, sticky="w", pady=(4, 0))
        self.cmb_fixed = ttk.Combobox(
            body, values=["Keiner"] + WEEKDAYS, width=16, state="readonly", style="App.TCombobox",
        )
        self.cmb_fixed.grid(row=3, column=1, sticky="ew", pady=(4, 0))
        self.cmb_fixed.current(0)

        self.var_no_shift = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            body, text="Keine Schichtarbeit", variable=self.var_no_shift, style="Card.TCheckbutton",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        buttons = tk.Frame(body, bg=CARD)
        buttons.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._button(buttons, "Hinzufügen", self.add_employee, "secondary").pack(side="left")
        self._button(buttons, "Entfernen", self.remove_employee, "secondary").pack(side="left", padx=(6, 0))

        self.lst_employees = self._listbox(body)
        self.lst_employees.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        body.grid_columnconfigure(1, weight=1)

    def _build_wish_card(self, parent):
        body = self._card(parent, 1, "Wunschtage", "Frühschicht, Spätschicht oder ein bestimmter Homeoffice-Tag.")
        self._field(body, "Mitarbeiter").grid(row=0, column=0, sticky="w")
        self.cmb_wish_emp = ttk.Combobox(body, state="readonly", width=16, style="App.TCombobox")
        self.cmb_wish_emp.grid(row=0, column=1, sticky="ew", pady=2)
        self._field(body, "Datum").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.dp_wish = CalendarDatePicker(body)
        self.dp_wish.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        self._field(body, "Wunsch").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.cmb_wish = ttk.Combobox(body, values=WISH_TYPES, state="readonly", width=16, style="App.TCombobox")
        self.cmb_wish.grid(row=2, column=1, sticky="ew", pady=(4, 0))
        self.cmb_wish.current(0)
        self._button(body, "Wunsch speichern", self.add_wish, "secondary").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0),
        )
        self.lst_wishes = self._listbox(body)
        self.lst_wishes.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._button(body, "Wunsch entfernen", self.remove_wish, "secondary").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(6, 0),
        )
        body.grid_columnconfigure(1, weight=1)

    def _build_vacation_card(self, parent):
        body = self._card(parent, 2, "Ferien", "Werden pro Woche mit den freien Tagen zusammengezählt.")
        self._field(body, "Mitarbeiter").grid(row=0, column=0, sticky="w")
        self.cmb_vac_emp = ttk.Combobox(body, state="readonly", width=16, style="App.TCombobox")
        self.cmb_vac_emp.grid(row=0, column=1, sticky="ew", pady=2)
        self._field(body, "Von").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.dp_vac_start = CalendarDatePicker(body)
        self.dp_vac_start.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        self._field(body, "Bis").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.dp_vac_end = CalendarDatePicker(body)
        self.dp_vac_end.grid(row=2, column=1, sticky="ew", pady=(4, 0))
        self._button(body, "Ferien speichern", self.add_vacation, "secondary").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0),
        )
        self.lst_vacations = self._listbox(body)
        self.lst_vacations.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._button(body, "Ferien entfernen", self.remove_vacation, "secondary").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(6, 0),
        )
        body.grid_columnconfigure(1, weight=1)

    def _build_meeting_card(self, parent):
        body = self._card(parent, 3, "Teammeeting", "Nur mittwochs. An diesem Tag gibt es kein Homeoffice.")
        self._field(body, "Datum").grid(row=0, column=0, sticky="w")
        self.dp_meeting = CalendarDatePicker(body)
        self.dp_meeting.grid(row=0, column=1, sticky="ew", pady=2)
        self._button(body, "Meeting eintragen", self.add_meeting, "secondary").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 0),
        )
        self.lst_meetings = self._listbox(body)
        self.lst_meetings.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._button(body, "Meeting entfernen", self.remove_meeting, "secondary").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(6, 0),
        )
        body.grid_columnconfigure(1, weight=1)

    def _update_pensum_hint(self):
        hints = {
            "100%": "Zwei Homeoffice-Tage, keine freien Tage.",
            "80%": "Ein Homeoffice-Tag und ein freier Tag.",
            "60%": "Kein Homeoffice, zwei freie Tage.",
            "40%": "Kein Homeoffice, drei freie Tage.",
            "20%": "Kein Homeoffice, vier freie Tage.",
        }
        self.pensum_hint.configure(text=hints.get(self.cmb_pensum.get(), ""))

    def _employee_text(self, emp):
        parts = [emp["name"], f"{emp['pensum']}%"]
        if emp["fixed_off"] is not None:
            parts.append(f"frei {WEEKDAYS[emp['fixed_off']][:2]}")
        if emp["no_shift"]:
            parts.append("Flex")
        return " · ".join(parts)

    def _selected_employee(self, combo):
        name = combo.get().strip()
        for emp in self.employees:
            if emp["name"] == name:
                return emp
        return None

    def _refresh_lists(self):
        self.lst_employees.delete(0, tk.END)
        for emp in self.employees:
            self.lst_employees.insert(tk.END, self._employee_text(emp))

        names = [emp["name"] for emp in self.employees]
        for combo in (self.cmb_wish_emp, self.cmb_vac_emp):
            current = combo.get()
            combo["values"] = names
            if current in names:
                combo.set(current)
            elif names:
                combo.current(0)
            else:
                combo.set("")

        self.lst_wishes.delete(0, tk.END)
        for wish in self.wishes:
            self.lst_wishes.insert(
                tk.END, f"{wish['emp']} · {wish['date'].strftime('%d.%m.%Y')} · {wish['type']}",
            )
        self.lst_vacations.delete(0, tk.END)
        for vacation in self.vacations:
            self.lst_vacations.insert(
                tk.END,
                f"{vacation['emp']} · {vacation['start'].strftime('%d.%m.%Y')} – {vacation['end'].strftime('%d.%m.%Y')}",
            )
        self.lst_meetings.delete(0, tk.END)
        for meeting in self.teammeetings:
            self.lst_meetings.insert(tk.END, meeting.strftime("%d.%m.%Y"))

    def _snapshot(self):
        return {
            "employees": deepcopy(self.employees),
            "wishes": [
                {"emp": w["emp"], "date": w["date"].isoformat(), "type": w["type"]}
                for w in self.wishes
            ],
            "vacations": [
                {"emp": v["emp"], "start": v["start"].isoformat(), "end": v["end"].isoformat()}
                for v in self.vacations
            ],
            "teammeetings": [day.isoformat() for day in self.teammeetings],
            "history": deepcopy(self.history),
            "next_seq": self.next_seq,
        }

    def _persist(self):
        try:
            save_state(self._snapshot())
        except OSError as error:
            self.status_var.set(f"Speichern fehlgeschlagen: {error}")

    def _load(self):
        data = None
        try:
            data = load_state()
        except (OSError, json.JSONDecodeError):
            messagebox.showwarning("Hinweis", "Die gespeicherten Daten waren ungültig. Es wird neu begonnen.", parent=self.root)

        if not data:
            self.employees = [dict(emp) for emp in SAMPLE_EMPLOYEES]
            self._refresh_lists()
            self.status_var.set("Beispieldaten geladen. Eigene Namen ersetzen Anna, Ben, Clara und David.")
            return

        try:
            self.employees = []
            for raw in data.get("employees", []):
                pensum = int(raw.get("pensum", 100))
                fixed_off = raw.get("fixed_off")
                self.employees.append({
                    "name": str(raw.get("name", "")).strip(),
                    "pensum": pensum,
                    "fixed_off": fixed_off if isinstance(fixed_off, int) else None,
                    "no_shift": bool(raw.get("no_shift", False)),
                })
            self.employees = [emp for emp in self.employees if emp["name"]]
            self.wishes = [
                {"emp": w["emp"], "date": parse_stored_date(w["date"]), "type": w["type"]}
                for w in data.get("wishes", [])
                if w.get("emp") and w.get("date") and w.get("type")
            ]
            self.vacations = [
                {
                    "emp": v["emp"],
                    "start": parse_stored_date(v["start"]),
                    "end": parse_stored_date(v["end"]),
                }
                for v in data.get("vacations", [])
                if v.get("emp") and v.get("start") and v.get("end")
            ]
            self.teammeetings = [parse_stored_date(value) for value in data.get("teammeetings", [])]
            self.history = empty_history()
            stored_history = data.get("history") or {}
            for key in FAIR_KEYS:
                self.history[key] = list(stored_history.get(key, []))
            self.next_seq = int(data.get("next_seq", 1))
        except (TypeError, ValueError, KeyError):
            self.employees = [dict(emp) for emp in SAMPLE_EMPLOYEES]
            self.wishes, self.vacations, self.teammeetings = [], [], []
            self.history = empty_history()
            self.next_seq = 1
            self._refresh_lists()
            self.status_var.set("Gespeicherte Daten waren unvollständig. Beispieldaten geladen.")
            return
        self._refresh_lists()
        self.status_var.set("Gespeicherte Mitarbeiter geladen.")

    def _known_absences(self, emp, year, week):
        days = set()
        for day in weekdays_of(year, week):
            if is_vacation(emp["name"], day, self.vacations):
                days.add(day)
            elif emp["fixed_off"] is not None and day.weekday() == emp["fixed_off"]:
                days.add(day)
        return len(days)

    def add_employee(self):
        name = self.ent_name.get().strip()
        if not name:
            messagebox.showwarning("Hinweis", "Bitte einen Namen eingeben.", parent=self.root)
            return
        if any(emp["name"] == name for emp in self.employees):
            messagebox.showwarning("Hinweis", f"{name} ist bereits erfasst.", parent=self.root)
            return
        fixed = self.cmb_fixed.get()
        emp = {
            "name": name,
            "pensum": int(self.cmb_pensum.get().replace("%", "")),
            "fixed_off": WEEKDAYS.index(fixed) if fixed in WEEKDAYS else None,
            "no_shift": self.var_no_shift.get(),
        }
        self.employees.append(emp)
        self.ent_name.delete(0, tk.END)
        self.var_no_shift.set(False)
        self.cmb_fixed.current(0)
        self._refresh_lists()
        self.cmb_wish_emp.set(name)
        self.cmb_vac_emp.set(name)
        self._persist()
        self.status_var.set(f"{name} gespeichert.")

    def remove_employee(self):
        selection = self.lst_employees.curselection()
        if not selection:
            messagebox.showwarning("Hinweis", "Bitte zuerst eine Person in der Liste auswählen.", parent=self.root)
            return
        emp = self.employees[selection[0]]
        if not messagebox.askyesno("Entfernen", f"{emp['name']} wirklich entfernen?", parent=self.root):
            return
        name = emp["name"]
        del self.employees[selection[0]]
        self.wishes = [wish for wish in self.wishes if wish["emp"] != name]
        self.vacations = [vacation for vacation in self.vacations if vacation["emp"] != name]
        self._refresh_lists()
        self._persist()
        self.status_var.set(f"{name} entfernt.")

    def add_wish(self):
        emp = self._selected_employee(self.cmb_wish_emp)
        if emp is None:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Mitarbeiter erfassen und auswählen.", parent=self.root)
            return
        day = self.dp_wish.get_date()
        wish_type = self.cmb_wish.get()
        if day is None:
            messagebox.showerror("Fehler", "Das Datum ist ungültig. Format: TT.MM.JJJJ.", parent=self.root)
            return
        if day.weekday() > 4:
            messagebox.showwarning("Hinweis", "Wunschtage sind nur von Montag bis Freitag möglich.", parent=self.root)
            return

        if wish_type == "Homeoffice":
            if emp["pensum"] <= 60:
                messagebox.showwarning(
                    "Kein Homeoffice",
                    f"{emp['name']} arbeitet {emp['pensum']} %. Ab 60 % gibt es kein Homeoffice.",
                    parent=self.root,
                )
                return
            if day in self.teammeetings:
                messagebox.showwarning(
                    "Teammeeting",
                    f"Am {day.strftime('%d.%m.%Y')} ist Teammeeting. Homeoffice ist an dem Tag nicht möglich.",
                    parent=self.root,
                )
                return
            if is_vacation(emp["name"], day, self.vacations) or (
                emp["fixed_off"] is not None and day.weekday() == emp["fixed_off"]
            ):
                messagebox.showwarning(
                    "Nicht möglich",
                    "An diesem Tag ist bereits Ferien oder ein freier Tag geplant.",
                    parent=self.root,
                )
                return
            year, week, _weekday = day.isocalendar()
            used = sum(
                1 for wish in self.wishes
                if wish["emp"] == emp["name"]
                and wish["type"] == "Homeoffice"
                and wish["date"] != day
                and wish["date"].isocalendar()[:2] == (year, week)
            )
            allowed = ho_cap(emp["pensum"], self._known_absences(emp, year, week))
            if used >= allowed:
                messagebox.showwarning(
                    "Kontingent",
                    f"{emp['name']} kann in dieser Woche höchstens {allowed} Homeoffice-Tag(e) wünschen.",
                    parent=self.root,
                )
                return

        replaced = False
        for wish in self.wishes:
            if wish["emp"] == emp["name"] and wish["date"] == day:
                wish["type"] = wish_type
                replaced = True
                break
        if not replaced:
            self.wishes.append({"emp": emp["name"], "date": day, "type": wish_type})
        self.wishes.sort(key=lambda wish: (wish["date"], wish["emp"]))
        self._refresh_lists()
        self._persist()
        self.status_var.set(
            f"Wunsch für {emp['name']} am {day.strftime('%d.%m.%Y')} {'aktualisiert' if replaced else 'gespeichert'}."
        )

    def remove_wish(self):
        selection = self.lst_wishes.curselection()
        if not selection:
            messagebox.showwarning("Hinweis", "Bitte einen Wunsch in der Liste auswählen.", parent=self.root)
            return
        del self.wishes[selection[0]]
        self._refresh_lists()
        self._persist()
        self.status_var.set("Wunsch entfernt.")

    def add_vacation(self):
        emp = self._selected_employee(self.cmb_vac_emp)
        if emp is None:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Mitarbeiter erfassen und auswählen.", parent=self.root)
            return
        start = self.dp_vac_start.get_date()
        end = self.dp_vac_end.get_date()
        if start is None or end is None or end < start:
            messagebox.showerror("Fehler", "Bitte ein gültiges Von- und Bis-Datum angeben.", parent=self.root)
            return
        entry = {"emp": emp["name"], "start": start, "end": end}
        if entry in self.vacations:
            self.status_var.set("Diese Ferien sind bereits erfasst.")
            return
        self.vacations.append(entry)
        self.vacations.sort(key=lambda item: (item["start"], item["emp"]))
        self._refresh_lists()
        self._persist()
        self.status_var.set(f"Ferien für {emp['name']} gespeichert.")

    def remove_vacation(self):
        selection = self.lst_vacations.curselection()
        if not selection:
            messagebox.showwarning("Hinweis", "Bitte einen Ferieneintrag auswählen.", parent=self.root)
            return
        del self.vacations[selection[0]]
        self._refresh_lists()
        self._persist()
        self.status_var.set("Ferien entfernt.")

    def add_meeting(self):
        day = self.dp_meeting.get_date()
        if day is None:
            messagebox.showerror("Fehler", "Das Datum ist ungültig.", parent=self.root)
            return
        if day.weekday() != 2:
            messagebox.showwarning("Hinweis", "Teammeetings sind nur am Mittwoch möglich.", parent=self.root)
            return
        if day in self.teammeetings:
            self.status_var.set("Dieses Meeting ist bereits eingetragen.")
            return
        self.teammeetings.append(day)
        self.teammeetings.sort()
        self._refresh_lists()
        self._persist()
        self.status_var.set(f"Teammeeting am {day.strftime('%d.%m.%Y')} eingetragen.")

    def remove_meeting(self):
        selection = self.lst_meetings.curselection()
        if not selection:
            messagebox.showwarning("Hinweis", "Bitte ein Meeting auswählen.", parent=self.root)
            return
        del self.teammeetings[selection[0]]
        self._refresh_lists()
        self._persist()
        self.status_var.set("Meeting entfernt.")

    def reset_inputs(self):
        if not messagebox.askyesno(
            "Zurücksetzen",
            "Wunschtage, Ferien und Meetings löschen? Mitarbeiter bleiben gespeichert.",
            parent=self.root,
        ):
            return
        self.wishes.clear()
        self.vacations.clear()
        self.teammeetings.clear()
        self.last_plan = None
        self.last_weeks = None
        self._refresh_lists()
        self._show_empty_state()
        self._persist()
        self.status_var.set("Wunschtage, Ferien und Meetings gelöscht.")

    def generate_plan(self):
        if not self.employees:
            messagebox.showwarning("Hinweis", "Bitte mindestens eine Person erfassen.", parent=self.root)
            return
        start = self.dp_start.get_date()
        end = self.dp_end.get_date()
        if start is None or end is None:
            messagebox.showerror("Fehler", "Bitte gültige Daten im Format TT.MM.JJJJ angeben.", parent=self.root)
            return
        result = generate_schedule(
            self.employees,
            self.wishes,
            self.vacations,
            self.teammeetings,
            start,
            end,
            history=self.history,
            next_seq=self.next_seq,
        )
        if result.get("error"):
            messagebox.showerror("Fehler", result["error"], parent=self.root)
            return

        self.history = result["history"]
        self.next_seq = result["next_seq"]
        self.last_plan = result["plan"]
        self.last_weeks = result["weeks"]
        self.last_warnings = result["warnings"]
        self._persist()
        self.render_matrix(result["weeks"], result["plan"], result["warnings"])

        notes = result["warnings"] + result["unfulfilled"]
        week_count = len(result["weeks"])
        if notes:
            self.status_var.set(f"Plan für {week_count} Woche(n) erzeugt. {len(notes)} Hinweis(e).")
            messagebox.showwarning("Hinweise zum Plan", "\n".join(notes), parent=self.root)
        else:
            self.status_var.set(f"Plan für {week_count} Woche(n) erzeugt.")

    def _show_empty_state(self):
        for child in self.result.winfo_children():
            child.destroy()
        tk.Label(
            self.result,
            text="Noch kein Plan.\nZeitraum prüfen und «Plan generieren» wählen.",
            bg=BG, fg=MUTED, font=(FONT, 11), justify="left",
        ).pack(anchor="w", pady=12)

    def render_matrix(self, weeks, plan, warnings):
        for child in self.result.winfo_children():
            child.destroy()

        warned = set()
        for line in warnings:
            try:
                warned.add(datetime.strptime(line[:10], "%d.%m.%Y").date())
            except ValueError:
                pass

        canvas = tk.Canvas(self.result, bg=BG, highlightthickness=0)
        scroll_y = ttk.Scrollbar(self.result, orient="vertical", command=canvas.yview)
        scroll_x = ttk.Scrollbar(self.result, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_x.pack(side="bottom", fill="x")
        scroll_y.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        holder = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=holder, anchor="nw")

        def sync_scroll(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            target = max(canvas.winfo_width(), holder.winfo_reqwidth())
            current = canvas.itemcget(window, "width")
            if str(current) != str(target):
                canvas.itemconfigure(window, width=target)

        holder.bind("<Configure>", sync_scroll)
        canvas.bind("<Configure>", sync_scroll)

        def on_wheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")

        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", on_wheel))
        canvas.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))

        short_names = ["Mo", "Di", "Mi", "Do", "Fr"]
        for (year, week), days in weeks:
            block = tk.Frame(holder, bg=CARD, highlightthickness=1, highlightbackground=LINE)
            block.pack(fill="x", pady=(0, 12))
            title = f"Woche {week}   ·   {days[0].strftime('%d.%m.%Y')} – {days[-1].strftime('%d.%m.%Y')}"
            tk.Label(block, text=title, bg=CARD, fg=INK, font=(FONT, 11, "bold")).pack(anchor="w", padx=12, pady=(10, 8))

            grid = tk.Frame(block, bg=CARD)
            grid.pack(fill="x", padx=12, pady=(0, 12))
            tk.Label(
                grid, text="Mitarbeiter", bg=SOFT, fg=MUTED, font=(FONT, 8),
                anchor="w", padx=10, pady=8, width=22,
            ).grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

            for column, day in enumerate(days, start=1):
                header_bg = "#FDECEC" if day in warned else ("#EEF2FF" if day in self.teammeetings else SOFT)
                header = f"{short_names[day.weekday()]}\n{day.strftime('%d.%m.')}"
                if day in self.teammeetings:
                    header += "\nMeeting"
                tk.Label(
                    grid, text=header, bg=header_bg, fg=INK, font=(FONT, 8),
                    width=14, pady=4, justify="center",
                ).grid(row=0, column=column, sticky="nsew", padx=1, pady=1)

            for row, emp in enumerate(self.employees, start=1):
                tk.Label(
                    grid, text=self._employee_text(emp), bg="#FAFAFB", fg=INK,
                    font=(FONT, 9), anchor="w", padx=10, pady=8,
                ).grid(row=row, column=0, sticky="nsew", padx=1, pady=1)
                for column, day in enumerate(days, start=1):
                    value = plan[emp["name"]].get(day, "–")
                    info = COLOR_CONFIG.get(value, {"bg": CARD, "fg": MUTED, "short": value})
                    tk.Label(
                        grid, text=info["short"], bg=info["bg"], fg=info["fg"],
                        font=(FONT, 9), width=14, pady=8,
                    ).grid(row=row, column=column, sticky="nsew", padx=1, pady=1)

    def export_pdf(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror(
                "Modul fehlt",
                "Für den PDF-Export fehlt die Bibliothek reportlab.\n\n"
                "Im Terminal:\n"
                f'"{sys.executable}" -m pip install reportlab',
                parent=self.root,
            )
            return
        if not self.last_plan or not self.last_weeks:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Plan generieren.", parent=self.root)
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            title="Schichtplan speichern",
            parent=self.root,
        )
        if not file_path:
            return
        try:
            self._write_pdf(file_path)
        except Exception as error:
            messagebox.showerror("PDF", f"Export fehlgeschlagen:\n{error}", parent=self.root)
            return
        self.status_var.set(f"PDF gespeichert: {file_path}")
        messagebox.showinfo("PDF", f"Gespeichert unter\n{file_path}", parent=self.root)

    def _write_pdf(self, file_path):
        doc = SimpleDocTemplate(
            file_path, pagesize=landscape(A4),
            rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=28,
        )
        styles = getSampleStyleSheet()
        title = ParagraphStyle("TitleDe", parent=styles["Heading1"], fontName="Helvetica", fontSize=18, textColor=colors.HexColor(INK), spaceAfter=4)
        sub = ParagraphStyle("SubDe", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=colors.HexColor(MUTED), spaceAfter=12)
        week_style = ParagraphStyle("WeekDe", parent=styles["Heading2"], fontName="Helvetica", fontSize=12, textColor=colors.HexColor(INK), spaceBefore=8, spaceAfter=6)
        cell = ParagraphStyle("CellDe", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, alignment=1)
        header = ParagraphStyle("HeadDe", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, alignment=1)
        elements = [
            Paragraph("Schichtplan IT-Service Desk", title),
            Paragraph(" · ".join(info["legend"] for info in COLOR_CONFIG.values()), sub),
        ]
        short_names = ["Mo", "Di", "Mi", "Do", "Fr"]
        for (_year, week), days in self.last_weeks:
            elements.append(Paragraph(
                f"Woche {week} · {days[0].strftime('%d.%m.%Y')} – {days[-1].strftime('%d.%m.%Y')}",
                week_style,
            ))
            data = [[Paragraph("Mitarbeiter", header)]]
            for day in days:
                label = f"{short_names[day.weekday()]}<br/>{day.strftime('%d.%m.')}"
                if day in self.teammeetings:
                    label += "<br/>Meeting"
                data[0].append(Paragraph(label, header))
            style_commands = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(SOFT)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(LINE)),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
            for row, emp in enumerate(self.employees, start=1):
                line = [Paragraph(self._employee_text(emp), cell)]
                for column, day in enumerate(days, start=1):
                    value = self.last_plan[emp["name"]].get(day, "–")
                    info = COLOR_CONFIG.get(value, {"bg": "#FFFFFF", "short": value})
                    line.append(Paragraph(info["short"], cell))
                    style_commands.append(("BACKGROUND", (column, row), (column, row), colors.HexColor(info["bg"])))
                data.append(line)
            table = Table(data, colWidths=[130] + [78] * len(days))
            table.setStyle(TableStyle(style_commands))
            elements.append(table)
            elements.append(Spacer(1, 8))
        doc.build(elements)


def _count(plan, name, days, value):
    return sum(1 for day in days if plan[name].get(day) == value)


def _assert_rotation(sequence, everyone):
    seen = set()
    for name in sequence:
        if everyone <= seen:
            seen = set()
        if name in seen:
            raise AssertionError(f"{name} kommt erneut, bevor alle dran waren: {sequence}")
        seen.add(name)


def run_self_check():
    """Prüft die Planungsregeln ohne das Fenster zu öffnen."""
    start = date(2026, 11, 2)
    if start.weekday() != 0:
        raise AssertionError("Testdatum ist kein Montag.")
    week = [start + timedelta(days=i) for i in range(5)]

    def person(name, pensum=100, fixed_off=None, no_shift=False):
        return {"name": name, "pensum": pensum, "fixed_off": fixed_off, "no_shift": no_shift}

    def run(employees, **kwargs):
        return generate_schedule(
            employees,
            kwargs.get("wishes", []),
            kwargs.get("vacations", []),
            kwargs.get("meetings", []),
            kwargs.get("start", start),
            kwargs.get("end", week[-1]),
            history=kwargs.get("history"),
            next_seq=kwargs.get("next_seq", 1),
            rng=random.Random(kwargs.get("seed", 1)),
        )

    filler = person("Filler")

    for pensum, ho, free in ((100, 2, 0), (80, 1, 1), (60, 0, 2), (40, 0, 3), (20, 0, 4)):
        result = run([person("A", pensum), filler])
        assert _count(result["plan"], "A", week, "Homeoffice") == ho, pensum
        assert _count(result["plan"], "A", week, "Teilzeit (Frei)") == free, pensum

    result = run(
        [person("A"), filler],
        vacations=[{"emp": "A", "start": start, "end": start}],
    )
    assert _count(result["plan"], "A", week, "Homeoffice") == 1
    assert result["plan"]["A"][start] == "Ferien"

    result = run(
        [person("A"), filler],
        vacations=[{"emp": "A", "start": start, "end": start + timedelta(days=1)}],
    )
    assert _count(result["plan"], "A", week, "Homeoffice") == 0

    result = run([person("A", fixed_off=2), filler])
    assert result["plan"]["A"][start + timedelta(days=2)] == "Teilzeit (Frei)"
    assert _count(result["plan"], "A", week, "Homeoffice") == 1

    result = run(
        [person("A"), filler],
        wishes=[{"emp": "A", "date": start + timedelta(days=1), "type": "Homeoffice"}],
    )
    assert result["plan"]["A"][start + timedelta(days=1)] == "Homeoffice"
    assert _count(result["plan"], "A", week, "Homeoffice") <= 2

    wednesday = start + timedelta(days=2)
    result = run([person("A"), person("B")], meetings=[wednesday])
    assert result["plan"]["A"].get(wednesday) != "Homeoffice"
    assert result["plan"]["B"].get(wednesday) != "Homeoffice"

    result = run(
        [person("A"), filler],
        wishes=[{"emp": "A", "date": wednesday, "type": "Homeoffice"}],
        meetings=[wednesday],
    )
    assert result["plan"]["A"].get(wednesday) != "Homeoffice"
    assert result["unfulfilled"]

    team = [person("A"), person("B"), person("C")]
    horizon = start + timedelta(days=7 * 8 - 3)
    for seed in range(8):
        result = run(team, end=horizon, seed=seed)
        fridays = []
        cursor = start
        while cursor <= horizon:
            if cursor.weekday() == 4:
                fridays.append(cursor)
            cursor += timedelta(days=1)
        friday_names = []
        monday_names = []
        for day in fridays:
            ho = [emp["name"] for emp in team if result["plan"][emp["name"]].get(day) == "Homeoffice"]
            assert len(ho) == 1, (seed, day, ho)
            friday_names.append(ho[0])
            on_site = [
                emp["name"] for emp in team
                if result["plan"][emp["name"]].get(day) not in ABSENT
            ]
            early = [name for name in on_site if result["plan"][name].get(day) == "Frühschicht"]
            late = [name for name in on_site if result["plan"][name].get(day) == "Spätschicht"]
            assert early and late
        cursor = start
        while cursor <= horizon:
            if cursor.weekday() == 0:
                ho = [emp["name"] for emp in team if result["plan"][emp["name"]].get(cursor) == "Homeoffice"]
                assert len(ho) == 1, (seed, cursor, ho)
                monday_names.append(ho[0])
            cursor += timedelta(days=1)
        _assert_rotation(friday_names, {"A", "B", "C"})
        _assert_rotation(monday_names, {"A", "B", "C"})
        assert set(friday_names) == {"A", "B", "C"}
        assert set(monday_names) == {"A", "B", "C"}

    vacations = []
    for offset in range(6):
        monday = start + timedelta(days=7 * offset)
        for name in ("A", "B", "C"):
            vacations.append({"emp": name, "start": monday, "end": monday + timedelta(days=1)})
    shift_end = start + timedelta(days=7 * 6 - 3)
    result = run(team, vacations=vacations, end=shift_end, seed=3)
    for key in ("ho_monday", "ho_friday"):
        assert result["history"][key] == []
    for key, everyone in (("frueh_friday", {"A", "B", "C"}), ("spaet_friday", {"A", "B", "C"})):
        sequence = [item["name"] for item in result["history"][key]]
        _assert_rotation(sequence, everyone)
        assert set(sequence) == everyone

    first = run(team, end=week[-1], seed=2)
    second = run(
        team,
        start=start + timedelta(days=7),
        end=start + timedelta(days=11),
        history=first["history"],
        next_seq=first["next_seq"],
        seed=2,
    )
    combined = [item["name"] for item in first["history"]["ho_friday"]]
    combined += [item["name"] for item in second["history"]["ho_friday"] if item["date"] > week[-1].isoformat()]
    _assert_rotation(combined, {"A", "B", "C"})

    again = run(team, end=horizon, history=result["history"], next_seq=result["next_seq"], seed=5)
    friday_events = [
        item for item in again["history"]["ho_friday"]
        if start.isoformat() <= item["date"] <= horizon.isoformat()
    ]
    assert len(friday_events) == 8

    print("Regeln geprüft.")
    print("Homeoffice nach Pensum, Ferien und freien Tagen: ok")
    print("Wunschtage und Teammeeting: ok")
    print("Rotation für Montag, Freitag, Früh- und Spätschicht: ok")


def main():
    root = tk.Tk()
    ShiftPlannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    if "--check" in sys.argv:
        run_self_check()
    else:
        main()
