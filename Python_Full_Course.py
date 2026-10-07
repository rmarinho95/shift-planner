import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

class ShiftPlannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Arbeitsplan Generator")
        self.root.geometry("1150x700")

        self.employees = []
        self.wishes = []      # Format: {'emp': str, 'date': date, 'type': str}
        self.vacations = []   # Format: {'emp': str, 'start': date, 'end': date}

        self._build_ui()

    def _build_ui(self):
        # Header / Konfiguration Frame
        control_frame = ttk.LabelFrame(self.root, text="Konfiguration & Erfassung", padding=10)
        control_frame.pack(fill="x", padx=10, pady=5)

        # 1. Zeitraum
        ttk.Label(control_frame, text="Startdatum (DD/MM/YYYY):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.ent_start = ttk.Entry(control_frame, width=12)
        self.ent_start.grid(row=0, column=1, padx=5, pady=2)
        self.ent_start.insert(0, "12/10/2026")

        ttk.Label(control_frame, text="Enddatum (DD/MM/YYYY):").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        self.ent_end = ttk.Entry(control_frame, width=12)
        self.ent_end.grid(row=0, column=3, padx=5, pady=2)
        self.ent_end.insert(0, "23/10/2026")

        # 2. Mitarbeiter
        emp_frame = ttk.LabelFrame(control_frame, text="1. Mitarbeiter verwalten", padding=5)
        emp_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        self.ent_emp_name = ttk.Entry(emp_frame, width=15)
        self.ent_emp_name.pack(side="top", anchor="w", padx=2, pady=2)
        btn_add_emp = ttk.Button(emp_frame, text="Mitarbeiter Hinzufügen", command=self.add_employee)
        btn_add_emp.pack(side="top", anchor="w", padx=2, pady=2)

        self.lst_employees = tk.Listbox(emp_frame, height=4, width=22)
        self.lst_employees.pack(side="bottom", fill="both", expand=True, pady=2)

        # 3. Wünsche
        wish_frame = ttk.LabelFrame(control_frame, text="2. Wunschtage erfassen", padding=5)
        wish_frame.grid(row=1, column=2, columnspan=2, sticky="nsew", padx=5, pady=5)

        ttk.Label(wish_frame, text="Datum (DD/MM/YYYY):").grid(row=0, column=0, sticky="w")
        self.ent_wish_date = ttk.Entry(wish_frame, width=12)
        self.ent_wish_date.grid(row=0, column=1, padx=2, pady=2)

        ttk.Label(wish_frame, text="Schicht / HO:").grid(row=1, column=0, sticky="w")
        self.cmb_wish_type = ttk.Combobox(
            wish_frame, 
            values=["Frühschicht (07:30-16:30)", "Spätschicht (08:30-17:30)", "Homeoffice"], 
            width=22, 
            state="readonly"
        )
        self.cmb_wish_type.grid(row=1, column=1, padx=2, pady=2)
        self.cmb_wish_type.current(0)

        btn_add_wish = ttk.Button(wish_frame, text="Wunsch speichern", command=self.add_wish)
        btn_add_wish.grid(row=2, column=0, columnspan=2, pady=6)

        # 4. Ferien
        vac_frame = ttk.LabelFrame(control_frame, text="3. Ferien erfassen", padding=5)
        vac_frame.grid(row=1, column=4, columnspan=2, sticky="nsew", padx=5, pady=5)

        ttk.Label(vac_frame, text="Von (DD/MM/YYYY):").grid(row=0, column=0, sticky="w")
        self.ent_vac_start = ttk.Entry(vac_frame, width=12)
        self.ent_vac_start.grid(row=0, column=1, padx=2, pady=2)

        ttk.Label(vac_frame, text="Bis (DD/MM/YYYY):").grid(row=1, column=0, sticky="w")
        self.ent_vac_end = ttk.Entry(vac_frame, width=12)
        self.ent_vac_end.grid(row=1, column=1, padx=2, pady=2)

        btn_add_vac = ttk.Button(vac_frame, text="Ferien speichern", command=self.add_vacation)
        btn_add_vac.grid(row=2, column=0, columnspan=2, pady=6)

        # Generieren-Knopf
        btn_generate = tk.Button(
            self.root, 
            text="Arbeitsplan Generieren", 
            bg="#2b5c8f", 
            fg="white", 
            font=("Arial", 11, "bold"), 
            command=self.generate_plan
        )
        btn_generate.pack(fill="x", padx=10, pady=8)

        # Ergebnis-Matrix Frame
        self.result_frame = ttk.LabelFrame(self.root, text="Arbeitsplan (Matrixansicht)", padding=10)
        self.result_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Beispiel-Daten zur sofortigen Testbarkeit
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
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Mitarbeiter in der Liste (links) auswählen.")
            return
        emp = self.employees[sel[0]]
        date_str = self.ent_wish_date.get().strip()
        wish_raw = self.cmb_wish_type.get()
        wish_type = "Frühschicht" if "Früh" in wish_raw else ("Spätschicht" if "Spät" in wish_raw else "Homeoffice")

        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y").date()
            self.wishes.append({'emp': emp, 'date': dt, 'type': wish_type})
            messagebox.showinfo("Gespeichert", f"Wunsch für {emp} am {date_str} ({wish_type}) hinterlegt.")
            self.ent_wish_date.delete(0, tk.END)
        except ValueError:
            messagebox.showerror("Fehler", "Ungültiges Format! Bitte DD/MM/YYYY eingeben.")

    def add_vacation(self):
        sel = self.lst_employees.curselection()
        if not sel:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Mitarbeiter in der Liste (links) auswählen.")
            return
        emp = self.employees[sel[0]]
        s_str = self.ent_vac_start.get().strip()
        e_str = self.ent_vac_end.get().strip()

        try:
            s_dt = datetime.strptime(s_str, "%d/%m/%Y").date()
            e_dt = datetime.strptime(e_str, "%d/%m/%Y").date()
            if e_dt < s_dt:
                messagebox.showerror("Fehler", "Das Enddatum muss nach dem Startdatum liegen.")
                return
            self.vacations.append({'emp': emp, 'start': s_dt, 'end': e_dt})
            messagebox.showinfo("Gespeichert", f"Ferien für {emp} ({s_str} bis {e_str}) hinterlegt.")
            self.ent_vac_start.delete(0, tk.END)
            self.ent_vac_end.delete(0, tk.END)
        except ValueError:
            messagebox.showerror("Fehler", "Ungültiges Format! Bitte DD/MM/YYYY eingeben.")

    def generate_plan(self):
        if not self.employees:
            messagebox.showwarning("Achtung", "Bitte mindestens einen Mitarbeiter erfassen.")
            return

        try:
            start_date = datetime.strptime(self.ent_start.get().strip(), "%d/%m/%Y").date()
            end_date = datetime.strptime(self.ent_end.get().strip(), "%d/%m/%Y").date()
        except ValueError:
            messagebox.showerror("Fehler", "Zeitraum im Format DD/MM/YYYY eingeben.")
            return

        if end_date < start_date:
            messagebox.showerror("Fehler", "Enddatum muss nach Startdatum liegen.")
            return

        # 1. Arbeitstage ermitteln (nur Mo-Fr)
        work_days = []
        curr = start_date
        while curr <= end_date:
            if curr.weekday() < 5:  # 0=Montag, 4=Freitag
                work_days.append(curr)
            curr += timedelta(days=1)

        if not work_days:
            messagebox.showinfo("Info", "Keine Arbeitstage (Mo-Fr) im gewählten Zeitraum.")
            return

        # 2. Datenstrukturen für Zuweisung & Verteilung
        plan = {emp: {} for emp in self.employees}
        ho_weekly_count = {emp: {} for emp in self.employees}
        shift_counts = {emp: {"Frühschicht": 0, "Spätschicht": 0} for emp in self.employees}

        weekday_names = ["Mo", "Di", "Mi", "Do", "Fr"]

        # 3. Tagesweise Planung durchführen
        for day in work_days:
            year, week_num, _ = day.isocalendar()
            week_key = f"{year}-W{week_num}"

            available_emps = []

            # A. Ferien abfangen
            for emp in self.employees:
                on_vac = any(v['start'] <= day <= v['end'] for v in self.vacations if v['emp'] == emp)
                if on_vac:
                    plan[emp][day] = "Ferien"
                else:
                    available_emps.append(emp)

            day_assigned = {}

            # B. Wunschtage berücksichtigen
            for emp in list(available_emps):
                emp_wishes = [w for w in self.wishes if w['emp'] == emp and w['date'] == day]
                if emp_wishes:
                    w_type = emp_wishes[0]['type']
                    if w_type == "Homeoffice":
                        current_ho = ho_weekly_count[emp].get(week_key, 0)
                        if current_ho < 2:
                            day_assigned[emp] = "Homeoffice"
                            ho_weekly_count[emp][week_key] = current_ho + 1
                            available_emps.remove(emp)
                    else:
                        day_assigned[emp] = w_type
                        shift_counts[emp][w_type] += 1
                        available_emps.remove(emp)

            # C. Verbleibende Mitarbeiter fair auf Früh-/Spätschicht verteilen
            for emp in available_emps:
                # Ausgewogene Verteilung basierend auf bisherigen Schichten
                if shift_counts[emp]["Frühschicht"] <= shift_counts[emp]["Spätschicht"]:
                    chosen_shift = "Frühschicht"
                else:
                    chosen_shift = "Spätschicht"

                day_assigned[emp] = chosen_shift
                shift_counts[emp][chosen_shift] += 1

            for emp, assignment in day_assigned.items():
                plan[emp][day] = assignment

        # 4. Ergebnis-Matrix rendern
        self.render_matrix(work_days, plan, weekday_names)

    def render_matrix(self, work_days, plan, weekday_names):
        for widget in self.result_frame.winfo_children():
            widget.destroy()

        tree_scroll_x = ttk.Scrollbar(self.result_frame, orient="horizontal")
        tree_scroll_y = ttk.Scrollbar(self.result_frame, orient="vertical")

        cols = ["Mitarbeiter"] + [f"{weekday_names[d.weekday()]} {d.strftime('%d/%m')}" for d in work_days]
        
        tree = ttk.Treeview(
            self.result_frame, 
            columns=cols, 
            show="headings",
            xscrollcommand=tree_scroll_x.set,
            yscrollcommand=tree_scroll_y.set
        )

        tree_scroll_x.config(command=tree.xview)
        tree_scroll_y.config(command=tree.yview)

        tree_scroll_x.pack(side="bottom", fill="x")
        tree_scroll_y.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)

        tree.heading("Mitarbeiter", text="Mitarbeiter")
        tree.column("Mitarbeiter", width=120, anchor="w")

        for idx, d in enumerate(work_days):
            col_id = cols[idx + 1]
            tree.heading(col_id, text=col_id)
            tree.column(col_id, width=100, anchor="center")

        for emp in self.employees:
            row_vals = [emp]
            for d in work_days:
                row_vals.append(plan[emp].get(d, "-"))
            tree.insert("", "end", values=row_vals)


if __name__ == "__main__":
    root = tk.Tk()
    app = ShiftPlannerApp(root)
    root.mainloop()