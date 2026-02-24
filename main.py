import os
import uuid
from datetime import datetime, timedelta
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
                    try:
                        data = json.load(f)
                        self.update(data)
                    except json.JSONDecodeError:
                        pass
        def __setitem__(self, key, value):
            super().__setitem__(key, value)
            with open(self.filename, 'w') as f:
                json.dump(dict(self), f)
    db = LocalDB()

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'super_secret_key')

if "users" not in db: db["users"] = {}
if "attendance" not in db: db["attendance"] = []
if "tasks" not in db: db["tasks"] = []
if "departments" not in db: db["departments"] = ["Designers", "Menu Upload", "Finance", "Customer Handling"]
if "customers" not in db: db["customers"] = []
if "notices" not in db: db["notices"] = []

@app.context_processor
def inject_user():
    user = None
    notifications = []
    selected_date = request.args.get('global_date', datetime.now().strftime("%Y-%m-%d"))
    if 'username' in session:
        users = dict(db["users"])
        user = users.get(session['username'])
        if user:
            notices = list(db["notices"])
            notifications = [n for n in notices if n['target'] == 'all' or n['target'] == session['username']]
    return dict(current_user=user, notifications=notifications, global_date=selected_date)

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

def has_permission(user, target_dept, action='view'):
    if user['role'] == 'admin': return True
    permissions = user.get('permissions', {})
    dept_perms = permissions.get(target_dept, [])
    if action in dept_perms or 'all' in dept_perms: return True
    if user['role'] == 'leader' and user['department'] == target_dept: return True
    return False

@app.route('/')
def index():
    if not db["users"]: return redirect(url_for('setup'))
    if 'username' in session:
        user = dict(db["users"]).get(session['username'])
        if not user: return redirect(url_for('logout'))
        if user.get('role') == 'admin': return redirect(url_for('admin_dashboard'))
        if user.get('role') == 'leader': return redirect(url_for('leader_dashboard'))
        return redirect(url_for('member_dashboard'))
    return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if db["users"]: return redirect(url_for('login'))
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        if u and p:
            users = dict(db["users"])
            users[u] = {
                "username": u,
                "password": generate_password_hash(p),
                "role": "admin",
                "department": "Admin",
                "contact": "",
                "profile_image": "",
                "permissions": {}
            }
            db["users"] = users
            flash("Admin created. Please login.")
            return redirect(url_for('login'))
    return render_template('setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not db["users"]: return redirect(url_for('setup'))
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        users = dict(db["users"])
        if u and p and u in users and check_password_hash(users[u]['password'], p):
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
    date_str = request.args.get('global_date', datetime.now().strftime("%Y-%m-%d"))
    tasks_list = list(db["tasks"])
    daily_tasks = [t for t in tasks_list if t.get('date', '').startswith(date_str)]
    attendance_list = list(db["attendance"])
    daily_attendance = [a for a in attendance_list if a.get('date') == date_str]
    return render_template('admin_dashboard.html', 
                         users_count=len(db["users"]), 
                         tasks_count=len(daily_tasks),
                         attendance_count=len(daily_attendance))

@app.route('/leader')
@login_required
def leader_dashboard():
    u = session['username']
    user = dict(db["users"]).get(u)
    if not user or user['role'] != 'leader': return redirect(url_for('index'))
    dept = user.get('department')
    dept_users = [usr for usr in dict(db["users"]).values() if usr.get('department') == dept]
    return render_template('leader_dashboard.html', dept_users=dept_users, dept=dept)

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
        if action == 'add' and u and u not in users:
            p = request.form.get('password')
            if p:
                users[u] = {
                    "username": u,
                    "password": generate_password_hash(p),
                    "role": request.form.get('role', 'member'),
                    "department": request.form.get('department', 'Designers'),
                    "contact": "",
                    "profile_image": "",
                    "permissions": {}
                }
        elif action == 'delete' and u and u in users and users[u]['role'] != 'admin':
            del users[u]
        elif action == 'reset_password' and u and u in users:
            p = request.form.get('password')
            if p:
                users[u]['password'] = generate_password_hash(p)
        elif action == 'update_permissions' and u in users:
            new_perms = {}
            for dept in departments:
                perms = request.form.getlist(f'perms_{u}_{dept}')
                if perms: new_perms[dept] = perms
            users[u]['permissions'] = new_perms
        db["users"] = users
        return redirect(url_for('manage_users'))
    return render_template('users.html', users=users.values(), departments=departments)

@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    u = session['username']
    users = dict(db["users"])
    user = users.get(u)
    if not user: return redirect(url_for('logout'))
    
    records = list(db["attendance"])
    departments = list(db["departments"])
    date_str = request.args.get('global_date', datetime.now().strftime("%Y-%m-%d"))
    
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
        return redirect(url_for('attendance', global_date=date_str))
        
    filtered = records
    if user['role'] in ['admin', 'leader']:
        f_user = request.args.get('member')
        f_dept = request.args.get('department')
        
        filtered = [r for r in filtered if r['date'] == date_str]
        if f_user: filtered = [r for r in filtered if r['username'] == f_user]
        if f_dept: 
            dept_users = [usr['username'] for usr in users.values() if usr.get('department') == f_dept]
            filtered = [r for r in filtered if r['username'] in dept_users]
        elif user['role'] == 'leader':
            dept_users = [usr['username'] for usr in users.values() if has_permission(user, usr.get('department'))]
            filtered = [r for r in filtered if r['username'] in dept_users]
            
        return render_template('attendance_admin.html', records=filtered, users=users.values(), departments=departments)
    
    return render_template('attendance_member.html', records=[r for r in records if r['username'] == u and r['date'] == date_str])

@app.route('/tasks', methods=['GET', 'POST'])
@login_required
def tasks():
    u = session['username']
    users = dict(db["users"])
    user = users.get(u)
    if not user: return redirect(url_for('logout'))
    
    tasks_list = list(db["tasks"])
    departments = list(db["departments"])
    date_str = request.args.get('global_date', datetime.now().strftime("%Y-%m-%d"))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            assigned_to = request.form.get('assigned_to', u)
            tasks_list.append({
                "id": str(uuid.uuid4()), 
                "username": assigned_to,
                "assigned_by": u,
                "title": request.form.get('title', 'Untitled'),
                "description": request.form.get('description', ''),
                "status": "Pending",
                "date": date_str + " " + datetime.now().strftime("%H:%M")
            })
        elif action == 'update':
            t_id = request.form.get('id')
            for t in tasks_list:
                if t['id'] == t_id and (user['role'] == 'admin' or t['username'] == u or user['role'] == 'leader'):
                    t['status'] = request.form.get('status', 'Pending')
        elif action == 'delete':
            tasks_list = [t for t in tasks_list if not (t['id'] == request.form.get('id') and (user['role'] == 'admin' or t['username'] == u))]
        db["tasks"] = tasks_list
        return redirect(url_for('tasks', global_date=date_str))
        
    filtered = [t for t in tasks_list if t.get('date', '').startswith(date_str)]
    if user['role'] in ['admin', 'leader']:
        f_user = request.args.get('member')
        f_dept = request.args.get('department')
        f_status = request.args.get('status')
        
        if f_user: filtered = [t for t in filtered if t['username'] == f_user]
        if f_status: filtered = [t for t in filtered if t['status'] == f_status]
        if f_dept:
            dept_users = [usr['username'] for usr in users.values() if usr.get('department') == f_dept]
            filtered = [t for t in filtered if t['username'] in dept_users]
        elif user['role'] == 'leader':
            dept_users = [usr['username'] for usr in users.values() if has_permission(user, usr.get('department'))]
            filtered = [t for t in filtered if t['username'] in dept_users]
            
        return render_template('tasks_admin.html', tasks=filtered, users=users.values(), departments=departments)
    
    return render_template('tasks_member.html', tasks=[t for t in filtered if t['username'] == u])

@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    users = dict(db["users"])
    user = users.get(session['username'])
    if not user: return redirect(url_for('logout'))
    
    customer_list = list(db["customers"])
    
    if request.method == 'POST' and user['role'] == 'admin':
        action = request.form.get('action')
        if action == 'add':
            customer_list.append({
                "id": str(uuid.uuid4()),
                "name": request.form.get('name', 'Unknown'),
                "website": request.form.get('website', ''),
                "contact": request.form.get('contact', ''),
                "weekly_payments": [],
                "invoices": []
            })
        elif action == 'update_payment':
            c_id = request.form.get('customer_id')
            week_start = request.form.get('week_start')
            week_end = request.form.get('week_end')
            status = request.form.get('status')
            week_range = f"{week_start} - {week_end}"
            for c in customer_list:
                if c['id'] == c_id:
                    c['weekly_payments'] = [p for p in c['weekly_payments'] if p['week'] != week_range]
                    c['weekly_payments'].append({"week": week_range, "status": status, "date": datetime.now().strftime("%Y-%m-%d")})
        elif action == 'update_invoice':
            c_id = request.form.get('customer_id')
            week_start = request.form.get('week_start')
            week_end = request.form.get('week_end')
            status = request.form.get('status')
            reason = request.form.get('reason', '')
            week_range = f"{week_start} - {week_end}"
            for c in customer_list:
                if c['id'] == c_id:
                    c['invoices'] = [i for i in c['invoices'] if i['week'] != week_range]
                    c['invoices'].append({"week": week_range, "status": status, "reason": reason, "date": datetime.now().strftime("%Y-%m-%d")})
        db["customers"] = customer_list
        return redirect(url_for('customers'))
        
    return render_template('customers.html', customers=customer_list)

@app.route('/notices', methods=['GET', 'POST'])
@login_required
def notices():
    users = dict(db["users"])
    user = users.get(session['username'])
    if not user: return redirect(url_for('logout'))
    
    notice_list = list(db["notices"])
    date_str = request.args.get('global_date', datetime.now().strftime("%Y-%m-%d"))
    
    if request.method == 'POST' and user['role'] == 'admin':
        action = request.form.get('action')
        if action == 'send':
            target = request.form.get('target', 'all')
            notice_list.append({
                "id": str(uuid.uuid4()),
                "title": request.form.get('title', 'Notification'),
                "message": request.form.get('message', ''),
                "target": target,
                "date": date_str + " " + datetime.now().strftime("%H:%M"),
                "sender": session['username']
            })
            db["notices"] = notice_list
            flash("Notice sent successfully")
            return redirect(url_for('notices', global_date=date_str))
            
    visible_notices = [n for n in notice_list if (n['target'] == 'all' or n['target'] == session['username'] or user['role'] == 'admin') and n.get('date', '').startswith(date_str)]
    return render_template('notices.html', notices=visible_notices, users=users.values())

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
    if not user: return redirect(url_for('logout'))
    
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
