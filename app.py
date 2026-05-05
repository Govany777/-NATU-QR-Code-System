"""
NATU Attendance Recording System - Flask Application
Main server file handling all routes and API endpoints.
"""

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, flash
)
from database import (
    init_db, register_student, authenticate_student, get_student_by_id,
    get_all_students, record_attendance, get_attendance_today,
    get_all_attendance, get_student_attendance_count,
    get_total_unique_dates, authenticate_admin,
    update_student_photo, update_student_profile,
    delete_student
)
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import uuid

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Upload config - Use /tmp on Vercel
if os.environ.get('VERCEL'):
    UPLOAD_FOLDER = '/tmp/uploads'
else:
    UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Initialize DB on startup
init_db()


# ==========================================
# Page Routes
# ==========================================

@app.route('/')
def index():
    """Home page."""
    return render_template('index.html')


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page and handler."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        admin = authenticate_admin(username, password)
        if admin:
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            return jsonify({'success': True, 'message': 'تم تسجيل الدخول بنجاح'})
        else:
            return jsonify({'success': False, 'message': 'اسم المستخدم أو كلمة المرور غير صحيحة'}), 401

    return render_template('admin-login.html')


@app.route('/admin-dashboard')
def admin_dashboard():
    """Admin dashboard - shows students and attendance."""
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    students = get_all_students()
    attendance = get_all_attendance()
    return render_template('admin-dashboard.html',
                           students=students,
                           attendance=attendance)


@app.route('/student-login', methods=['GET', 'POST'])
def student_login():
    """Student login page and handler."""
    if request.method == 'POST':
        full_name = request.form.get('fullName', '').strip()
        password = request.form.get('password', '')

        student = authenticate_student(full_name, password)
        if student:
            session['student_id'] = student['student_id']
            session['student_name'] = student['full_name']
            session['student_db_id'] = student['id']
            return jsonify({'success': True, 'redirect': url_for('student_dashboard')})
        else:
            return jsonify({'success': False, 'message': 'خطأ في الاسم الكامل أو كلمة المرور'}), 401

    return render_template('student-login.html')


@app.route('/student-registration', methods=['GET', 'POST'])
def student_registration():
    """Student registration page and handler."""
    if request.method == 'POST':
        full_name = request.form.get('fullName', '').strip()
        department = request.form.get('department', '').strip()
        academic_year = request.form.get('academicYear', '').strip()
        section = request.form.get('section', '').strip()
        student_id = request.form.get('studentId', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirmPassword', '')

        # Validation
        if not all([full_name, department, academic_year, section, student_id, password, confirm_password]):
            return jsonify({'success': False, 'message': 'الرجاء ملء جميع الحقول المطلوبة'}), 400

        if password != confirm_password:
            return jsonify({'success': False, 'message': 'كلمات المرور غير متطابقة'}), 400

        if len(password) < 6:
            return jsonify({'success': False, 'message': 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'}), 400

        success, message = register_student(
            student_id, full_name, department, academic_year, section, password
        )

        if success:
            session['student_id'] = student_id
            session['student_name'] = full_name
            return jsonify({'success': True, 'redirect': url_for('student_dashboard')})
        else:
            return jsonify({'success': False, 'message': message}), 400

    return render_template('student-registration.html')


@app.route('/student-dashboard')
def student_dashboard():
    """Student dashboard with profile, QR code, and stats."""
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    student = get_student_by_id(session['student_id'])
    if not student:
        session.clear()
        return redirect(url_for('student_login'))

    attendance_count = get_student_attendance_count(student['student_id'])
    total_sessions = get_total_unique_dates()
    attendance_pct = round((attendance_count / total_sessions * 100)) if total_sessions > 0 else 0

    return render_template('student-dashboard.html',
                           student=student,
                           attendance_count=attendance_count,
                           attendance_pct=attendance_pct,
                           total_sessions=total_sessions)


@app.route('/attendance')
def attendance():
    """Attendance scanning/search page."""
    return render_template('attendance.html')


# ==========================================
# API Routes
# ==========================================

@app.route('/api/attendance/scan', methods=['POST'])
def api_attendance_scan():
    """Look up a student by scanned QR code data (student_id)."""
    data = request.get_json()
    scanned_id = data.get('student_id', '').strip()

    if not scanned_id:
        return jsonify({'success': False, 'message': 'لم يتم قراءة بيانات'}), 400

    student = get_student_by_id(scanned_id)
    if student:
        return jsonify({
            'success': True,
            'student': {
                'student_id': student['student_id'],
                'full_name': student['full_name'],
                'department': student['department'],
                'academic_year': student['academic_year'],
                'section': student['section'],
                'photo_url': student.get('photo_url')
            }
        })
    else:
        return jsonify({'success': False, 'message': 'لم يتم العثور على الطالب'}), 404


@app.route('/api/attendance/search', methods=['POST'])
def api_attendance_search():
    """Search for a student by ID (manual search)."""
    data = request.get_json()
    search_id = data.get('student_id', '').strip()

    if not search_id:
        return jsonify({'success': False, 'message': 'الرجاء إدخال رقم تعريفي'}), 400

    student = get_student_by_id(search_id)
    if student:
        return jsonify({
            'success': True,
            'student': {
                'student_id': student['student_id'],
                'full_name': student['full_name'],
                'department': student['department'],
                'academic_year': student['academic_year'],
                'section': student['section'],
                'photo_url': student.get('photo_url')
            }
        })
    else:
        return jsonify({'success': False, 'message': 'لم يتم العثور على الطالب'}), 404


@app.route('/api/attendance/confirm', methods=['POST'])
def api_attendance_confirm():
    """Confirm and record a student's attendance."""
    data = request.get_json()
    student_id = data.get('student_id', '').strip()

    if not student_id:
        return jsonify({'success': False, 'message': 'بيانات غير صالحة'}), 400

    student = get_student_by_id(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'الطالب غير موجود'}), 404

    now = datetime.now()
    days_ar = ['الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
    day_name = days_ar[now.weekday()]
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')

    success, message = record_attendance(
        student['student_id'], student['full_name'],
        day_name, date_str, time_str
    )

    if success:
        return jsonify({'success': True, 'message': f"تم تسجيل حضور: {student['full_name']}"})
    else:
        return jsonify({'success': False, 'message': message}), 409


@app.route('/api/attendance/today')
def api_attendance_today():
    """Get today's attendance list."""
    today = datetime.now().strftime('%Y-%m-%d')
    records = get_attendance_today(today)
    return jsonify({
        'count': len(records),
        'records': records
    })


@app.route('/api/admin/delete_student', methods=['POST'])
def api_delete_student():
    """Delete a student and their attendance records."""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'غير مصرح لك القيام بهذا الإجراء'}), 401

    data = request.get_json()
    student_id = data.get('student_id', '').strip()

    if not student_id:
        return jsonify({'success': False, 'message': 'بيانات غير صالحة'}), 400

    success, message = delete_student(student_id)

    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 500


@app.route('/api/student/upload-photo', methods=['POST'])
def api_upload_photo():
    """Upload a student photo."""
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'غير مسجل دخول'}), 401

    if 'photo' not in request.files:
        return jsonify({'success': False, 'message': 'لم يتم اختيار صورة'}), 400

    file = request.files['photo']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'لم يتم اختيار صورة'}), 400

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{session['student_id']}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        photo_url = f"uploads/{filename}"
        success, msg = update_student_photo(session['student_id'], photo_url)

        if success:
            return jsonify({'success': True, 'photo_url': url_for('static', filename=photo_url)})
        else:
            return jsonify({'success': False, 'message': msg}), 500
    else:
        return jsonify({'success': False, 'message': 'نوع الملف غير مدعوم. الأنواع المدعومة: PNG, JPG, JPEG, GIF, WEBP'}), 400


@app.route('/api/student/update-profile', methods=['POST'])
def api_update_profile():
    """Update student profile data."""
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'غير مسجل دخول'}), 401

    data = request.get_json()
    full_name = data.get('full_name', '').strip() or None
    department = data.get('department', '').strip() or None
    academic_year = data.get('academic_year', '').strip() or None
    section = data.get('section', '').strip() or None
    new_password = data.get('new_password', '').strip() or None

    if new_password and len(new_password) < 6:
        return jsonify({'success': False, 'message': 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'}), 400

    success, message = update_student_profile(
        session['student_id'], full_name, department, academic_year, section, new_password
    )

    if success and full_name:
        session['student_name'] = full_name

    return jsonify({'success': success, 'message': message})


@app.route('/logout')
def logout():
    """Clear session and redirect to home."""
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
