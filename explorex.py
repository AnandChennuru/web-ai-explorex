import os
from flask import Flask, render_template, url_for, request, redirect, session, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', "sqlite:///explorex.db")
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "explorex_secret_dev_only")
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
db = SQLAlchemy(app)


# ─── Models ───────────────────────────────────────────────────────────────────

class User(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(100), unique=True, nullable=False)
    total_xp         = db.Column(db.Integer, default=0)
    level            = db.Column(db.Integer, default=0)
    streak           = db.Column(db.Integer, default=0)
    momentum_score   = db.Column(db.Float, default=0.0)
    last_active_date = db.Column(db.Date, nullable=True)
    actives          = db.relationship('Active', backref='user', lazy=True)
    todos            = db.relationship('Todo', backref='user')

    def __repr__(self):
        return f"<User {self.name}>"

    def recalculate_momentum(self):
        streak_weight    = self.streak * 10
        session_count    = len(self.actives)
        frequency_factor = min(session_count * 2, 50)
        xp_contribution  = self.total_xp * 0.1
        self.momentum_score = round(streak_weight + frequency_factor + xp_contribution, 1)

    @property
    def badges(self):
        earned = []
        if self.total_xp >= 100:
            earned.append({"name": "Starter",          "icon": "🌱", "xp": 100})
        if self.total_xp >= 500:
            earned.append({"name": "Consistent",       "icon": "🔥", "xp": 500})
        if self.total_xp >= 1000:
            earned.append({"name": "Momentum Builder", "icon": "🚀", "xp": 1000})
        return earned

    @property
    def next_badge(self):
        thresholds = [
            (100,  "Starter",          "🌱"),
            (500,  "Consistent",       "🔥"),
            (1000, "Momentum Builder", "🚀"),
        ]
        for xp, name, icon in thresholds:
            if self.total_xp < xp:
                return {"name": name, "icon": icon, "xp": xp, "remaining": xp - self.total_xp}
        return None


class Active(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time    = db.Column(db.DateTime, default=datetime.now)
    duration_mins = db.Column(db.Integer, nullable=True)
    date          = db.Column(db.Date)
    reflection    = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Active {self.id} - User {self.user_id}>"


class Todo(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text    = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f"<Todo {self.text}>"


# ─── Auth helpers ──────────────────────────────────────────────────────────────

def current_user():
    if 'user_id' not in session:
        return None
    return db.session.get(User, session['user_id'])


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            return render_template('login.html', title='Login', error="Please enter a name.")
        user = User.query.filter_by(name=name).first()
        if not user:
            user = User(name=name)
            db.session.add(user)
            db.session.commit()
        session['user_id'] = user.id
        return redirect('/')
    return render_template('login.html', title='Login')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    user = current_user()
    if not user:
        return redirect('/login')

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'start':
            new_active = Active(user_id=user.id, start_time=datetime.now(), date=date.today())
            db.session.add(new_active)
            db.session.commit()
            session['active_session_id'] = new_active.id
            return redirect('/active')

        if action == 'add_todo':
            text = request.form.get('text', '').strip()
            if text:
                db.session.add(Todo(user_id=user.id, text=text))
                db.session.commit()

        if action == 'delete_todo':
            todo_id = request.form.get('id')
            todo = db.session.get(Todo, todo_id)
            if todo and todo.user_id == user.id:
                db.session.delete(todo)
                db.session.commit()

        return redirect('/')

    recent_reflections = (
        Active.query
        .filter(Active.user_id == user.id, Active.reflection != None)
        .order_by(Active.id.desc())
        .limit(3).all()
    )

    # ── Analytics data for Chart.js ────────────────────────────────────────
    today = date.today()
    week_labels, week_minutes = [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        mins = db.session.query(
            db.func.coalesce(db.func.sum(Active.duration_mins), 0)
        ).filter(Active.user_id == user.id, Active.date == day).scalar()
        week_labels.append(day.strftime('%a'))
        week_minutes.append(int(mins))

    xp_sessions = (
        Active.query
        .filter(Active.user_id == user.id, Active.duration_mins != None)
        .order_by(Active.id).all()
    )
    xp_labels, cumulative_xp, running_xp = [], [], 0
    for idx, s in enumerate(xp_sessions, 1):
        running_xp += s.duration_mins
        xp_labels.append(f"#{idx}")
        cumulative_xp.append(running_xp)

    # Fallback so Chart.js never receives empty arrays
    if not xp_labels:
        xp_labels = ["#0"]
        cumulative_xp = [0]

    return render_template(
        'home.html',
        title='Home',
        user=user,
        todos=user.todos,
        recent_reflections=recent_reflections,
        week_labels=week_labels,
        week_minutes=week_minutes,
        xp_labels=xp_labels,
        cumulative_xp=cumulative_xp,
    )


@app.route('/active', methods=['GET', 'POST'])
def active():
    user = current_user()
    if not user:
        return redirect('/login')
    if 'active_session_id' not in session:
        return redirect('/')

    active_session = db.session.get(Active, session['active_session_id'])
    if not active_session or active_session.user_id != user.id:
        session.pop('active_session_id', None)
        return redirect('/')
    if request.method == 'POST':
        end_time = datetime.now()
        duration = int((end_time - active_session.start_time).total_seconds() // 60)

        active_session.duration_mins = duration

        if duration > 0:
            user.total_xp += duration

        user.level = user.total_xp // 100

        today = date.today()
        momentum_reset = False

        if duration >= 5:

            if user.last_active_date is None:
                user.streak = 1

            else:
                gap = (today - user.last_active_date).days

                if gap == 0:
                    pass
                elif gap == 1:
                    user.streak += 1
                elif gap == 2:
                    pass
                else:
                    user.streak = 1
                    momentum_reset = True

            user.last_active_date = today
        user.recalculate_momentum()
        db.session.commit()

        session.pop('active_session_id', None)
        if momentum_reset:
            session['momentum_reset'] = True
        return redirect(f'/reflect/{active_session.id}')

    return render_template(
        'active.html',
        title='Active',
        active=active_session,
        todos=user.todos,
    )


@app.route('/reflect/<int:id>', methods=['GET', 'POST'])
def reflect(id):
    user = current_user()
    if not user:
        return redirect('/login')

    active_obj = db.session.get(Active, id)
    if active_obj is None:
        abort(404)
    if active_obj.user_id != user.id:
        abort(403)

    momentum_reset = session.pop('momentum_reset', False)

    if request.method == 'POST':
        reflection = request.form.get('reflection', '').strip()
        active_obj.reflection = reflection or None
        db.session.commit()
        return redirect('/')

    return render_template(
        'reflect.html',
        title='Reflect',
        active=active_obj,
        momentum_reset=momentum_reset,
    )


@app.route('/guide')
def guide():
    user = current_user()
    if not user:
        return redirect('/login')
    return render_template('guide.html', title='User Guide')


@app.route('/history')
def history():
    user = current_user()
    if not user:
        return redirect('/login')

    # ── Pagination ─────────────────────────────────────────────────────────
    PER_PAGE = 10
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1

    total_sessions = (
        Active.query
        .filter(Active.user_id == user.id, Active.duration_mins != None)
        .count()
    )
    total_pages = max((total_sessions + PER_PAGE - 1) // PER_PAGE, 1)
    page = min(page, total_pages)

    sessions = (
        Active.query
        .filter(Active.user_id == user.id, Active.duration_mins != None)
        .order_by(Active.id.desc())
        .offset((page - 1) * PER_PAGE)
        .limit(PER_PAGE)
        .all()
    )

    return render_template(
        'history.html',
        title='Session History',
        sessions=sessions,
        user=user,
        page=page,
        total_pages=total_pages,
    )


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # with app.app_context():
    #     db.create_all()
    app.run(debug=app.config['DEBUG'])