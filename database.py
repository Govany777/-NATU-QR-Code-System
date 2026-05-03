"""
Database module for NATU Attendance Recording System.
Handles SQLite database initialization and helper functions.
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'natu.db')


def get_db():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize the database with schema and default admin."""
    conn = get_db()
    cursor = conn.cursor()

    # Create Students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            department TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            section TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            photo_url TEXT DEFAULT NULL,
            registration_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add photo_url column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN photo_url TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Create Attendance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            day TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    # Create Admins table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    # Insert default admin if not exists
    existing = cursor.execute(
        "SELECT id FROM admins WHERE username = ?", ("admin",)
    ).fetchone()
    if not existing:
        cursor.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )

    conn.commit()
    conn.close()


# --- Student helpers ---

def register_student(student_id, full_name, department, academic_year, section, password):
    """Register a new student. Returns (success: bool, message: str)."""
    conn = get_db()
    try:
        # Check if student_id already exists
        existing = conn.execute(
            "SELECT id FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if existing:
            return False, "هذا الـ ID مسجل بالفعل"

        # Check if full_name already exists
        existing_name = conn.execute(
            "SELECT id FROM students WHERE full_name = ?", (full_name,)
        ).fetchone()
        if existing_name:
            return False, "هذا الاسم مسجل بالفعل"

        conn.execute(
            """INSERT INTO students (student_id, full_name, department, academic_year, section, password_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (student_id, full_name, department, academic_year, section,
             generate_password_hash(password))
        )
        conn.commit()
        return True, "تم التسجيل بنجاح"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def authenticate_student(full_name, password):
    """Authenticate a student by name and password. Returns student dict or None."""
    conn = get_db()
    student = conn.execute(
        "SELECT * FROM students WHERE full_name = ?", (full_name,)
    ).fetchone()
    conn.close()

    if student and check_password_hash(student['password_hash'], password):
        return dict(student)
    return None


def get_student_by_id(student_id):
    """Find a student by their university ID."""
    conn = get_db()
    student = conn.execute(
        "SELECT * FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    conn.close()
    return dict(student) if student else None


def get_all_students():
    """Get all registered students."""
    conn = get_db()
    students = conn.execute(
        "SELECT full_name, department, academic_year, section, student_id, photo_url, registration_date FROM students ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(s) for s in students]


def update_student_photo(student_id, photo_url):
    """Update a student's photo URL."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE students SET photo_url = ? WHERE student_id = ?",
            (photo_url, student_id)
        )
        conn.commit()
        return True, "تم تحديث الصورة بنجاح"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def update_student_profile(student_id, full_name=None, department=None, academic_year=None, section=None, new_password=None):
    """Update a student's profile. Only updates non-None fields."""
    conn = get_db()
    try:
        student = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if not student:
            return False, "الطالب غير موجود"

        updates = []
        params = []

        if full_name and full_name != student['full_name']:
            # Check if new name is taken
            existing = conn.execute("SELECT id FROM students WHERE full_name = ? AND student_id != ?", (full_name, student_id)).fetchone()
            if existing:
                return False, "هذا الاسم مسجل بالفعل"
            updates.append("full_name = ?")
            params.append(full_name)

        if department:
            updates.append("department = ?")
            params.append(department)

        if academic_year:
            updates.append("academic_year = ?")
            params.append(academic_year)

        if section:
            updates.append("section = ?")
            params.append(section)

        if new_password:
            updates.append("password_hash = ?")
            params.append(generate_password_hash(new_password))

        if not updates:
            return True, "لا توجد تغييرات"

        params.append(student_id)
        query = f"UPDATE students SET {', '.join(updates)} WHERE student_id = ?"
        conn.execute(query, params)
        conn.commit()

        # Also update full_name in attendance records if name changed
        if full_name and full_name != student['full_name']:
            conn.execute("UPDATE attendance SET full_name = ? WHERE student_id = ?", (full_name, student_id))
            conn.commit()

        return True, "تم تحديث البيانات بنجاح"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


# --- Attendance helpers ---

def delete_student(student_id):
    """Delete a student and their attendance records."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        conn.commit()
        return True, "تم حذف الطالب بنجاح"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


# --- Attendance helpers ---

def record_attendance(student_id, full_name, day, date, time):
    """Record a student's attendance. Returns (success, message)."""
    conn = get_db()
    try:
        # Check if already recorded today
        existing = conn.execute(
            "SELECT id FROM attendance WHERE student_id = ? AND date = ?",
            (student_id, date)
        ).fetchone()
        if existing:
            return False, "تم تسجيل حضور هذا الطالب مسبقاً اليوم"

        conn.execute(
            "INSERT INTO attendance (student_id, full_name, day, date, time) VALUES (?, ?, ?, ?, ?)",
            (student_id, full_name, day, date, time)
        )
        conn.commit()
        return True, "تم تسجيل الحضور بنجاح"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def get_attendance_today(date):
    """Get all attendance records for a given date."""
    conn = get_db()
    records = conn.execute(
        "SELECT * FROM attendance WHERE date = ? ORDER BY id DESC", (date,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in records]


def get_all_attendance():
    """Get all attendance records."""
    conn = get_db()
    records = conn.execute(
        "SELECT a.full_name, a.student_id, a.day, a.date, a.time, s.photo_url "
        "FROM attendance a "
        "LEFT JOIN students s ON a.student_id = s.student_id "
        "ORDER BY a.id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in records]


def get_student_attendance_count(student_id):
    """Get how many times a student attended."""
    conn = get_db()
    result = conn.execute(
        "SELECT COUNT(*) as count FROM attendance WHERE student_id = ?",
        (student_id,)
    ).fetchone()
    conn.close()
    return result['count'] if result else 0


def get_total_unique_dates():
    """Get total number of unique attendance dates (total sessions)."""
    conn = get_db()
    result = conn.execute(
        "SELECT COUNT(DISTINCT date) as count FROM attendance"
    ).fetchone()
    conn.close()
    return result['count'] if result else 0


# --- Admin helpers ---

def authenticate_admin(username, password):
    """Authenticate an admin. Returns admin dict or None."""
    conn = get_db()
    admin = conn.execute(
        "SELECT * FROM admins WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if admin and check_password_hash(admin['password_hash'], password):
        return dict(admin)
    return None
