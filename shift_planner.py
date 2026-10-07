import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta, date
import calendar
from collections import defaultdict
import random

# PDF Export via ReportLab
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# --- FARBLEGENDE (Pastelltöne) ---
COLOR_CONFIG = {
    "Frühschicht":     {"bg": "#D4EDDA", "fg": "#155724", "desc": "Frühschicht (07:30 - 16:30)"},
    "Spätschicht":     {"bg": "#A8E6CF", "fg": "#0B5345", "desc": "Spätschicht (08:30 - 17:30)"},
    "Homeoffice":      {"bg": "#D0E8FF", "fg": "#0C5460", "desc": "Homeoffice"},
    "Teilzeit (Frei)": {"bg": "#E2E3E5", "fg": "#383D41", "desc": "Teilzeit / Freier Tag"},
    "Ferien":          {"bg": "#E2E3E5", "fg": "#383D41", "desc": "Ferien"},
    "Unterbesetzt":    {"bg": "#F8D7DA", "fg": "#721C24", "desc": "Fehlende Besetzung!"}
}

WEEKDAYS_LIST = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]


class CalendarDatePicker(ttk.Frame):
    """Dropdown-Minikalender Widget mit roter Hervorhebung für das heutige Datum"""
    def __init__(self, parent, initial_date=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.selected_date = initial_date or date.today()

        self.entry = ttk.Entry(self, width=12)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.insert(0, self.selected_date.strftime("%d/%m/%Y"))

        self.btn = ttk.Button(self, text="📅", width=3, command=self.toggle_popup)
        self.btn.pack(side="left", padx=(2, 0))

        self.popup = None

    def get_date(self):
        txt = self.entry.get().strip()
        try:
            return datetime.strptime(txt, "%d/%m/%Y").date()
        except ValueError:
            return None

    def set_date(self, dt):
        self.selected_date = dt
        self.entry.delete(0, tk.END)
        self.entry.insert(0, dt.strftime("%d/%m/%Y"))

    def toggle_popup(self):
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()
            self.popup = None
            return

        current_dt = self.get_date() or date.today()
        self.view_year = current_dt.year
        self.view_month = current_dt.month

        self.popup = tk.Toplevel(self)
        self.popup.wm_overrideredirect(True)
        self.popup.attributes("-topmost", True)

        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height() + 2
        self.popup.geometry(f"+{x}+{y}")

        self.render_calendar()

    def render_calendar(self):
        for w in self.popup.winfo_children():
            w.destroy()

        outer_frame = tk.Frame(self.popup, bg="#707070", bd=1)
        outer_frame.pack(fill="both", expand=True)

        inner_frame = tk.Frame(outer_frame, bg="#FFFFFF", bd=2)
        inner_frame.pack(fill="both", expand=True)

        # Header mit Monatsnavigation
        hdr = tk.Frame(inner_frame, bg="#EFEFEF")
        hdr.pack(fill="x")

        btn_prev = tk.Button(hdr, text="◄", bd=0, bg="#EFEFEF", activebackground="#DDD", command=self.prev_month)
        btn_prev.pack(side="left", padx=5, pady=3)

        month_name = calendar.month_name[self.view_month]
        lbl_title = tk.Label(hdr, text=f"{month_name} {self.view_year}", bg="#EFEFEF", font=("Arial", 9, "bold"))
        lbl_title.pack(side="left", expand=True)

        btn_next = tk.Button(hdr, text="►", bd=0, bg="#EFEFEF", activebackground="#DDD", command=self.next_month)
        btn_next.pack(side="right", padx=5, pady=3)

        # Wochentage Header
        grid_frame = tk.Frame(inner_frame, bg="#FFFFFF")
        grid_frame.pack(padx=5, pady=3)

        days_hdr = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        for col, dname in enumerate(days_hdr):
            tk.Label(grid_frame, text=dname, bg="#FFFFFF", fg="#777777", font=("Arial", 8, "bold"), width=3).grid(row=0, column=col)

        # Tage-Raster
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdatescalendar(self.view_year, self.view_month)
        today = date.today()

        for row_idx, week in enumerate(month_days, start=1):
            for col_idx, day_dt in enumerate(week):
                is_curr_month = (day_dt.month == self.view_month)
                is_today = (day_dt == today)
                is_selected = (day_dt == self.get_date())

                if is_today:
                    fg_color = "#D9534F"
                    font_style = ("Arial", 8, "bold")
                elif is_curr_month:
                    fg_color = "#000000"
                    font_style = ("Arial", 8)
                else:
                    fg_color = "#B0B0B0"
                    font_style = ("Arial", 8)

                if is_selected:
                    bg_color = "#D0E8FF"
                elif is_today:
                    bg_color = "#FFE6E6"
                else:
                    bg_color = "#FFFFFF"

                btn_day = tk.Button(
                    grid_frame,
                    text=str(day_dt.day),
                    bg=bg_color,
                    fg=fg_color,
                    bd=1,
                    relief="solid" if is_today else "flat",
                    width=3,
                    font=font_style,
                    command=lambda d=day_dt: self.select_day(d)
                )
                btn_day.grid(row=row_idx, column=col_idx, padx=1, pady=1)

        btn_today = tk.Button(
            inner_frame,
            text=f"Heute: {today.strftime('%d.%m.%Y')}",
            bg="#FFE6E6",
            fg="#D9534F",
            bd=0,
            font=("Arial", 8, "bold", "underline"),
            command=lambda: self.select_day(today)
        )
        btn_today.pack(fill="x", pady=(2, 2))

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

    def select_day(self, dt):
        self.set_date(dt)
        if self.popup:
            self.popup.destroy()
            self.popup = None


class ShiftPlannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Arbeitsplan Generator mit fairem Mo/Fr HO-Turnus")
        self.root.geometry("1280x860")

        self.employees = []   # List of dicts: {'name': str, 'pensum': int, 'fixed_off': int or None}
        self.wishes = []      # {'emp': str, 'date': date, 'type': str}
        self.vacations = []   # {'emp': str, 'start': date, 'end': date}

        self.last_weeks_dict = None
        self.last_plan = None

        self._build_ui()

    def _build_ui(self):
        # Steuerung Frame
        control_frame = ttk.LabelFrame(self.root, text="Konfiguration & Erfassung", padding=10)
        control_frame.pack(fill="x", padx=10, pady=5)

        # 1. Zeitraum
        ttk.Label(control_frame, text="Startdatum:").grid(row=0, column=0, sticky="w", padx=5)
        self.dp_start = CalendarDatePicker(control_frame, date.today())
        self.dp_start.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(control_frame, text="Enddatum:").grid(row=0, column=2, sticky="w", padx=5)
        self.dp_end = CalendarDatePicker(control_frame, date.today() + timedelta(days=18))
        self.dp_end.grid(row=0, column=3, padx=5, pady=2, sticky="w")

        # 2. Mitarbeiter
        emp_frame = ttk.LabelFrame(control_frame, text="1. Mitarbeiter & Pensum", padding=5)
        emp_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        ttk.Label(emp_frame, text="Name:").grid(row=0, column=0, sticky="w")
        self.ent_emp_name = ttk.Entry(emp_frame, width=15)
        self.ent_emp_name.grid(row=0, column=1, padx=2, pady=2, sticky="w")

        ttk.Label(emp_frame, text="Pensum:").grid(row=1, column=0, sticky="w")
        self.cmb_pensum = ttk.Combobox(emp_frame, values=["100%", "80%", "60%"], width=13, state="readonly")
        self.cmb_pensum.grid(row=1, column=1, padx=2, pady=2, sticky="w")
        self.cmb_pensum.current(0)

        ttk.Label(emp_frame, text="Fixer freier Tag:").grid(row=2, column=0, sticky="w")
        self.cmb_fixed_off = ttk.Combobox(emp_frame, values=["Keiner"] + WEEKDAYS_LIST, width=13, state="readonly")
        self.cmb_fixed_off.grid(row=2, column=1, padx=2, pady=2, sticky="w")
        self.cmb_fixed_off.current(0)

        emp_btn_subframe = tk.Frame(emp_frame)
        emp_btn_subframe.grid(row=3, column=0, columnspan=2, pady=4, sticky="w")

        btn_add_emp = ttk.Button(emp_btn_subframe, text="+ Hinzufügen", command=self.add_employee)
        btn_add_emp.pack(side="left", padx=(0, 2))

        btn_rem_emp = ttk.Button(emp_btn_subframe, text="- Entfernen", command=self.remove_employee)
        btn_rem_emp.pack(side="left")

        self.lst_employees = tk.Listbox(emp_frame, height=4, width=28)
        self.lst_employees.grid(row=4, column=0, columnspan=2, pady=2, sticky="nsew")

        # 3. Wünsche
        wish_frame = ttk.LabelFrame(control_frame, text="2. Wunschtage", padding=5)
        wish_frame.grid(row=1, column=2, columnspan=2, sticky="nsew", padx=5, pady=5)

        ttk.Label(wish_frame, text="Datum:").grid(row=0, column=0, sticky="w")
        self.dp_wish_date = CalendarDatePicker(wish_frame)
        self.dp_wish_date.grid(row=0, column=1, padx=2, pady=2, sticky="w")

        ttk.Label(wish_frame, text="Schicht/HO:").grid(row=1, column=0, sticky="w")
        self.cmb_wish_type = ttk.Combobox(
            wish_frame, 
            values=["Frühschicht", "Spätschicht", "Homeoffice"], 
            width=18, 
            state="readonly"
        )
        self.cmb_wish_type.grid(row=1, column=1, padx=2, pady=2, sticky="w")
        self.cmb_wish_type.current(0)

        btn_add_wish = ttk.Button(wish_frame, text="Wunsch speichern", command=self.add_wish)
        btn_add_wish.grid(row=2, column=0, columnspan=2, pady=6)

        # 4. Ferien
        vac_frame = ttk.LabelFrame(control_frame, text="3. Ferien", padding=5)
        vac_frame.grid(row=1, column=4, columnspan=2, sticky="nsew", padx=5, pady=5)

        ttk.Label(vac_frame, text="Von:").grid(row=0, column=0, sticky="w")
        self.dp_vac_start = CalendarDatePicker(vac_frame)
        self.dp_vac_start.grid(row=0, column=1, padx=2, pady=2, sticky="w")

        ttk.Label(vac_frame, text="Bis:").grid(row=1, column=0, sticky="w")
        self.dp_vac_end = CalendarDatePicker(vac_frame)
        self.dp_vac_end.grid(row=1, column=1, padx=2, pady=2, sticky="w")

        btn_add_vac = ttk.Button(vac_frame, text="Ferien speichern", command=self.add_vacation)
        btn_add_vac.grid(row=2, column=0, columnspan=2, pady=6)

        # Aktions-Buttons
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=5)

        btn_generate = tk.Button(
            btn_frame, 
            text="Arbeitsplan Generieren", 
            bg="#2b5c8f", 
            fg="white", 
            font=("Arial", 10, "bold"), 
            command=self.generate_plan
        )
        btn_generate.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_pdf = tk.Button(
            btn_frame, 
            text="Export to PDF", 
            bg="#27AE60", 
            fg="white", 
            font=("Arial", 10, "bold"), 
            command=self.export_pdf
        )
        btn_pdf.pack(side="left", padx=5)

        btn_reset = tk.Button(
            btn_frame, 
            text="Alles Zurücksetzen", 
            bg="#C0392B", 
            fg="white", 
            font=("Arial", 10, "bold"), 
            command=self.reset_all
        )
        btn_reset.pack(side="right", padx=(5, 0))

        # Farblegende
        legend_frame = tk.Frame(self.root)
        legend_frame.pack(fill="x", padx=10, pady=2)
        tk.Label(legend_frame, text="Legende: ", font=("Arial", 9, "bold")).pack(side="left")

        for key, info in COLOR_CONFIG.items():
            lbl = tk.Label(
                legend_frame, 
                text=f" {key} ", 
                bg=info["bg"], 
                fg=info["fg"], 
                font=("Arial", 8, "bold"),
                bd=1,
                relief="solid"
            )
            lbl.pack(side="left", padx=4)

        # Ergebnismatrix Container
        self.result_container = ttk.LabelFrame(self.root, text="Arbeitsplan Matrix (Wochenübersicht)", padding=5)
        self.result_container.pack(fill="both", expand=True, padx=10, pady=5)

        # Beispieldaten
        sample_data = [
            {'name': 'Anna',  'pensum': 100, 'fixed_off': None},
            {'name': 'Ben',   'pensum': 80,  'fixed_off': 2},    # Fixer Mittwoch
            {'name': 'Clara', 'pensum': 80,  'fixed_off': None}, # 80% (Zufälliger freier Tag)
            {'name': 'David', 'pensum': 100, 'fixed_off': None}
        ]
        for emp in sample_data:
            self._insert_employee_object(emp)

    def _insert_employee_object(self, emp_obj):
        self.employees.append(emp_obj)
        off_str = f" - Frei: {WEEKDAYS_LIST[emp_obj['fixed_off']][:2]}" if emp_obj['fixed_off'] is not None else ""
        disp = f"{emp_obj['name']} ({emp_obj['pensum']}%{off_str})"
        self.lst_employees.insert(tk.END, disp)

    def add_employee(self):
        name = self.ent_emp_name.get().strip()
        if not name:
            messagebox.showwarning("Hinweis", "Bitte einen Namen eingeben.")
            return

        if any(e['name'] == name for e in self.employees):
            messagebox.showwarning("Hinweis", f"Mitarbeiter '{name}' existiert bereits.")
            return

        pensum_val = int(self.cmb_pensum.get().replace("%", ""))
        fixed_off_str = self.cmb_fixed_off.get()

        fixed_off_idx = WEEKDAYS_LIST.index(fixed_off_str) if fixed_off_str in WEEKDAYS_LIST else None

        emp_obj = {
            'name': name,
            'pensum': pensum_val,
            'fixed_off': fixed_off_idx
        }
        self._insert_employee_object(emp_obj)
        self.ent_emp_name.delete(0, tk.END)

    def remove_employee(self):
        sel = self.lst_employees.curselection()
        if not sel:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Mitarbeiter in der Liste auswählen.")
            return

        idx = sel[0]
        emp_name = self.employees[idx]['name']

        if messagebox.askyesno("Mitarbeiter Entfernen", f"Möchtest du '{emp_name}' wirklich entfernen?"):
            del self.employees[idx]
            self.lst_employees.delete(idx)
            self.wishes = [w for w in self.wishes if w['emp'] != emp_name]
            self.vacations = [v for v in self.vacations if v['emp'] != emp_name]
            messagebox.showinfo("Entfernt", f"Mitarbeiter '{emp_name}' wurde gelöscht.")

    def add_wish(self):
        sel = self.lst_employees.curselection()
        if not sel:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Mitarbeiter in der Liste auswählen.")
            return

        emp_name = self.employees[sel[0]]['name']
        dt = self.dp_wish_date.get_date()
        wish_type = self.cmb_wish_type.get()

        if not dt:
            messagebox.showerror("Fehler", "Ungültiges Datum.")
            return

        if wish_type == "Homeoffice":
            year, week_num, _ = dt.isocalendar()
            ho_count_in_week = sum(
                1 for w in self.wishes 
                if w['emp'] == emp_name and w['type'] == "Homeoffice" and w['date'].isocalendar()[:2] == (year, week_num)
            )

            if ho_count_in_week >= 2:
                messagebox.showwarning(
                    "Regelung nicht erfüllt", 
                    f"Nicht möglich!\n\nFür {emp_name} wurden in KW {week_num} bereits {ho_count_in_week} Homeoffice-Wunschtage erfasst."
                )
                return

        self.wishes.append({'emp': emp_name, 'date': dt, 'type': wish_type})
        messagebox.showinfo("Gespeichert", f"Wunsch für {emp_name} am {dt.strftime('%d/%m/%Y')} ({wish_type}) hinterlegt.")

    def add_vacation(self):
        sel = self.lst_employees.curselection()
        if not sel:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Mitarbeiter auswählen.")
            return

        emp_name = self.employees[sel[0]]['name']
        s_dt = self.dp_vac_start.get_date()
        e_dt = self.dp_vac_end.get_date()

        if not s_dt or not e_dt or e_dt < s_dt:
            messagebox.showerror("Fehler", "Gültiges Von- und Bis-Datum angeben.")
            return

        self.vacations.append({'emp': emp_name, 'start': s_dt, 'end': e_dt})
        messagebox.showinfo("Gespeichert", f"Ferien für {emp_name} vom {s_dt.strftime('%d/%m/%Y')} bis {e_dt.strftime('%d/%m/%Y')} erfasst.")

    def reset_all(self):
        if messagebox.askyesno("Zurücksetzen", "Möchtest du wirklich alle eingegebenen Wunschtage und Ferien zurücksetzen?"):
            self.wishes.clear()
            self.vacations.clear()
            self.last_weeks_dict = None
            self.last_plan = None
            for widget in self.result_container.winfo_children():
                widget.destroy()
            messagebox.showinfo("Zurückgesetzt", "Alle Wunschtage und Ferien wurden erfolgreich gelöscht.")

    def is_in_vacation(self, emp_name, d):
        return any(v['start'] <= d <= v['end'] for v in self.vacations if v['emp'] == emp_name)

    def generate_plan(self):
        if not self.employees:
            messagebox.showwarning("Achtung", "Bitte mindestens einen Mitarbeiter erfassen.")
            return

        start_date = self.dp_start.get_date()
        end_date = self.dp_end.get_date()

        if not start_date or not end_date or end_date < start_date:
            messagebox.showerror("Fehler", "Gültigen Zeitraum wählen.")
            return

        # 1. Arbeitstage ermitteln (Mo-Fr)
        work_days = []
        curr = start_date
        while curr <= end_date:
            if curr.weekday() < 5:
                work_days.append(curr)
            curr += timedelta(days=1)

        if not work_days:
            messagebox.showinfo("Info", "Keine Arbeitstage (Mo-Fr) im gewählten Zeitraum.")
            return

        weeks_dict = defaultdict(list)
        for day in work_days:
            year, week_num, _ = day.isocalendar()
            weeks_dict[(year, week_num)].append(day)

        # Pre- / Post-Ferien Tage ermitteln
        pre_vac_days = set()
        post_vac_days = set()
        for emp in self.employees:
            e_name = emp['name']
            for idx, day in enumerate(work_days):
                if not self.is_in_vacation(e_name, day):
                    if idx > 0 and self.is_in_vacation(e_name, work_days[idx - 1]):
                        post_vac_days.add((e_name, day))
                    if idx < len(work_days) - 1 and self.is_in_vacation(e_name, work_days[idx + 1]):
                        pre_vac_days.add((e_name, day))

        plan = {emp['name']: {} for emp in self.employees}
        unstaffed_warnings = []
        shift_counts = {emp['name']: {"Frühschicht": 0, "Spätschicht": 0} for emp in self.employees}

        # Zähler für fair gewichteten Turnus bei Freitag & Montag Homeoffice
        monday_ho_counts = defaultdict(int)
        friday_ho_counts = defaultdict(int)

        # 2. Chronologische wochenweise Berechnung
        for (year, week_num), week_days in sorted(weeks_dict.items()):
            
            # Wöchentliches HO-Limit festlegen (Pensum berücksichtigen)
            weekly_ho_max = {}
            for emp in self.employees:
                e_name = emp['name']
                base_ho_max = 2 if emp['pensum'] == 100 else 1

                for day in week_days:
                    if (e_name, day) in pre_vac_days or (e_name, day) in post_vac_days:
                        base_ho_max = 1

                weekly_ho_max[e_name] = base_ho_max

            ho_weekly_count = defaultdict(int)

            # A. Ferien eintragen
            for day in week_days:
                for emp in self.employees:
                    e_name = emp['name']
                    if self.is_in_vacation(e_name, day):
                        plan[e_name][day] = "Ferien"

            # B. Fixen Freitags-Tag (Teilzeit) eintragen
            for day in week_days:
                for emp in self.employees:
                    e_name = emp['name']
                    if day not in plan[e_name] and emp['fixed_off'] is not None and day.weekday() == emp['fixed_off']:
                        plan[e_name][day] = "Teilzeit (Frei)"

            # C. Zufällige freie Tage für Teilzeitkräfte (<100%) ohne fixen freien Tag zuweisen
            for emp in self.employees:
                e_name = emp['name']
                if emp['pensum'] < 100:
                    target_off_days = (100 - emp['pensum']) // 20
                    existing_off_count = sum(
                        1 for d in week_days 
                        if plan[e_name].get(d) in ["Teilzeit (Frei)", "Ferien"]
                    )
                    needed_random_off = target_off_days - existing_off_count

                    if needed_random_off > 0:
                        candidate_days = [d for d in week_days if d not in plan[e_name]]
                        if len(candidate_days) >= needed_random_off:
                            selected_off_days = random.sample(candidate_days, needed_random_off)
                            for off_day in selected_off_days:
                                plan[e_name][off_day] = "Teilzeit (Frei)"

            # D. Wunschtage anwenden
            for day in week_days:
                for emp in self.employees:
                    e_name = emp['name']
                    if plan[e_name].get(day) in ["Ferien", "Teilzeit (Frei)"]:
                        continue
                    emp_wishes = [w for w in self.wishes if w['emp'] == e_name and w['date'] == day]
                    if emp_wishes:
                        w_type = emp_wishes[0]['type']
                        if w_type == "Homeoffice":
                            if ho_weekly_count[e_name] < weekly_ho_max[e_name]:
                                plan[e_name][day] = "Homeoffice"
                                ho_weekly_count[e_name] += 1
                                if day.weekday() == 0:
                                    monday_ho_counts[e_name] += 1
                                elif day.weekday() == 4:
                                    friday_ho_counts[e_name] += 1
                        else:
                            plan[e_name][day] = w_type
                            shift_counts[e_name][w_type] += 1

            # E. Prioritäre Ferien-Übergangstage (Pre/Post WFH)
            for day in week_days:
                for emp in self.employees:
                    e_name = emp['name']
                    if day in plan[e_name]:
                        continue
                    if (e_name, day) in pre_vac_days or (e_name, day) in post_vac_days:
                        if ho_weekly_count[e_name] < weekly_ho_max[e_name]:
                            on_site_count = sum(
                                1 for e in self.employees 
                                if plan[e['name']].get(day) not in ["Ferien", "Homeoffice", "Teilzeit (Frei)"]
                            )
                            if on_site_count - 1 >= 2 or len(self.employees) < 3:
                                plan[e_name][day] = "Homeoffice"
                                ho_weekly_count[e_name] += 1
                                if day.weekday() == 0:
                                    monday_ho_counts[e_name] += 1
                                elif day.weekday() == 4:
                                    friday_ho_counts[e_name] += 1

            # F. Faire Turnus-Verteilung für FREITAG Homeoffice (Minimale Freitag-Anzahl gewinnt)
            friday = next((d for d in week_days if d.weekday() == 4), None)
            if friday:
                friday_has_ho = any(plan[e['name']].get(friday) == "Homeoffice" for e in self.employees)
                if not friday_has_ho:
                    friday_candidates = []
                    for emp in self.employees:
                        e_name = emp['name']
                        if friday not in plan[e_name] and ho_weekly_count[e_name] < weekly_ho_max[e_name]:
                            on_site_count = sum(
                                1 for e in self.employees 
                                if plan[e['name']].get(friday) not in ["Ferien", "Homeoffice", "Teilzeit (Frei)"]
                            )
                            if on_site_count > 2 or len(self.employees) <= 2:
                                friday_candidates.append(e_name)

                    if friday_candidates:
                        # Sortieren nach geringster Anzahl bisheriger Freitag-HOs
                        friday_candidates.sort(key=lambda name: (friday_ho_counts[name], random.random()))
                        selected_emp = friday_candidates[0]
                        plan[selected_emp][friday] = "Homeoffice"
                        ho_weekly_count[selected_emp] += 1
                        friday_ho_counts[selected_emp] += 1

            # G. Faire Turnus-Verteilung für MONTAG Homeoffice (Minimale Montag-Anzahl gewinnt)
            monday = next((d for d in week_days if d.weekday() == 0), None)
            if monday:
                monday_has_ho = any(plan[e['name']].get(monday) == "Homeoffice" for e in self.employees)
                if not monday_has_ho:
                    monday_candidates = []
                    for emp in self.employees:
                        e_name = emp['name']
                        if monday not in plan[e_name] and ho_weekly_count[e_name] < weekly_ho_max[e_name]:
                            on_site_count = sum(
                                1 for e in self.employees 
                                if plan[e['name']].get(monday) not in ["Ferien", "Homeoffice", "Teilzeit (Frei)"]
                            )
                            if on_site_count > 2 or len(self.employees) <= 2:
                                monday_candidates.append(e_name)

                    if monday_candidates:
                        # Sortieren nach geringster Anzahl bisheriger Montag-HOs
                        monday_candidates.sort(key=lambda name: (monday_ho_counts[name], random.random()))
                        selected_emp = monday_candidates[0]
                        plan[selected_emp][monday] = "Homeoffice"
                        ho_weekly_count[selected_emp] += 1
                        monday_ho_counts[selected_emp] += 1

            # H. Automatische Verteilung verbleibender Homeofficetage
            shuffled_emps = list(self.employees)
            random.shuffle(shuffled_emps)

            for emp in shuffled_emps:
                e_name = emp['name']
                while ho_weekly_count[e_name] < weekly_ho_max[e_name]:
                    candidate_days = []
                    for day in week_days:
                        if day in plan[e_name]:
                            continue
                        on_site_count = sum(
                            1 for e in self.employees 
                            if plan[e['name']].get(day) not in ["Ferien", "Homeoffice", "Teilzeit (Frei)"]
                        )
                        if on_site_count > 2 or len(self.employees) <= 2:
                            candidate_days.append(day)

                    if not candidate_days:
                        break

                    non_wed_candidates = [d for d in candidate_days if d.weekday() != 2]
                    if non_wed_candidates:
                        selected_day = random.choice(non_wed_candidates)
                    else:
                        selected_day = random.choice(candidate_days)

                    plan[e_name][selected_day] = "Homeoffice"
                    ho_weekly_count[e_name] += 1
                    if selected_day.weekday() == 0:
                        monday_ho_counts[e_name] += 1
                    elif selected_day.weekday() == 4:
                        friday_ho_counts[e_name] += 1

            # I. Schichteinteilung (Früh- vs. Spätschicht) vor Ort
            for day in week_days:
                on_site_emps = [
                    e['name'] for e in self.employees 
                    if plan[e['name']].get(day) not in ["Ferien", "Homeoffice", "Teilzeit (Frei)"]
                ]
                unassigned_on_site = [e for e in on_site_emps if day not in plan[e]]
                
                N = len(on_site_emps)
                if N == 0:
                    unstaffed_warnings.append(day.strftime("%d/%m/%Y"))
                    continue

                target_frueh = (N + 1) // 2

                already_frueh = sum(1 for e in on_site_emps if plan[e].get(day) == "Frühschicht")
                needed_frueh = max(0, target_frueh - already_frueh)

                random.shuffle(unassigned_on_site)
                unassigned_on_site.sort(key=lambda e: (shift_counts[e]["Frühschicht"] - shift_counts[e]["Spätschicht"], random.random()))

                for idx, emp_name in enumerate(unassigned_on_site):
                    if idx < needed_frueh:
                        plan[emp_name][day] = "Frühschicht"
                        shift_counts[emp_name]["Frühschicht"] += 1
                    else:
                        plan[emp_name][day] = "Spätschicht"
                        shift_counts[emp_name]["Spätschicht"] += 1

        if unstaffed_warnings:
            messagebox.showwarning(
                "Besetzungswarnung", 
                f"An folgenden Tagen konnte die Mindestbesetzung (Früh-/Spätschicht) nicht abgedeckt werden:\n\n" + 
                ", ".join(unstaffed_warnings)
            )

        self.last_weeks_dict = weeks_dict
        self.last_plan = plan
        self.render_matrix(weeks_dict, plan)

    def render_matrix(self, weeks_dict, plan):
        for widget in self.result_container.winfo_children():
            widget.destroy()

        canvas = tk.Canvas(self.result_container, bg="#FFFFFF")
        scrollbar_y = ttk.Scrollbar(self.result_container, orient="vertical", command=canvas.yview)
        scrollbar_x = ttk.Scrollbar(self.result_container, orient="horizontal", command=canvas.xview)

        scroll_frame = tk.Frame(canvas, bg="#FFFFFF")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(xscrollcommand=scrollbar_x.set, yscrollcommand=scrollbar_y.set)

        scrollbar_x.pack(side="bottom", fill="x")
        scrollbar_y.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        weekday_names = ["Mo", "Di", "Mi", "Do", "Fr"]

        for (year, week_num), days in weeks_dict.items():
            week_title = f" Kalenderwoche {week_num} ({days[0].strftime('%d.%m.%Y')} bis {days[-1].strftime('%d.%m.%Y')}) "
            
            week_frame = ttk.LabelFrame(scroll_frame, text=week_title, padding=8)
            week_frame.pack(fill="x", expand=True, padx=10, pady=10)

            lbl_top_left = tk.Label(
                week_frame, text="Mitarbeiter", font=("Arial", 9, "bold"), 
                bg="#E0E0E0", width=18, height=2, bd=1, relief="solid"
            )
            lbl_top_left.grid(row=0, column=0, sticky="nsew")

            for col_idx, d in enumerate(days, start=1):
                col_text = f"{weekday_names[d.weekday()]}\n{d.strftime('%d/%m')}"
                lbl_hdr = tk.Label(
                    week_frame, text=col_text, font=("Arial", 8, "bold"), 
                    bg="#E0E0E0", width=14, height=2, bd=1, relief="solid"
                )
                lbl_hdr.grid(row=0, column=col_idx, sticky="nsew")

            for row_idx, emp in enumerate(self.employees, start=1):
                emp_name = emp['name']
                disp_text = f"{emp_name} ({emp['pensum']}%)"
                lbl_name = tk.Label(
                    week_frame, text=disp_text, font=("Arial", 9, "bold"), 
                    bg="#F5F5F5", width=18, bd=1, relief="solid", anchor="w", padx=5
                )
                lbl_name.grid(row=row_idx, column=0, sticky="nsew")

                for col_idx, d in enumerate(days, start=1):
                    val = plan[emp_name].get(d, "-")
                    cfg = COLOR_CONFIG.get(val, {"bg": "#FFFFFF", "fg": "#000000"})

                    lbl_cell = tk.Label(
                        week_frame,
                        text=val,
                        font=("Arial", 8, "bold"),
                        bg=cfg["bg"],
                        fg=cfg["fg"],
                        width=14,
                        height=2,
                        bd=1,
                        relief="solid"
                    )
                    lbl_cell.grid(row=row_idx, column=col_idx, sticky="nsew")

    def export_pdf(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror(
                "Modul fehlt", 
                "Für den PDF-Export wird die Python-Bibliothek 'reportlab' benötigt.\n\n"
                "Bitte installiere sie über das Terminal/Konsole mit:\npip install reportlab"
            )
            return

        if not self.last_plan or not self.last_weeks_dict:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Arbeitsplan generieren.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Datei", "*.pdf")],
            title="Arbeitsplan als PDF speichern"
        )

        if not file_path:
            return

        try:
            doc = SimpleDocTemplate(
                file_path, 
                pagesize=landscape(A4),
                rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'DocTitle',
                parent=styles['Heading1'],
                fontSize=18,
                leading=22,
                textColor=colors.HexColor("#2B5C8F"),
                spaceAfter=15
            )
            week_heading_style = ParagraphStyle(
                'WeekTitle',
                parent=styles['Heading2'],
                fontSize=12,
                leading=16,
                textColor=colors.HexColor("#333333"),
                spaceBefore=10,
                spaceAfter=5
            )
            cell_style = ParagraphStyle(
                'CellText',
                parent=styles['Normal'],
                fontSize=8,
                leading=10,
                alignment=1
            )
            hdr_cell_style = ParagraphStyle(
                'HdrCellText',
                parent=styles['Normal'],
                fontSize=8,
                leading=10,
                alignment=1,
                fontName="Helvetica-Bold"
            )

            elements = []
            elements.append(Paragraph("Arbeitsplan & Schichteinteilung", title_style))

            weekday_names = ["Mo", "Di", "Mi", "Do", "Fr"]

            for (year, week_num), days in self.last_weeks_dict.items():
                week_str = f"Kalenderwoche {week_num} ({days[0].strftime('%d.%m.%Y')} bis {days[-1].strftime('%d.%m.%Y')})"
                elements.append(Paragraph(week_str, week_heading_style))

                table_data = []
                header_row = [Paragraph("<b>Mitarbeiter</b>", hdr_cell_style)]
                for d in days:
                    hdr_text = f"<b>{weekday_names[d.weekday()]}</b><br/>{d.strftime('%d/%m')}"
                    header_row.append(Paragraph(hdr_text, hdr_cell_style))
                table_data.append(header_row)

                table_styles = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#B0B0B0")),
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                ]

                for row_idx, emp in enumerate(self.employees, start=1):
                    emp_name = emp['name']
                    row = [Paragraph(f"<b>{emp_name} ({emp['pensum']}%)</b>", cell_style)]
                    for col_idx, d in enumerate(days, start=1):
                        val = self.last_plan[emp_name].get(d, "-")
                        cfg = COLOR_CONFIG.get(val, {"bg": "#FFFFFF", "fg": "#000000"})
                        
                        row.append(Paragraph(val, cell_style))
                        bg_hex = cfg["bg"]
                        table_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor(bg_hex)))

                    table_data.append(row)

                col_widths = [110] + [80] * len(days)
                t = Table(table_data, colWidths=col_widths)
                t.setStyle(TableStyle(table_styles))
                elements.append(t)
                elements.append(Spacer(1, 15))

            doc.build(elements)
            messagebox.showinfo("PDF Export", f"Der Arbeitsplan wurde erfolgreich unter:\n{file_path}\ngespeichert.")

        except Exception as e:
            messagebox.showerror("Fehler beim PDF Export", f"Export fehlgeschlagen:\n{str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ShiftPlannerApp(root)
    root.mainloop()