import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from replit import db
except ImportError:
    import json
    class LocalDB(dict):
        def __init__(self, filename='db.json'):
            super().__init__()
            self.filename = filename
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    self.update(json.load(f))
        def __setitem__(self, key, value):
            super().__setitem__(key, value)
            with open(self.filename, 'w') as f:
                json.dump(self, f)
    db = LocalDB()

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'super_secret_key')

if "users" not in db: db["users"] = {}
if "attendance" not in db: db["attendance"] = []
if "tasks" not in db: db["tasks"] = []
if "payments" not in db: db["payments"] = []
if "departments" not in db: db["departments"] = ["Designers", "Menu Upload", "Finance", "Customer Handling"]

@app.context_processor
def inject_user():
    user = None
    if 'username' in session:
        user = dict(db["users"]).get(session['username'])
    return dict(current_user=user)

def login_required(f):
    def wrap(*args, **kwargs):
        if 'username' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

def admin_required(f):
    def wrap(*args, **kwargs):
        user = dict(db["users"]).get(session.get('username'))
        if not user or user.get('role') != 'admin': return "Unauthorized", 403
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route('/')
def index():
    if not db["users"]: return redirect(url_for('setup'))
    if 'username' in session:
        user = dict(db["users"]).get(session['username'])
        if user and user.get('role') == 'admin': return redirect(url_for('admin_dashboard'))
        return redirect(url_for('member_dashboard'))
    return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if db["users"]: return redirect(url_for('login'))
    if request.method == 'POST':
        users = dict(db["users"])
        users[request.form['username']] = {
            "username": request.form['username'],
            "password": generate_password_hash(request.form['password']),
            "role": "admin",
            "department": "Admin",
            "contact": "",
            "profile_image": ""
        }
        db["users"] = users
        flash("Admin created. Please login.")
        return redirect(url_for('login'))
    return render_template('setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not db["users"]: return redirect(url_for('setup'))
    if request.method == 'POST':
        u = request.form['username']
        users = dict(db["users"])
        if u in users and check_password_hash(users[u]['password'], request.form['password']):
            session['username'] = u
            return redirect(url_for('index'))
        flash("Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html', users_count=len(db["users"]), tasks_count=len(db["tasks"]))

@app.route('/member')
@login_required
def member_dashboard():
    return render_template('member_dashboard.html')

@app.route('/users', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_users():
    users = dict(db["users"])
    departments = list(db["departments"])
    if request.method == 'POST':
        action = request.form.get('action')
        u = request.form.get('username')
        if action == 'add' and u not in users:
            users[u] = {
                "username": u,
                "password": generate_password_hash(request.form.get('password')),
                "role": request.form.get('role'),
                "department": request.form.get('department'),
                "contact": "",
                "profile_image": ""
            }
        elif action == 'delete' and u in users and users[u]['role'] != 'admin':
            del users[u]
        elif action == 'reset_password' and u in users:
            users[u]['password'] = generate_password_hash(request.form.get('password'))
        db["users"] = users
        return redirect(url_for('manage_users'))
    return render_template('users.html', users=users.values(), departments=departments)

@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    u = session['username']
    users = dict(db["users"])
    user = users.get(u)
    records = list(db["attendance"])
    departments = list(db["departments"])
    
    if request.method == 'POST':
        action = request.form.get('action')
        now = datetime.now()
        d_str = now.strftime("%Y-%m-%d")
        t_str = now.strftime("%H:%M")
        
        today_record = next((r for r in records if r['username'] == u and r['date'] == d_str), None)
        
        if action == 'check_in' and not today_record:
            records.append({
                "id": str(uuid.uuid4()), "username": u, "date": d_str,
                "time_in": t_str, "time_out": "", "total_hours": 0
            })
            db["attendance"] = records
        elif action == 'check_out' and today_record and not today_record['time_out']:
            today_record['time_out'] = t_str
            t_in = datetime.strptime(today_record['time_in'], "%H:%M")
            t_out = datetime.strptime(t_str, "%H:%M")
            today_record['total_hours'] = round((t_out - t_in).total_seconds() / 3600, 2)
            db["attendance"] = records
        return redirect(url_for('attendance'))
        
    if user['role'] == 'admin':
        f_date, f_user, f_dept = request.args.get('date'), request.args.get('member'), request.args.get('department')
        filtered = records
        if f_date: filtered = [r for r in filtered if r['date'] == f_date]
        if f_user: filtered = [r for r in filtered if r['username'] == f_user]
        if f_dept: 
            dept_users = [usr['username'] for usr in users.values() if usr.get('department') == f_dept]
            filtered = [r for r in filtered if r['username'] in dept_users]
        return render_template('attendance_admin.html', records=filtered, users=users.values(), departments=departments)
    
    return render_template('attendance_member.html', records=[r for r in records if r['username'] == u])

@app.route('/tasks', methods=['GET', 'POST'])
@login_required
def tasks():
    u = session['username']
    users = dict(db["users"])
    user = users.get(u)
    tasks_list = list(db["tasks"])
    departments = list(db["departments"])
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            tasks_list.append({
                "id": str(uuid.uuid4()), "username": u,
                "title": request.form.get('title'),
                "description": request.form.get('description'),
                "status": "Pending"
            })
        elif action == 'update':
            t_id = request.form.get('id')
            for t in tasks_list:
                if t['id'] == t_id and (user['role'] == 'admin' or t['username'] == u):
                    t['status'] = request.form.get('status')
        elif action == 'delete':
            tasks_list = [t for t in tasks_list if not (t['id'] == request.form.get('id') and (user['role'] == 'admin' or t['username'] == u))]
        db["tasks"] = tasks_list
        return redirect(url_for('tasks'))
        
    if user['role'] == 'admin':
        f_user, f_dept, f_status = request.args.get('member'), request.args.get('department'), request.args.get('status')
        filtered = tasks_list
        if f_user: filtered = [t for t in filtered if t['username'] == f_user]
        if f_status: filtered = [t for t in filtered if t['status'] == f_status]
        if f_dept:
            dept_users = [usr['username'] for usr in users.values() if usr.get('department') == f_dept]
            filtered = [t for t in filtered if t['username'] in dept_users]
        return render_template('tasks_admin.html', tasks=filtered, users=users.values(), departments=departments)
    
    return render_template('tasks_member.html', tasks=[t for t in tasks_list if t['username'] == u])

@app.route('/payments', methods=['GET', 'POST'])
@login_required
def payments():
    users = dict(db["users"])
    user = users.get(session['username'])
    pay_list = list(db["payments"])
    
    if request.method == 'POST' and user['role'] == 'admin':
        action = request.form.get('action')
        if action == 'add':
            pay_list.append({
                "id": str(uuid.uuid4()), "username": request.form.get('username'),
                "amount": request.form.get('amount'), "status": request.form.get('status'),
                "reason": request.form.get('reason', ''), "date": request.form.get('date', datetime.now().strftime("%Y-%m-%d"))
            })
        elif action == 'update':
            for p in pay_list:
                if p['id'] == request.form.get('id'):
                    p['status'] = request.form.get('status')
                    p['reason'] = request.form.get('reason', '')
        db["payments"] = pay_list
        return redirect(url_for('payments'))
        
    if user['role'] == 'admin':
        return render_template('payments_admin.html', payments=pay_list, users=users.values())
    return render_template('payments_member.html', payments=[p for p in pay_list if p['username'] == user['username']])

@app.route('/departments', methods=['GET', 'POST'])
@login_required
@admin_required
def departments():
    depts = list(db["departments"])
    if request.method == 'POST':
        action = request.form.get('action')
        d = request.form.get('department')
        if action == 'add' and d and d not in depts: depts.append(d)
        elif action == 'delete' and d in depts: depts.remove(d)
        db["departments"] = depts
        return redirect(url_for('departments'))
    return render_template('departments.html', departments=depts)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    users = dict(db["users"])
    u = session['username']
    user = users.get(u)
    
    if request.method == 'POST':
        user['contact'] = request.form.get('contact', '')
        if request.form.get('profile_image'):
            user['profile_image'] = request.form.get('profile_image')
        users[u] = user
        db["users"] = users
        flash("Profile updated")
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
