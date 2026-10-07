# shift-planner
Python Shift Planner &amp; Schedule Generator for an IT Service Desk. 

An intuitive Tkinter-based desktop application that automates fair employee shift distribution (Early/Late shifts), manages Home Office limits (max 2 days/week), handles vacation periods, and visualizes schedules in a color-coded matrix using a custom popup mini-calendar.

# 📅 Shift Planner & Schedule Generator

A lightweight, standalone GUI application built with Python and Tkinter for managing employee shift schedules, vacation planning, and Home Office tracking with built-in rule validation.

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## ✨ Features

- **Custom Dropdown Mini-Calendar Widget**: Date picker with month navigation and "Today" button, built entirely with Tkinter without external dependencies.
- **Automated Fair Scheduling**: Balances Early Shifts (`07:30 - 16:30`) and Late Shifts (`08:30 - 17:30`) across team members.
- **Minimum Coverage Guarantee**: Automatically ensures at least one employee is assigned to the Early Shift and Late Shift each working day (Monday–Friday).
- **Home Office Constraint Validation**: Enforces a maximum limit of **2 Home Office days per week** per employee and alerts the user if exceeded.
- **Vacation & Wish Day Tracking**: Allows employees to request specific shifts, Home Office, or register multi-day vacations.
- **Pastel Color-Coded Schedule Matrix**: Interactive, scrollable schedule grid with visual indicators:
  - 🟩 **Early Shift**: Light Green
  - 🟩 **Late Shift**: Dark Green (Pastel)
  - 🟦 **Home Office**: Soft Blue
  - ⬜ **Vacation**: Light Gray
  - 🟥 **Coverage Warning**: Soft Red

---

## 🛠️ Prerequisites & Installation

No external `pip` packages required. The project relies strictly on standard Python libraries (`tkinter`, `datetime`, `calendar`).

1. **Clone the repository**:
   ```bash
   git clone [https://github.com/your-username/shift-planner.git](https://github.com/your-username/shift-planner.git)
   cd shift-planner
