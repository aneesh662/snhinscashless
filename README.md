# Santhi Nursing Home — Cashless Insurance Flask + SQLite

## Features
- Public user section with responsive insurance-company cards
- Insurance selection popup with company/TPA/contact details
- Patient name, age, doctor, contact number
- ID card + insurance card front + insurance card back uploads
- Request is stored in SQLite
- Admin login
- Admin dashboard with Requested → Received → Processing → Done workflow
- Search/filter requests
- View/download uploaded documents
- Add insurance companies and upload logos
- Enable/disable insurance companies
- Seeded with the insurance companies from the original HTML
- Render/GitHub ready

## Run locally

Windows:
```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

Default admin:
- Username: admin
- Password: admin123

Change these before production with environment variables:
- ADMIN_USERNAME
- ADMIN_PASSWORD
- SECRET_KEY

## GitHub

Create a repository, then:
```bash
git init
git add .
git commit -m "Initial cashless insurance Flask app"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

## Render

Create a new Web Service from the GitHub repository.

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
gunicorn app:app
```

Environment variables:
- SECRET_KEY = a long random value
- ADMIN_USERNAME = your admin username
- ADMIN_PASSWORD = your strong admin password

### IMPORTANT: SQLite/uploads on Render
Render service files are ephemeral unless you attach persistent storage. Because this app stores SQLite and uploaded patient documents on the local filesystem, attach a persistent Render Disk and mount it at `/opt/render/project/src/data` OR adapt the paths to a mounted disk.

For a simple deployment, this project works without a disk, but database records and uploaded documents can disappear after a redeploy/restart. For real hospital use, use persistent storage and a production database/object storage.

## Suggested production improvements
- Hash admin passwords (Werkzeug/Flask-Login)
- HTTPS (Render provides TLS)
- Automatic backups
- PostgreSQL for database
- Private object storage for patient documents
- Role-based access
- Audit log
- CSRF protection
- File size/type/content validation
- Document retention policy
- Hospital privacy/security review
