import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta, date
import calendar
from collections import defaultdict

# --- FARBLEGENDE (Pastelltöne) ---
COLOR_CONFIG = {
    "Frühschicht": {"bg": "#D4EDDA", "fg": "#155724", "desc": "Frühschicht (07:30 - 16:30)"},
    "Spätschicht": {"bg": "#A8E6CF", "fg": "#0B5345", "desc": "Spätschicht (08:30 - 17:30)"},
    "Homeoffice":  {"bg": "#D0E8FF", "fg": "#0C5460", "desc": "Homeoffice"},
    "Ferien":      {"bg": "#E2E3E5", "fg": "#383D41", "desc": "Ferien"},
    "Unterbesetzt":{"bg": "#F8D7DA", "fg": "#721C24", "desc": "Fehlende Besetzung!"}
}


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
        self.root.title("Arbeitsplan Generator mit intelligenter HO-Verteilung")
        self.root.geometry("1200x820")

        self.employees = []
        self.wishes = []      # {'emp': str, 'date': date, 'type': str}
        self.vacations = []   # {'emp': str, 'start': date, 'end': date}

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
        emp_frame = ttk.LabelFrame(control_frame, text="1. Mitarbeiter", padding=5)
        emp_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        self.ent_emp_name = ttk.Entry(emp_frame, width=15)
        self.ent_emp_name.pack(side="top", anchor="w", padx=2, pady=2)
        btn_add_emp = ttk.Button(emp_frame, text="Mitarbeiter Hinzufügen", command=self.add_employee)
        btn_add_emp.pack(side="top", anchor="w", padx=2, pady=2)

        self.lst_employees = tk.Listbox(emp_frame, height=4, width=22)
        self.lst_employees.pack(side="bottom", fill="both", expand=True, pady=2)

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

        # Aktions-Buttons (Generieren & Reset)
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=5)

        btn_generate = tk.Button(
            btn_frame, 
            text="Arbeitsplan Generieren", 
            bg="#2b5c8f", 
            fg="white", 
            font=("Arial", 11, "bold"), 
            command=self.generate_plan
        )
        btn_generate.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_reset = tk.Button(
            btn_frame, 
            text="Alles Zurücksetzen", 
            bg="#C0392B", 
            fg="white", 
            font=("Arial", 11, "bold"), 
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
        for name in ["Anna", "Ben", "Clara", "David"]:
            self.employees.append(name)
            self.lst_employees.insert(tk.END, name)

    def add_employee(self):
        name = self.ent_emp_name.get().strip()
        if name and name not in self.employees:
            self.employees.append(name)
            self.lst_employees.insert(tk.END, name)
            self.ent_emp_name.delete(0, tk.END)

    def add_wish(self):
        sel = self.lst_employees.curselection()
        if not sel:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Mitarbeiter in der Liste auswählen.")
            return

        emp = self.employees[sel[0]]
        dt = self.dp_wish_date.get_date()
        wish_type = self.cmb_wish_type.get()

        if not dt:
            messagebox.showerror("Fehler", "Ungültiges Datum.")
            return

        if wish_type == "Homeoffice":
            year, week_num, _ = dt.isocalendar()
            ho_count_in_week = sum(
                1 for w in self.wishes 
                if w['emp'] == emp and w['type'] == "Homeoffice" and w['date'].isocalendar()[:2] == (year, week_num)
            )

            if ho_count_in_week >= 2:
                messagebox.showwarning(
                    "Regelung nicht erfüllt", 
                    f"Nicht möglich!\n\nFür {emp} wurden in KW {week_num} bereits {ho_count_in_week} Homeoffice-Wunschtage erfasst.\n\n"
                    f"Regelung: Nur max. 2 Tage Homeoffice pro Woche bei 100%-Pensum erlaubt."
                )
                return

        self.wishes.append({'emp': emp, 'date': dt, 'type': wish_type})
        messagebox.showinfo("Gespeichert", f"Wunsch für {emp} am {dt.strftime('%d/%m/%Y')} ({wish_type}) hinterlegt.")

    def add_vacation(self):
        sel = self.lst_employees.curselection()
        if not sel:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Mitarbeiter auswählen.")
            return

        emp = self.employees[sel[0]]
        s_dt = self.dp_vac_start.get_date()
        e_dt = self.dp_vac_end.get_date()

        if not s_dt or not e_dt or e_dt < s_dt:
            messagebox.showerror("Fehler", "Gültiges Von- und Bis-Datum angeben.")
            return

        self.vacations.append({'emp': emp, 'start': s_dt, 'end': e_dt})
        messagebox.showinfo("Gespeichert", f"Ferien für {emp} vom {s_dt.strftime('%d/%m/%Y')} bis {e_dt.strftime('%d/%m/%Y')} erfasst.")

    def reset_all(self):
        """Löscht alle erfassten Wünsche und Ferien"""
        if messagebox.askyesno("Zurücksetzen", "Möchtest du wirklich alle eingegebenen Wunschtage und Ferien zurücksetzen?"):
            self.wishes.clear()
            self.vacations.clear()
            for widget in self.result_container.winfo_children():
                widget.destroy()
            messagebox.showinfo("Zurückgesetzt", "Alle Wunschtage und Ferien wurden erfolgreich gelöscht.")

    def is_in_vacation(self, emp, d):
        return any(v['start'] <= d <= v['end'] for v in self.vacations if v['emp'] == emp)

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

        # 2. Vorabermittlung von Tagen direkt VOR und NACH Ferien pro Mitarbeiter
        pre_vac_days = set()   # (emp, day) -> Tag vor Ferien
        post_vac_days = set()  # (emp, day) -> Tag nach Ferien

        for emp in self.employees:
            for idx, day in enumerate(work_days):
                if not self.is_in_vacation(emp, day):
                    if idx > 0 and self.is_in_vacation(emp, work_days[idx - 1]):
                        post_vac_days.add((emp, day))
                    if idx < len(work_days) - 1 and self.is_in_vacation(emp, work_days[idx + 1]):
                        pre_vac_days.add((emp, day))

        # Max HO Limit pro Woche ermitteln (Standard: 2, bei Ferienübergang in dieser Woche: 1)
        weekly_ho_max = {}
        for day in work_days:
            y, w, _ = day.isocalendar()
            week_key = f"{y}-W{w}"
            for emp in self.employees:
                if (emp, week_key) not in weekly_ho_max:
                    weekly_ho_max[(emp, week_key)] = 2
                if (emp, day) in pre_vac_days or (emp, day) in post_vac_days:
                    weekly_ho_max[(emp, week_key)] = 1  # Wegen Ferien-HO darf kein weiteres HO vergeben werden

        plan = {emp: {} for emp in self.employees}
        ho_weekly_count = defaultdict(lambda: defaultdict(int))
        shift_counts = {emp: {"Frühschicht": 0, "Spätschicht": 0} for emp in self.employees}
        unstaffed_warnings = []

        weeks_dict = defaultdict(list)

        # 3. Tagesweise Berechnung
        for day in work_days:
            year, week_num, _ = day.isocalendar()
            week_key = f"{year}-W{week_num}"
            weeks_dict[(year, week_num)].append(day)

            available_emps = []

            # A. Ferien kennzeichnen
            for emp in self.employees:
                if self.is_in_vacation(emp, day):
                    plan[emp][day] = "Ferien"
                else:
                    available_emps.append(emp)

            assigned_today = {}

            # B. Benutzerdefinierte Wunschtage
            for emp in list(available_emps):
                emp_wishes = [w for w in self.wishes if w['emp'] == emp and w['date'] == day]
                if emp_wishes:
                    w_type = emp_wishes[0]['type']
                    if w_type == "Homeoffice":
                        if ho_weekly_count[emp][week_key] < weekly_ho_max[(emp, week_key)]:
                            assigned_today[emp] = "Homeoffice"
                            ho_weekly_count[emp][week_key] += 1
                            available_emps.remove(emp)
                    else:
                        assigned_today[emp] = w_type
                        shift_counts[emp][w_type] += 1
                        available_emps.remove(emp)

            # C. Prioritäre Ferien-Übergangstage (Pre / Post Vacation HO)
            for emp in list(available_emps):
                if (emp, day) in pre_vac_days or (emp, day) in post_vac_days:
                    if ho_weekly_count[emp][week_key] < weekly_ho_max[(emp, week_key)]:
                        # Prüfen, ob noch genügend Mitarbeiter für Schichten übrig bleiben
                        if len(available_emps) - 1 >= 2 or (len(self.employees) < 3):
                            assigned_today[emp] = "Homeoffice"
                            ho_weekly_count[emp][week_key] += 1
                            available_emps.remove(emp)

            # D. Mindestbesetzung garantieren (1x Frühschicht, 1x Spätschicht)
            has_frueh = any(val == "Frühschicht" for val in assigned_today.values())
            has_spaet = any(val == "Spätschicht" for val in assigned_today.values())

            if not has_frueh and available_emps:
                best_emp = min(available_emps, key=lambda e: shift_counts[e]["Frühschicht"])
                assigned_today[best_emp] = "Frühschicht"
                shift_counts[best_emp]["Frühschicht"] += 1
                available_emps.remove(best_emp)
                has_frueh = True

            if not has_spaet and available_emps:
                best_emp = min(available_emps, key=lambda e: shift_counts[e]["Spätschicht"])
                assigned_today[best_emp] = "Spätschicht"
                shift_counts[best_emp]["Spätschicht"] += 1
                available_emps.remove(best_emp)
                has_spaet = True

            if not has_frueh or not has_spaet:
                unstaffed_warnings.append(day.strftime("%d/%m/%Y"))

            # E. Automatische & faire Verteilung verbleibender Homeofficetage
            # Sortiere nach wer aktuell am wenigsten HO in der Woche hat
            available_emps.sort(key=lambda e: ho_weekly_count[e][week_key])

            for emp in list(available_emps):
                max_allowed = weekly_ho_max[(emp, week_key)]
                if ho_weekly_count[emp][week_key] < max_allowed:
                    # Mindestbesetzung für verbleibende Personen wahren
                    assigned_today[emp] = "Homeoffice"
                    ho_weekly_count[emp][week_key] += 1
                    available_emps.remove(emp)

            # F. Restliche Mitarbeiter auf Früh- und Spätschicht aufteilen
            for emp in available_emps:
                chosen = "Frühschicht" if shift_counts[emp]["Frühschicht"] <= shift_counts[emp]["Spätschicht"] else "Spätschicht"
                assigned_today[emp] = chosen
                shift_counts[emp][chosen] += 1

            for emp, assignment in assigned_today.items():
                plan[emp][day] = assignment

        if unstaffed_warnings:
            messagebox.showwarning(
                "Besetzungswarnung", 
                f"An folgenden Tagen konnte die Mindestbesetzung (Früh-/Spätschicht) nicht abgedeckt werden:\n\n" + 
                ", ".join(unstaffed_warnings)
            )

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
                bg="#E0E0E0", width=16, height=2, bd=1, relief="solid"
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
                lbl_name = tk.Label(
                    week_frame, text=emp, font=("Arial", 9, "bold"), 
                    bg="#F5F5F5", width=16, bd=1, relief="solid", anchor="w", padx=5
                )
                lbl_name.grid(row=row_idx, column=0, sticky="nsew")

                for col_idx, d in enumerate(days, start=1):
                    val = plan[emp].get(d, "-")
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


if __name__ == "__main__":
    root = tk.Tk()
    app = ShiftPlannerApp(root)
    root.mainloop()