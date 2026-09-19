import csv
import io
import os
import random
from datetime import datetime

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

# -----------------------------------------------------------------------------
# APP CONFIGURATION & REAL GMAIL SMTP (PORT 465 SSL)
# -----------------------------------------------------------------------------
import os
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message

base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(base_dir, 'templates'),
    static_folder=os.path.join(base_dir, 'static'),
    static_url_path='/static'
)

app.config['SECRET_KEY'] = 'UniTrack-super-secret-key-2026'

# Serverless-safe SQLite database path in /tmp
db_path = os.path.join(tempfile.gettempdir(), 'campus_maintenance.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Gmail SMTP Configuration
MY_GMAIL = 'sandelakumar06@gmail.com'
MY_APP_PASSWORD = 'reiluirzdawrjaxj'

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = MY_GMAIL
app.config['MAIL_PASSWORD'] = MY_APP_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = ('UniTrack Support', MY_GMAIL)

mail = Mail(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

BUILDINGS = ['Block A', 'Block B', 'Block C', 'Computer Lab', 'Library', 'Hostel Block']
CATEGORIES = ['Electrical', 'Furniture', 'Plumbing', 'IT', 'Internet', 'Cleaning', 'AC/Cooling']
STATUSES = ['Pending', 'In Progress', 'Resolved']
# -----------------------------------------------------------------------------
# DATABASE MODELS
# -----------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)  # Full Student Name / Staff Handle
    course = db.Column(db.String(50), nullable=True)                  # B.Tech, BCA, MCA, etc.
    department = db.Column(db.String(50), nullable=True)              # CSE, ECE, Mechanical, etc.
    specialization = db.Column(db.String(80), nullable=True)          # AI, AIML, Data Science, etc.
    year_semester = db.Column(db.String(50), nullable=True)           # e.g., 2nd Year (Sem 3)
    mobile_no = db.Column(db.String(15), nullable=True)               # 10-digit phone
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(30), default='Student')                # Student, Department, Admin
    department_name = db.Column(db.String(50), nullable=True)         # For Maintenance Staff accounts

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Complaint(db.Model):
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.String(20), unique=True, nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    student_email = db.Column(db.String(120), nullable=True)
    department = db.Column(db.String(50), nullable=False)            # Course / Dept Info
    building = db.Column(db.String(50), nullable=False)
    room_no = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)              # Maintenance Category
    priority = db.Column(db.String(20), default='Medium')
    problem = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default='Pending')
    date = db.Column(db.String(20), default=lambda: datetime.utcnow().strftime('%Y-%m-%d'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    maintenance = db.relationship('Maintenance', backref='complaint', uselist=False, cascade='all, delete-orphan')

    @property
    def support_count(self):
        return ComplaintSupport.query.filter_by(complaint_id=self.id).count()


class ComplaintSupport(db.Model):
    __tablename__ = 'complaint_supports'
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


class Maintenance(db.Model):
    __tablename__ = 'maintenance'
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    staff_name = db.Column(db.String(100), default='Unassigned')
    action_taken = db.Column(db.Text, default='None')
    repair_cost = db.Column(db.Float, default=0.0)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -----------------------------------------------------------------------------
# AUTHENTICATION & STUDENT REGISTRATION WITH OTP
# -----------------------------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        course = request.form.get('course', '').strip()
        dept = request.form.get('department', '').strip()
        specialization = request.form.get('specialization', '').strip() if dept == 'CSE' else 'None'
        year_semester = request.form.get('year_semester', '').strip()
        mobile_no = request.form.get('mobile_no', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if password != confirm_password:
            flash('Passwords do not match. Please re-enter your password.', 'danger')
            return redirect(url_for('register'))

        if not (mobile_no.isdigit() and len(mobile_no) == 10):
            flash('Please enter a valid 10-digit mobile number.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=full_name).first():
            flash('This full name is already registered. Please use a unique handle or initial.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email address already registered. Please sign in.', 'danger')
            return redirect(url_for('register'))

        otp = f"{random.randint(100000, 999999)}"

        session['pending_user'] = {
            'username': full_name,
            'course': course,
            'department': dept,
            'specialization': specialization,
            'year_semester': year_semester,
            'mobile_no': mobile_no,
            'email': email,
            'password_hash': generate_password_hash(password),
            'otp': otp
        }

        try:
            msg = Message(
                subject='UniTrack - Student Registration OTP',
                recipients=[email],
                body=(
                    f"Hello {full_name},\n\n"
                    f"Your 6-digit UniTrack verification code is: {otp}\n\n"
                    f"Academic Profile:\n"
                    f"- Course: {course}\n"
                    f"- Department: {dept}\n"
                    f"- Specialization: {specialization}\n"
                    f"- Year/Semester: {year_semester}\n\n"
                    "Enter this code on the verification screen to activate your account."
                )
            )
            mail.send(msg)
            flash(f'Verification code dispatched to {email}. Check your inbox.', 'success')
            return redirect(url_for('verify_email'))
        except Exception as e:
            print('\n' + '=' * 50)
            print(f'>>> SMTP ERROR: {repr(e)}')
            print(f'>>> CONSOLE BACKUP OTP FOR {email}: {otp} <<<')
            print('=' * 50 + '\n', flush=True)
            flash(f'Email dispatch issue encountered. For testing, check the server console for OTP: {otp}', 'warning')
            return redirect(url_for('verify_email'))

    return render_template('register.html')


@app.route('/verify-email', methods=['GET', 'POST'])
@app.route('/verify_email', methods=['GET', 'POST'])
def verify_email():
    pending = session.get('pending_user')
    if not pending:
        flash('No pending registration found. Please register first.', 'warning')
        return redirect(url_for('register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()

        if entered_otp == pending['otp']:
            new_user = User(
                username=pending['username'],
                course=pending['course'],
                department=pending['department'],
                specialization=pending['specialization'],
                year_semester=pending['year_semester'],
                mobile_no=pending['mobile_no'],
                email=pending['email'],
                password_hash=pending['password_hash'],
                role='Student'
            )
            db.session.add(new_user)
            db.session.commit()

            session.pop('pending_user', None)
            flash('Email verified! Your account is now active. Please sign in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Incorrect verification code. Please check and try again.', 'danger')

    return render_template('verify_email.html', email=pending['email'])


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('home'))

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home'))


@app.route('/change-password', methods=['GET', 'POST'])
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(old_password):
            flash('Current password incorrect.', 'danger')
            return redirect(url_for('change_password'))

        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('change_password'))

        current_user.set_password(new_password)
        db.session.commit()
        flash('Password updated successfully.', 'success')
        return redirect(url_for('home'))

    return render_template('change_password.html')


@app.route('/student/edit-profile', methods=['POST'])
@login_required
def edit_student_profile():
    if current_user.role != 'Student':
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('home'))

    course = request.form.get('course', '').strip()
    dept = request.form.get('department', '').strip()
    specialization = request.form.get('specialization', '').strip() if dept == 'CSE' else 'None'
    year_semester = request.form.get('year_semester', '').strip()
    mobile_no = request.form.get('mobile_no', '').strip()

    if not (mobile_no.isdigit() and len(mobile_no) == 10):
        flash('Please enter a valid 10-digit mobile number.', 'danger')
        return redirect(url_for('student_dashboard'))

    current_user.course = course
    current_user.department = dept
    current_user.specialization = specialization
    current_user.year_semester = year_semester
    current_user.mobile_no = mobile_no

    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('student_dashboard'))

# -----------------------------------------------------------------------------
# TICKETING & COMPLAINTS WORKFLOW
# -----------------------------------------------------------------------------
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def home(path=""):
    try:
        # Calculate metric card counts
        total_complaints = Complaint.query.count()
        pending_count = Complaint.query.filter_by(status='Pending').count()
        in_progress_count = Complaint.query.filter_by(status='In Progress').count()
        resolved_count = Complaint.query.filter_by(status='Resolved').count()

        # Fetch the most recent 10 tickets for the campus activity table
        recent_tickets = Complaint.query.order_by(Complaint.id.desc()).limit(10).all()
    except Exception:
        total_complaints = 0
        pending_count = 0
        in_progress_count = 0
        resolved_count = 0
        recent_tickets = []

    return render_template(
        'index.html',
        total=total_complaints,
        pending=pending_count,
        in_progress=in_progress_count,
        resolved=resolved_count,
        tickets=recent_tickets
    )

@app.route('/report', methods=['GET', 'POST'])
@app.route('/report-problem', methods=['GET', 'POST'])
@app.route('/report_problem', methods=['GET', 'POST'])
@login_required
def report_problem():
    if request.method == 'POST':
        building = request.form.get('building', '')
        room_no = request.form.get('room_no', '').strip()
        category = request.form.get('category', '')
        priority = request.form.get('priority', 'Medium')
        problem_desc = request.form.get('problem', '').strip()

        total_tickets = Complaint.query.count() + 1
        generated_id = f"CMP{total_tickets:03d}"

        student_info = f"{current_user.course} - {current_user.department}" if current_user.course else 'General'

        new_complaint = Complaint(
            complaint_id=generated_id,
            student_name=current_user.username,
            student_email=current_user.email,
            department=student_info,
            building=building,
            room_no=room_no,
            category=category,
            priority=priority,
            problem=problem_desc,
            status='Pending'
        )
        db.session.add(new_complaint)
        db.session.flush()

        initial_maint = Maintenance(
            complaint_id=new_complaint.id,
            staff_name='Unassigned',
            action_taken='Logged into system',
            repair_cost=0.0
        )
        db.session.add(initial_maint)
        db.session.commit()

        flash(f'Ticket {generated_id} submitted successfully!', 'success')
        return redirect(url_for('browse_problems'))

    return render_template('report_problem.html', buildings=BUILDINGS, categories=CATEGORIES)


@app.route('/problems')
@app.route('/browse-problems')
@app.route('/browse_problems')
@login_required
def browse_problems():
    # Sorted ascending: CMP001, CMP002, ...
    complaints = Complaint.query.order_by(Complaint.id.asc()).all()
    user_supported_ids = [
        s.complaint_id for s in ComplaintSupport.query.filter_by(user_id=current_user.id).all()
    ]
    return render_template(
        'browse_problems.html',
        complaints=complaints,
        user_supported_ids=user_supported_ids
    )


@app.route('/support_problem', methods=['POST'])
@login_required
def support_problem():
    complaint_id = request.form.get('complaint_id')
    if not complaint_id:
        flash('Ticket identifier missing.', 'danger')
        return redirect(url_for('browse_problems'))

    complaint = Complaint.query.get_or_404(int(complaint_id))

    # Reject upvoting if the issue is already resolved
    if complaint.status == 'Resolved':
        flash('This issue has already been resolved and closed.', 'warning')
        return redirect(request.referrer or url_for('browse_problems'))

    existing = ComplaintSupport.query.filter_by(
        complaint_id=complaint.id,
        user_id=current_user.id
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('You unmarked this issue.', 'info')
    else:
        new_support = ComplaintSupport(complaint_id=complaint.id, user_id=current_user.id)
        db.session.add(new_support)
        db.session.commit()
        flash('Marked that you are also facing this problem!', 'success')

    return redirect(request.referrer or url_for('browse_problems'))


@app.route('/ticket/delete/', methods=['POST'])
@login_required
def delete_ticket(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)

    # Permission check: student owner or admin
    if current_user.role != 'Admin' and complaint.student_name != current_user.username:
        flash('Unauthorized action. You can only delete tickets you created.', 'danger')
        return redirect(request.referrer or url_for('student_dashboard'))

    ComplaintSupport.query.filter_by(complaint_id=complaint.id).delete()
    db.session.delete(complaint)
    db.session.commit()

    flash(f'Ticket {complaint.complaint_id} was deleted successfully.', 'info')
    return redirect(request.referrer or url_for('student_dashboard'))

# -----------------------------------------------------------------------------
# PORTALS (STUDENT, DEPARTMENT, ADMIN)
# -----------------------------------------------------------------------------
@app.route('/student/dashboard')
@app.route('/student_dashboard')
@login_required
def student_dashboard():
    # Sorted ascending: CMP001, CMP002, ...
    my_complaints = Complaint.query.filter_by(student_name=current_user.username).order_by(Complaint.id.asc()).all()
    return render_template('student_dashboard.html', my_complaints=my_complaints)


@app.route('/department')
@app.route('/department/portal')
@app.route('/department_portal')
@login_required
def department_portal():
    dept_name = current_user.department_name or 'Electrical'
    # Sorted ascending: CMP001, CMP002, ...
    complaints = Complaint.query.filter_by(category=dept_name).order_by(Complaint.id.asc()).all()
    return render_template('department_portal.html', complaints=complaints, statuses=STATUSES)


@app.route('/update_status', methods=['POST'])
@login_required
def update_status():
    complaint_id = request.form.get('complaint_id')
    if not complaint_id:
        flash('Missing ticket ID.', 'danger')
        return redirect(url_for('department_portal'))

    complaint = Complaint.query.get_or_404(int(complaint_id))

    # Reject updates if already resolved
    if complaint.status == 'Resolved':
        flash('This ticket is already resolved and locked from further edits.', 'warning')
        return redirect(url_for('department_portal'))

    new_status = request.form.get('status')
    staff_name = request.form.get('staff_name')
    remarks = request.form.get('remarks')
    cost_str = request.form.get('cost')

    if new_status:
        complaint.status = new_status

    maint = Maintenance.query.filter_by(complaint_id=complaint.id).first()
    if not maint:
        maint = Maintenance(complaint_id=complaint.id)
        db.session.add(maint)

    if staff_name:
        maint.staff_name = staff_name
    if remarks:
        maint.action_taken = remarks
    if cost_str:
        try:
            maint.repair_cost = float(cost_str)
        except ValueError:
            maint.repair_cost = 0.0

    db.session.commit()
    flash(f'Ticket {complaint.complaint_id} updated successfully!', 'success')
    return redirect(url_for('department_portal'))


@app.route('/admin')
@app.route('/admin/portal')
@app.route('/admin_portal')
@login_required
def admin_portal():
    if current_user.role != 'Admin':
        flash('Admin authorization required.', 'danger')
        return redirect(url_for('home'))

    # Student Filter & Search
    student_search = request.args.get('student_search', '').strip()
    selected_dept = request.args.get('department_filter', '').strip()

    student_query = User.query.filter_by(role='Student')
    if student_search:
        student_query = student_query.filter(
            (User.username.ilike(f"%{student_search}%")) |
            (User.email.ilike(f"%{student_search}%")) |
            (User.mobile_no.ilike(f"%{student_search}%"))
        )
    if selected_dept:
        student_query = student_query.filter_by(department=selected_dept)

    students_list = student_query.order_by(User.id.desc()).all()

    student_records = []
    for s in students_list:
        ticket_count = Complaint.query.filter_by(student_name=s.username).count()
        student_records.append({
            'user': s,
            'ticket_count': ticket_count
        })

    all_departments = ['CSE', 'ECE', 'Mechanical', 'Civil', 'IT', 'Management']

    # Staff / Department Directory Data
    staff_users = User.query.filter_by(role='Department').all()
    department_staff_records = []
    for staff in staff_users:
        dept_name = staff.department_name or 'General'
        assigned_tickets = Complaint.query.filter_by(category=dept_name).count()
        resolved_tickets = Complaint.query.filter_by(category=dept_name, status='Resolved').count()
        department_staff_records.append({
            'staff': staff,
            'dept_name': dept_name,
            'assigned_count': assigned_tickets,
            'resolved_count': resolved_tickets
        })

    # Maintenance & Cost Analytics (Sorted ascending)
    complaints = Complaint.query.order_by(Complaint.id.asc()).all()
    total = len(complaints)
    pending = len([c for c in complaints if c.status == 'Pending'])
    in_progress = len([c for c in complaints if c.status == 'In Progress'])
    resolved = len([c for c in complaints if c.status in ('Resolved', 'Closed')])

    all_maint = Maintenance.query.all()
    total_cost = sum(m.repair_cost for m in all_maint if m.repair_cost)
    avg_cost = (total_cost / total) if total > 0 else 0.0

    cat_counts = [Complaint.query.filter_by(category=cat).count() for cat in CATEGORIES]
    bldg_counts = [Complaint.query.filter_by(building=bldg).count() for bldg in BUILDINGS]

    cost_counts = []
    for cat in CATEGORIES:
        cat_complaint_ids = [c.id for c in Complaint.query.filter_by(category=cat).all()]
        cat_cost = sum(m.repair_cost for m in Maintenance.query.filter(Maintenance.complaint_id.in_(cat_complaint_ids)).all() if m.repair_cost)
        cost_counts.append(cat_cost)

    top_cat_idx = cat_counts.index(max(cat_counts)) if total > 0 else 0
    top_bldg_idx = bldg_counts.index(max(bldg_counts)) if total > 0 else 0

    metrics = {
        'total': total,
        'pending': pending,
        'in_progress': in_progress,
        'resolved': resolved,
        'total_cost': total_cost,
        'avg_cost': avg_cost,
        'top_category': CATEGORIES[top_cat_idx] if total > 0 else 'N/A',
        'top_building': BUILDINGS[top_bldg_idx] if total > 0 else 'N/A'
    }

    chart_data = {
        'category_counts': cat_counts,
        'bldg_counts': bldg_counts,
        'cost_counts': cost_counts
    }

    return render_template(
        'admin_portal.html',
        complaints=complaints,
        metrics=metrics,
        chart_data=chart_data,
        categories=CATEGORIES,
        student_records=student_records,
        all_departments=all_departments,
        student_search=student_search,
        selected_dept=selected_dept,
        department_staff_records=department_staff_records
    )


@app.route('/admin/reassign/', methods=['POST'])
@login_required
def admin_reassign(complaint_id):
    if current_user.role != 'Admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('home'))

    complaint = Complaint.query.get_or_404(complaint_id)
    new_cat = request.form.get('category')
    if new_cat:
        complaint.category = new_cat
        db.session.commit()
        flash(f'Ticket {complaint.complaint_id} reassigned to {new_cat}.', 'success')

    return redirect(url_for('admin_portal'))

@app.route('/export/csv')
@app.route('/admin/export-csv')
@app.route('/admin/export_csv')
@login_required
def export_csv():
    if current_user.role != 'Admin':
        flash('Unauthorized.', 'danger')
        return redirect(url_for('home'))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Ticket ID', 'Student Name', 'Course & Department', 'Student Email', 
        'Building', 'Room', 'Category', 'Priority', 
        'Status', 'Date', 'Staff', 'Repair Cost (INR)', 'Action Taken'
    ])

    for c in Complaint.query.order_by(Complaint.id.asc()).all():
        maint = Maintenance.query.filter_by(complaint_id=c.id).first()
        
        # Format the date safely
        if c.created_at:
            date_str = c.created_at.strftime('%Y-%m-%d')
        elif c.date:
            date_str = str(c.date)
        else:
            date_str = 'N/A'

        writer.writerow([
            c.complaint_id,
            c.student_name,
            c.department,
            c.student_email or 'N/A',
            c.building,
            c.room_no,
            c.category,
            c.priority,
            c.status,
            date_str,
            maint.staff_name if maint else 'Unassigned',
            maint.repair_cost if maint else 0.0,
            maint.action_taken if maint else 'None'
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=campus_maintenance_report.csv'}
    )
# -----------------------------------------------------------------------------
# DATABASE SEEDER (SEEDS ADMIN & DEPARTMENT STAFF)
# -----------------------------------------------------------------------------
def init_db():
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(username='admin').first():
            db.session.add(User(
                username='admin',
                email='admin@campus.edu',
                password_hash=generate_password_hash('admin123'),
                role='Admin'
            ))

        if not User.query.filter_by(username='elec_staff').first():
            db.session.add(User(
                username='elec_staff',
                email='electric@campus.edu',
                password_hash=generate_password_hash('dept123'),
                role='Department',
                department_name='Electrical'
            ))

        if not User.query.filter_by(username='it_staff').first():
            db.session.add(User(
                username='it_staff',
                email='it@campus.edu',
                password_hash=generate_password_hash('dept123'),
                role='Department',
                department_name='IT'
            ))

        if not User.query.filter_by(username='plumb_staff').first():
            db.session.add(User(
                username='plumb_staff',
                email='plumbing@campus.edu',
                password_hash=generate_password_hash('dept123'),
                role='Department',
                department_name='Plumbing'
            ))

        if not User.query.filter_by(username='clean_staff').first():
            db.session.add(User(
                username='clean_staff',
                email='cleaning@campus.edu',
                password_hash=generate_password_hash('dept123'),
                role='Department',
                department_name='Cleaning'
            ))

        if not User.query.filter_by(username='ac_staff').first():
            db.session.add(User(
                username='ac_staff',
                email='ac@campus.edu',
                password_hash=generate_password_hash('dept123'),
                role='Department',
                department_name='AC/Cooling'
            ))      

        if not User.query.filter_by(username='internet_staff').first():
            db.session.add(User(
                username='internet_staff',
                email='internet@campus.edu',
                password_hash=generate_password_hash('dept123'),
                role='Department',
                department_name='Internet'
            ))

        if not User.query.filter_by(username='furniture_staff').first():
            db.session.add(User(
                username='furniture_staff',
                email='furniture@campus.edu',
                password_hash=generate_password_hash('dept123'),
                role='Department',
                department_name='Furniture'
            ))

        db.session.commit()

# Runs database table creation and account seeding on Vercel startup
with app.app_context():
    init_db()

# Only runs when testing locally on your computer
if __name__ == '__main__':
    app.run(debug=True, port=5000)
