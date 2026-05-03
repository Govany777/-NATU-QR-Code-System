import sqlite3
import os

# Get absolute path to database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'natu.db')

def show_data():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("\n" + "="*80)
    print("NATU ATTENDANCE SYSTEM - DATABASE VIEWER")
    print("="*80)

    # 1. Show Students
    print("\n[!] REGISTERED STUDENTS")
    print("-" * 120)
    print(f"{'ID':<10} | {'Name':<25} | {'Dept':<15} | {'Year':<10} | {'Sec':<5} | {'Photo'}")
    print("-" * 120)
    
    students = cursor.execute("SELECT * FROM students").fetchall()
    for s in students:
        photo = "Yes" if s['photo_url'] else "No"
        print(f"{s['student_id']:<10} | {s['full_name']:<25} | {s['department']:<15} | {s['academic_year']:<10} | {s['section']:<5} | {photo}")

    # 2. Show Attendance
    print("\n[!] ATTENDANCE RECORDS")
    print("-" * 100)
    print(f"{'Student ID':<15} | {'Name':<25} | {'Day':<10} | {'Date':<15} | {'Time'}")
    print("-" * 100)
    
    attendance = cursor.execute("SELECT * FROM attendance ORDER BY id DESC").fetchall()
    for a in attendance:
        print(f"{a['student_id']:<15} | {a['full_name']:<25} | {a['day']:<10} | {a['date']:<15} | {a['time']}")

    conn.close()
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    show_data()
