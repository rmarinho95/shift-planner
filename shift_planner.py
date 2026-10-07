import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta, date
import calendar

# --- FARBLEGENDE (Pastelltöne) ---
COLOR_CONFIG = {
    "Frühschicht": {"bg": "#D4EDDA", "fg": "#155724", "desc": "Frühschicht (07:30 - 16:30)"},
    "Spätschicht": {"bg": "#A8E6CF", "fg": "#0B5345", "desc": "Spätschicht (08:30 - 17:30)"},
    "Homeoffice":  {"bg": "#D0E8FF", "fg": "#0C5460", "desc": "Homeoffice"},
    "Ferien":      {"bg": "#E2E3E5", "fg": "#383D41", "desc": "Ferien"},
    "Unterbesetzt":{"bg": "#F8D7DA", "fg": "#721C24", "desc": "Fehlende Besetzung!"}
}


class CalendarDatePicker(ttk.Frame):
    """Dropdown-Minikalender Widget analog Excel / Windows Kalender-Popup"""
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

        # TopLevel-Fenster ohne Rahmen für echten Dropdown-Look
        self.popup = tk.Toplevel(self)
        self.popup.wm_overrideredirect(True)
        self.popup.attributes("-topmost", True)

        # Position exakt unter dem Eingabefeld
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

        for row_idx, week in enumerate(month_days, start=1):
            for col_idx, day_dt in enumerate(week):
                is_curr_month = (day_dt.month == self.view_month)
                fg_color = "#000000" if is_curr_month else "#B0B0B0"
                bg_color = "#D0E8FF" if day_dt == self.get_date() else "#FFFFFF"

                btn_day = tk.Button(
                    grid_frame,
                    text=str(day_dt.day),
                    bg=bg_color,
                    fg=fg_color,
                    bd=1,
                    relief="flat",
                    width=3,
                    font=("Arial", 8),
                    command=lambda d=day_dt: self.select_day(d)
                )
                btn_day.grid(row=row_idx, column=col_idx, padx=1, pady=1)

        # Fusszeile "Heute" (wie im Bild)
        today = date.today()
        btn_today = tk.Button(
            inner_frame,
            text=f"Heute: {today.strftime('%d.%m.%Y')}",
            bg="#F8F8F8",
            bd=0,
            font=("Arial", 8, "underline"),
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
        self.root.title("Arbeitsplan Generator mit Schichtprüfungen")
        self.root.geometry("1200x750")

        self.employees = []
        self.wishes = []      # {'emp': str, 'date': date, 'type': str}
        self.vacations = []   # {'emp': str, 'start': date, 'end': date}

        self._build_ui()

    def _build_ui(self):
        # Steuerung
        control_frame = ttk.LabelFrame(self.root, text="Konfiguration & Erfassung", padding=10)
        control_frame.pack(fill="x", padx=10, pady=5)

        # 1. Zeitraum
        ttk.Label(control_frame, text="Startdatum:").grid(row=0, column=0, sticky="w", padx=5)
        self.dp_start = CalendarDatePicker(control_frame, date.today())
        self.dp_start.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(control_frame, text="Enddatum:").grid(row=0, column=2, sticky="w", padx=5)
        self.dp_end = CalendarDatePicker(control_frame, date.today() + timedelta(days=12))
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

        # Generieren Knopf
        btn_generate = tk.Button(
            self.root, 
            text="Arbeitsplan Generieren", 
            bg="#2b5c8f", 
            fg="white", 
            font=("Arial", 11, "bold"), 
            command=self.generate_plan
        )
        btn_generate.pack(fill="x", padx=10, pady=5)

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
        self.result_container = ttk.LabelFrame(self.root, text="Arbeitsplan Matrix", padding=5)
        self.result_container.pack(fill="both", expand=True, padx=10, pady=5)

        # Beispieldaten vorausfüllen
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

        # PRÜFUNG: Maximal 2 Tage Homeoffice pro Kalenderwoche
        if wish_type == "Homeoffice":
            year, week_num, _ = dt.isocalendar()
            
            # Bereits erfasste HO-Wünsche dieser Person in dieser Woche zählen
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

        if not s_dt or not e_dt:
            messagebox.showerror("Fehler", "Gültiges Von- und Bis-Datum angeben.")
            return

        if e_dt < s_dt:
            messagebox.showerror("Fehler", "Enddatum muss nach Startdatum liegen.")
            return

        self.vacations.append({'emp': emp, 'start': s_dt, 'end': e_dt})
        messagebox.showinfo("Gespeichert", f"Ferien für {emp} vom {s_dt.strftime('%d/%m/%Y')} bis {e_dt.strftime('%d/%m/%Y')} erfasst.")

    def generate_plan(self):
        if not self.employees:
            messagebox.showwarning("Achtung", "Bitte mindestens einen Mitarbeiter erfassen.")
            return

        start_date = self.dp_start.get_date()
        end_date = self.dp_end.get_date()

        if not start_date or not end_date or end_date < start_date:
            messagebox.showerror("Fehler", "Gültigen Zeitraum wählen.")
            return

        # Arbeitstage ermitteln (Montag bis Freitag)
        work_days = []
        curr = start_date
        while curr <= end_date:
            if curr.weekday() < 5:
                work_days.append(curr)
            curr += timedelta(days=1)

        if not work_days:
            messagebox.showinfo("Info", "Keine Arbeitstage (Mo-Fr) im gewählten Zeitraum.")
            return

        plan = {emp: {} for emp in self.employees}
        ho_weekly_count = {emp: {} for emp in self.employees}
        shift_counts = {emp: {"Frühschicht": 0, "Spätschicht": 0} for emp in self.employees}
        unstaffed_warnings = []

        # Tagesweise Einteilung mit Besetzungsprüfung
        for day in work_days:
            year, week_num, _ = day.isocalendar()
            week_key = f"{year}-W{week_num}"

            available_emps = []

            # 1. Ferien filtern
            for emp in self.employees:
                on_vac = any(v['start'] <= day <= v['end'] for v in self.vacations if v['emp'] == emp)
                if on_vac:
                    plan[emp][day] = "Ferien"
                else:
                    available_emps.append(emp)

            assigned_today = {}

            # 2. Wunschtage verarbeiten
            for emp in list(available_emps):
                emp_wishes = [w for w in self.wishes if w['emp'] == emp and w['date'] == day]
                if emp_wishes:
                    w_type = emp_wishes[0]['type']
                    if w_type == "Homeoffice":
                        if ho_weekly_count[emp].get(week_key, 0) < 2:
                            assigned_today[emp] = "Homeoffice"
                            ho_weekly_count[emp][week_key] = ho_weekly_count[emp].get(week_key, 0) + 1
                            available_emps.remove(emp)
                    else:
                        assigned_today[emp] = w_type
                        shift_counts[emp][w_type] += 1
                        available_emps.remove(emp)

            # 3. Mindestbesetzung garantieren (Frühschicht & Spätschicht)
            has_frueh = any(val == "Frühschicht" for val in assigned_today.values())
            has_spaet = any(val == "Spätschicht" for val in assigned_today.values())

            # A. Frühschicht sichern
            if not has_frueh and available_emps:
                # Wähle Person mit den wenigsten Frühschichten
                best_emp = min(available_emps, key=lambda e: shift_counts[e]["Frühschicht"])
                assigned_today[best_emp] = "Frühschicht"
                shift_counts[best_emp]["Frühschicht"] += 1
                available_emps.remove(best_emp)
                has_frueh = True

            # B. Spätschicht sichern
            if not has_spaet and available_emps:
                # Wähle Person mit den wenigsten Spätschichten
                best_emp = min(available_emps, key=lambda e: shift_counts[e]["Spätschicht"])
                assigned_today[best_emp] = "Spätschicht"
                shift_counts[best_emp]["Spätschicht"] += 1
                available_emps.remove(best_emp)
                has_spaet = True

            # Warnung sammeln, falls Besetzung mangels Personal unmöglich ist
            if not has_frueh or not has_spaet:
                unstaffed_warnings.append(day.strftime("%d/%m/%Y"))

            # 4. Restliche Mitarbeiter fair aufschlüsseln
            for emp in available_emps:
                if shift_counts[emp]["Frühschicht"] <= shift_counts[emp]["Spätschicht"]:
                    chosen = "Frühschicht"
                else:
                    chosen = "Spätschicht"
                assigned_today[emp] = chosen
                shift_counts[emp][chosen] += 1

            for emp, assignment in assigned_today.items():
                plan[emp][day] = assignment

        if unstaffed_warnings:
            messagebox.showwarning(
                "Besetzungswarnung", 
                f"An folgenden Tagen konnte mangels verfügbarem Personal die Früh- oder Spätschicht nicht besetzt werden:\n\n" + 
                ", ".join(unstaffed_warnings)
            )

        self.render_matrix(work_days, plan)

    def render_matrix(self, work_days, plan):
        # Container leeren
        for widget in self.result_container.winfo_children():
            widget.destroy()

        # Scrollbare Canvas-Matrix für Farbzellen
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

        # 1. Header-Zeile (Mitarbeiter + Daten)
        lbl_top_left = tk.Label(
            scroll_frame, text="Mitarbeiter", font=("Arial", 9, "bold"), 
            bg="#E0E0E0", width=16, height=2, bd=1, relief="solid"
        )
        lbl_top_left.grid(row=0, column=0, sticky="nsew")

        for col_idx, d in enumerate(work_days, start=1):
            col_text = f"{weekday_names[d.weekday()]}\n{d.strftime('%d/%m')}"
            lbl_hdr = tk.Label(
                scroll_frame, text=col_text, font=("Arial", 8, "bold"), 
                bg="#E0E0E0", width=12, height=2, bd=1, relief="solid"
            )
            lbl_hdr.grid(row=0, column=col_idx, sticky="nsew")

        # 2. Datenzeilen mit farbigen Feldern
        for row_idx, emp in enumerate(self.employees, start=1):
            # Namensspalte
            lbl_name = tk.Label(
                scroll_frame, text=emp, font=("Arial", 9, "bold"), 
                bg="#F5F5F5", width=16, bd=1, relief="solid", anchor="w", padx=5
            )
            lbl_name.grid(row=row_idx, column=0, sticky="nsew")

            for col_idx, d in enumerate(work_days, start=1):
                val = plan[emp].get(d, "-")
                
                # Farbkonfiguration abrufen
                cfg = COLOR_CONFIG.get(val, {"bg": "#FFFFFF", "fg": "#000000"})

                lbl_cell = tk.Label(
                    scroll_frame,
                    text=val,
                    font=("Arial", 8, "bold"),
                    bg=cfg["bg"],
                    fg=cfg["fg"],
                    width=12,
                    height=2,
                    bd=1,
                    relief="solid"
                )
                lbl_cell.grid(row=row_idx, column=col_idx, sticky="nsew")


if __name__ == "__main__":
    root = tk.Tk()
    app = ShiftPlannerApp(root)
    root.mainloop()