import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort, session, Response
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOGO_DIR = os.path.join(UPLOAD_DIR, "logos")
DOC_DIR = os.path.join(UPLOAD_DIR, "documents")
os.makedirs(LOGO_DIR, exist_ok=True)
os.makedirs(DOC_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "cashless.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
db = SQLAlchemy(app)

ALLOWED_IMAGES = {"png", "jpg", "jpeg", "webp"}
ALLOWED_DOCS = {"png", "jpg", "jpeg", "webp", "pdf"}

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class InsuranceCompany(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    tpa_name = db.Column(db.String(160), default="")
    contact = db.Column(db.String(80), default="")
    email = db.Column(db.String(160), default="")
    address = db.Column(db.Text, default="")
    description = db.Column(db.Text, default="")
    logo = db.Column(db.String(255), default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CashlessRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    insurance_id = db.Column(db.Integer, db.ForeignKey("insurance_company.id"), nullable=False)
    insurance = db.relationship("InsuranceCompany", backref=db.backref("requests", lazy=True))
    patient_name = db.Column(db.String(160), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    doctor_name = db.Column(db.String(160), nullable=False)
    contact_number = db.Column(db.String(40), nullable=False)
    id_card = db.Column(db.String(255), nullable=False)
    insurance_card_front = db.Column(db.String(255), nullable=False)
    insurance_card_back = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(30), default="Requested", nullable=False)
    admin_note = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

STATUS_FLOW = ["Requested", "Received", "Processing", "Done"]

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def allowed(filename, kinds):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in kinds

def save_upload(file, folder, kinds):
    if not file or not file.filename:
        return None
    if not allowed(file.filename, kinds):
        return None
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    name = secure_filename(file.filename)
    final = f"{stamp}_{name}"
    file.save(os.path.join(folder, final))
    return final

@app.context_processor
def inject_globals():
    return {"status_flow": STATUS_FLOW}

@app.route("/")
def home():
    insurers = InsuranceCompany.query.filter_by(active=True).order_by(InsuranceCompany.name.asc()).all()
    return render_template("index.html", insurers=insurers)

@app.post("/request")
def create_request():
    insurance_id = request.form.get("insurance_id", type=int)
    insurer = db.session.get(InsuranceCompany, insurance_id)
    if not insurer or not insurer.active:
        flash("Please select a valid insurance company.", "danger")
        return redirect(url_for("home"))

    patient = request.form.get("patient_name", "").strip()
    doctor = request.form.get("doctor_name", "").strip()
    phone = request.form.get("contact_number", "").strip()
    age = request.form.get("age", type=int)
    id_card = request.files.get("id_card")
    front = request.files.get("insurance_card_front")
    back = request.files.get("insurance_card_back")

    if not all([patient, doctor, phone, age is not None, id_card and id_card.filename,
                front and front.filename, back and back.filename]):
        flash("Please complete all patient details and upload ID + insurance card front/back.", "danger")
        return redirect(url_for("home"))

    id_file = save_upload(id_card, DOC_DIR, ALLOWED_DOCS)
    front_file = save_upload(front, DOC_DIR, ALLOWED_DOCS)
    back_file = save_upload(back, DOC_DIR, ALLOWED_DOCS)
    if not all([id_file, front_file, back_file]):
        flash("Allowed document types: JPG, PNG, WEBP or PDF.", "danger")
        return redirect(url_for("home"))

    obj = CashlessRequest(
        insurance_id=insurer.id, patient_name=patient, age=age,
        doctor_name=doctor, contact_number=phone,
        id_card=id_file, insurance_card_front=front_file,
        insurance_card_back=back_file, status="Requested"
    )
    db.session.add(obj)
    db.session.commit()
    flash(f"Cashless request #{obj.id} submitted successfully.", "success")
    return redirect(url_for("home"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username, password=password).first()
        if admin:
            session["admin_id"] = admin.id
            return redirect(url_for("admin_dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("admin_login.html")

@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

@app.get("/admin")
@admin_required
def admin_dashboard():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    query = CashlessRequest.query
    if q:
        like = f"%{q}%"
        query = query.join(InsuranceCompany).filter(
            db.or_(CashlessRequest.patient_name.ilike(like),
                   CashlessRequest.contact_number.ilike(like),
                   InsuranceCompany.name.ilike(like))
        )
    if status in STATUS_FLOW:
        query = query.filter_by(status=status)
    requests_list = query.order_by(CashlessRequest.created_at.desc()).all()
    stats = {s: CashlessRequest.query.filter_by(status=s).count() for s in STATUS_FLOW}
    return render_template("admin_dashboard.html", requests_list=requests_list, insurers=InsuranceCompany.query.order_by(InsuranceCompany.name.asc()).all(), stats=stats, q=q, selected_status=status)

@app.post("/admin/request/<int:req_id>/status")
@admin_required
def update_status(req_id):
    item = db.get_or_404(CashlessRequest, req_id)
    status = request.form.get("status")
    if status not in STATUS_FLOW:
        flash("Invalid status.", "danger")
    else:
        item.status = status
        item.admin_note = request.form.get("admin_note", "").strip()
        db.session.commit()
        flash(f"Request #{item.id} updated to {status}.", "success")
    return redirect(request.referrer or url_for("admin_dashboard"))

@app.post("/admin/insurance/add")
@admin_required
def add_insurance():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Insurance company name is required.", "danger")
        return redirect(url_for("admin_dashboard"))
    logo = save_upload(request.files.get("logo"), LOGO_DIR, ALLOWED_IMAGES) or ""
    item = InsuranceCompany(
        name=name,
        tpa_name=request.form.get("tpa_name", "").strip(),
        contact=request.form.get("contact", "").strip(),
        email=request.form.get("email", "").strip(),
        address=request.form.get("address", "").strip(),
        description=request.form.get("description", "").strip(),
        logo=logo
    )
    db.session.add(item)
    db.session.commit()
    flash("Insurance company added.", "success")
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/insurance/<int:ins_id>/toggle")
@admin_required
def toggle_insurance(ins_id):
    item = db.get_or_404(InsuranceCompany, ins_id)
    item.active = not item.active
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/insurance/<int:ins_id>/delete")
@admin_required
def delete_insurance(ins_id):
    item = db.get_or_404(InsuranceCompany, ins_id)
    if item.requests:
        flash("Cannot delete an insurer that has requests. Disable it instead.", "danger")
    else:
        if item.logo:
            try: os.remove(os.path.join(LOGO_DIR, item.logo))
            except OSError: pass
        db.session.delete(item)
        db.session.commit()
        flash("Insurance company deleted.", "success")
    return redirect(url_for("admin_dashboard"))

@app.get("/uploads/logos/<path:filename>")
def logo_file(filename):
    return send_from_directory(LOGO_DIR, filename)

@app.get("/insurance-logo/<int:ins_id>.svg")
def generated_insurance_logo(ins_id):
    """Return a built-in SVG logo when an insurer has no uploaded logo."""
    insurer = db.get_or_404(InsuranceCompany, ins_id)
    initials = "".join([part[0] for part in insurer.name.split() if part][:3]).upper() or "INS"
    safe_initials = initials.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_name = insurer.name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="500" height="220" viewBox="0 0 500 220">
<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#087bdc"/><stop offset="1" stop-color="#12b9e9"/></linearGradient></defs>
<rect width="500" height="220" rx="32" fill="#f4faff"/>
<circle cx="105" cy="110" r="68" fill="url(#g)"/>
<text x="105" y="125" text-anchor="middle" font-family="Arial,sans-serif" font-size="42" font-weight="700" fill="white">{safe_initials}</text>
<text x="195" y="104" font-family="Arial,sans-serif" font-size="25" font-weight="700" fill="#062b62">{safe_name[:30]}</text>
<text x="195" y="138" font-family="Arial,sans-serif" font-size="16" fill="#5d7690">Insurance Partner</text>
</svg>"""
    return Response(svg, mimetype="image/svg+xml")

@app.get("/uploads/documents/<path:filename>")
@admin_required
def document_file(filename):
    return send_from_directory(DOC_DIR, filename)

@app.get("/health")
def health():
    return {"status": "ok"}

def seed():
    db.create_all()
    if not Admin.query.first():
        db.session.add(Admin(username=os.environ.get("ADMIN_USERNAME", "admin"),
                             password=os.environ.get("ADMIN_PASSWORD", "admin123")))
    if InsuranceCompany.query.count() == 0:
        names = [
            "TATA AIG Insurance", "Aditya Birla Health Insurance",
            "Vidal Health (Norca Care Plus)", "SBI General Insurance",
            "MD India Health Insurance", "Medi Assist", "FHPL",
            "HDFC ERGO General Insurance", "ICICI Lombard General Insurance",
            "ManipalCigna Health Insurance", "ACKO General Insurance",
            "Chola MS General Insurance", "Ericson Insurance TPA",
            "Galaxy Health Insurance", "General Central Insurance",
            "IFFCO Tokio General Insurance", "Link K Insurance TPA",
            "Liberty General Insurance", "Narayana Health Insurance",
            "Reliance General Insurance", "Royal Sundaram General Insurance",
            "Universal Sompo General Insurance", "Volo Health",
            "Magma General Insurance", "Zuno General Insurance"
        ]
        for n in names:
            db.session.add(InsuranceCompany(name=n))
    db.session.commit()

with app.app_context():
    seed()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
