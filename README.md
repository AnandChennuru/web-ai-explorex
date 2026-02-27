# ExploreX ⚡

A momentum-powered study session tracker built with Flask.

---

## Project Structure

```
explorex/
├── explorex.py              ← Flask app (main backend)
├── requirements.txt
├── templates/               ← Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── home.html
│   ├── active.html
│   ├── reflect.html
│   └── history.html
└── static/
    └── css/
        └── style.css        ← All styles
```

> **Important:** Flask looks for templates in `templates/` and static files in `static/`.  
> Do **not** move these folders — the directory names are required by Flask.

---

## Setup & Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python explorex.py
```

Then open http://127.0.0.1:5000 in your browser.

### Optional environment variables

| Variable       | Default                    | Description                        |
|----------------|----------------------------|------------------------------------|
| `DATABASE_URL` | `sqlite:///explorex.db`    | SQLAlchemy DB URI                  |
| `SECRET_KEY`   | `explorex_secret_dev_only` | Flask session secret (**change in production!**) |
| `FLASK_DEBUG`  | `false`                    | Set to `true` for auto-reload      |

---

## What was fixed

| File            | Issue                                           | Fix                                                         |
|-----------------|-------------------------------------------------|-------------------------------------------------------------|
| `explorex.py`   | `write_templates()` referenced undefined vars (`BASE_HTML` etc.) causing a crash on startup | Removed the function entirely — Flask loads templates from `templates/` automatically |
| `explorex.py`   | `history()` route didn't pass `page` / `total_pages` but the template used them | Added server-side pagination (10 per page)                  |
| `explorex.py`   | `User.query.get()` / `Active.query.get()` deprecated in SQLAlchemy 2.x | Replaced with `db.session.get()`                            |
| `explorex.py`   | Sessions shorter than 1 minute awarded 0 XP     | Minimum of 1 minute XP is now always awarded               |
| `history.html`  | `url_for('history', page=…)` pagination links   | Backend now handles the `page` query param correctly        |
