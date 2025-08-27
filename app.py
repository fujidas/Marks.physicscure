import os
import json
import pandas as pd
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

# ---------------- Config ----------------
app = Flask(__name__)
app.secret_key = "supersecretkey"

EXCEL_FILE = "students.xlsx"
ADMIN_USER = "admin"
ADMIN_PASS = "743263"
SECRET_QUESTION = "What is your favorite color?"
SECRET_ANSWER = "blue"

# Image upload config
UPLOAD_FOLDER = "static/uploads"
IMAGES_JSON = "images.json"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------- Helpers ----------------
def safe_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def load_students():
    try:
        df = pd.read_excel(EXCEL_FILE)
        students = df.to_dict(orient="records")

        for s in students:
            total_obtained = (
                s.get("mock_test1", 0) + s.get("mock_test2", 0) +
                s.get("mock_test3", 0) + s.get("mock_test4", 0)
            )
            total_full = (
                s.get("mock_test1_full", 0) + s.get("mock_test2_full", 0) +
                s.get("mock_test3_full", 0) + s.get("mock_test4_full", 0)
            )
            s["percentage"] = round((total_obtained / total_full) * 100, 2) if total_full > 0 else 0
        return students
    except Exception as e:
        print("Error loading Excel:", e)
        return []


def save_students(students):
    df = pd.DataFrame(students)
    df.to_excel(EXCEL_FILE, index=False)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_images():
    if os.path.exists(IMAGES_JSON):
        with open(IMAGES_JSON, "r") as f:
            return json.load(f)
    return []


def save_images(images):
    with open(IMAGES_JSON, "w") as f:
        json.dump(images, f)


# ---------------- Rank Card PDF ----------------
@app.route("/rankcard/<int:student_id>")
def generate_rank_card(student_id):
    students = load_students()
    student = next((s for s in students if s["id"] == student_id), None)

    if not student:
        return "❌ Student not found", 404

    # Rank calculation (Dense Ranking)
    same_class_students = [s for s in students if s["student_class"] == student["student_class"]]
    ranked = sorted(same_class_students, key=lambda x: float(x["percentage"]), reverse=True)

    current_rank = 0
    last_percentage = None
    for s in ranked:
        if s["percentage"] != last_percentage:
            current_rank += 1
        s["rank"] = current_rank
        last_percentage = s["percentage"]

    student_rank = next(s["rank"] for s in ranked if s["id"] == student_id)

    # Create PDF
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    pdf.setTitle("Rank Card")

    # Certificate Border
    pdf.setStrokeColor(colors.darkblue)
    pdf.setLineWidth(6)
    pdf.rect(20, 20, width - 40, height - 40)

    pdf.setStrokeColor(colors.gold)
    pdf.setLineWidth(3)
    pdf.rect(35, 35, width - 70, height - 70)

    # Background equations
    equations = ["E=mc²", "F=ma", "V=IR", "p=mv", "ΔE=hν", "s=ut+½at²", "V=4/3πr³", "λ = v/f"]
    eq_positions = [(80, 650, 20), (450, 690, -15), (100, 500, -25), (420, 520, 10),
                    (80, 380, 15), (460, 360, -20), (120, 250, 12), (420, 230, -14)]
    pdf.setFillColor(colors.Color(0, 0, 0, alpha=0.15))
    for (x, y, angle), eq in zip(eq_positions, equations * 2):
        pdf.saveState()
        pdf.translate(x, y)
        pdf.rotate(angle)
        pdf.setFont("Helvetica-Bold", 24)
        pdf.drawString(0, 0, eq)
        pdf.restoreState()
    pdf.setFillColor(colors.black)

    # Logo
    logo_path = os.path.join("static", "logo.png")
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        pdf.drawImage(logo, width/2 - 100, height - 200, width=200, height=120, mask='auto')

    # Title
    pdf.setFont("Helvetica-Bold", 26)
    pdf.setFillColor(colors.darkblue)
    pdf.drawCentredString(width/2, height - 230, "🏆 Certificate of Achievement")

    pdf.setFont("Helvetica-Bold", 20)
    pdf.setFillColor(colors.black)
    pdf.drawCentredString(width/2, height - 260, "Student Rank Card")

    # Student Info
    pdf.setFont("Helvetica", 14)
    y = height - 320
    pdf.drawString(80, y, f"Name: {student['name']}")
    pdf.drawString(80, y - 30, f"Class: {student['student_class']}")
    pdf.drawString(80, y - 60, f"School: {student['school']}")
    pdf.drawString(80, y - 90, f"Phone: {student['phone']}")

    # Performance
    pdf.setFont("Helvetica-Bold", 16)
    pdf.setFillColor(colors.darkred)
    pdf.drawString(80, y - 140, "Academic Performance:")

    pdf.setFont("Helvetica", 13)
    pdf.setFillColor(colors.black)
    pdf.drawString(100, y - 170, f"Percentage: {student['percentage']}%")

    # Rank
    rank_text = f"Class Rank: {student_rank}"
    if student_rank == 1: rank_text += " 🥇"
    elif student_rank == 2: rank_text += " 🥈"
    elif student_rank == 3: rank_text += " 🥉"

    pdf.setFont("Helvetica-Bold", 15)
    pdf.setFillColor(colors.darkblue)
    pdf.drawString(100, y - 200, rank_text)

    # Mock test details
    pdf.setFont("Helvetica-Bold", 16)
    pdf.setFillColor(colors.darkgreen)
    pdf.drawString(80, y - 240, "Mock Test Performance:")

    pdf.setFont("Helvetica", 13)
    pdf.setFillColor(colors.black)
    pdf.drawString(100, y - 270, f"Mock Test 1: {student.get('mock_test1', 0)} / {student.get('mock_test1_full', 0)}")
    pdf.drawString(100, y - 295, f"Mock Test 2: {student.get('mock_test2', 0)} / {student.get('mock_test2_full', 0)}")
    pdf.drawString(100, y - 320, f"Mock Test 3: {student.get('mock_test3', 0)} / {student.get('mock_test3_full', 0)}")
    pdf.drawString(100, y - 345, f"Mock Test 4: {student.get('mock_test4', 0)} / {student.get('mock_test4_full', 0)}")

    # Footer
    pdf.setFont("Helvetica", 12)
    pdf.setFillColor(colors.black)
    pdf.drawString(80, 100, "Signature (Teacher): SHANTANU DUTTA")
    pdf.line(width-250, 100, width-80, 100)
    pdf.drawCentredString(width-165, 85, "Signature (Guardian)")

    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(colors.darkred)
    pdf.drawCentredString(width/2, 60, "FALL IN LOVE WITH PHYSICS ❤️")

    pdf.setFont("Helvetica-Oblique", 9)
    pdf.setFillColor(colors.black)
    pdf.drawCentredString(width/2, 45, "Generated by PHYSICKS CURE Student Management System")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True,
                     download_name=f"RankCard_{student['name']}.pdf",
                     mimetype="application/pdf")

# ---------------- Admin Login ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin"))
        else:
            return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")


# ---------------- Change Password ----------------
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if "admin" not in session:  # only allow admin
        return redirect(url_for("login"))

    if request.method == "POST":
        old_pass = request.form["old_password"]
        new_pass = request.form["new_password"]

        # Load current password (example: from a JSON file or DB)
        if not os.path.exists("admin.json"):
            with open("admin.json", "w") as f:
                json.dump({"password": ADMIN_PASS}, f)

        with open("admin.json", "r") as f:
            data = json.load(f)

        if data["password"] == old_pass:  # check old password
            data["password"] = new_pass
            with open("admin.json", "w") as f:
                json.dump(data, f)

            flash("Password changed successfully!", "success")
            return redirect(url_for("admin"))
        else:
            flash("Old password is incorrect!", "danger")

    return render_template("change_password.html")


# ---------------- Admin Page ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect(url_for("login"))

    students = load_students()
    images = load_images()

    if request.method == "POST":
        action = request.form.get("action")

        # Student add
        if action == "add":
            new_student = {
                "id": len(students) + 1,
                "name": request.form["name"],
                "student_class": request.form["class"],
                "phone": request.form["phone"],
                "guardian_phone": request.form["guardian_phone"],
                "school": request.form["school"],
                "mock_test1": safe_float(request.form.get("mock_test1", 0)),
                "mock_test1_full": safe_float(request.form.get("mock_test1_full", 0)),
                "mock_test2": safe_float(request.form.get("mock_test2", 0)),
                "mock_test2_full": safe_float(request.form.get("mock_test2_full", 0)),
                "mock_test3": safe_float(request.form.get("mock_test3", 0)),
                "mock_test3_full": safe_float(request.form.get("mock_test3_full", 0)),
                "mock_test4": safe_float(request.form.get("mock_test4", 0)),
                "mock_test4_full": safe_float(request.form.get("mock_test4_full", 0)),
            }
            students.append(new_student)
            save_students(students)

        elif action == "delete":
            student_id = int(request.form["id"])
            students = [s for s in students if s["id"] != student_id]
            save_students(students)

        elif action == "edit":
            student_id = int(request.form["id"])
            for s in students:
                if s["id"] == student_id:
                    s["name"] = request.form["name"]
                    s["student_class"] = request.form["class"]
                    s["phone"] = request.form["phone"]
                    s["guardian_phone"] = request.form["guardian_phone"]
                    s["school"] = request.form["school"]
                    s["mock_test1"] = safe_float(request.form.get("mock_test1", 0))
                    s["mock_test1_full"] = safe_float(request.form.get("mock_test1_full", 0))
                    s["mock_test2"] = safe_float(request.form.get("mock_test2", 0))
                    s["mock_test2_full"] = safe_float(request.form.get("mock_test2_full", 0))
                    s["mock_test3"] = safe_float(request.form.get("mock_test3", 0))
                    s["mock_test3_full"] = safe_float(request.form.get("mock_test3_full", 0))
                    s["mock_test4"] = safe_float(request.form.get("mock_test4", 0))
                    s["mock_test4_full"] = safe_float(request.form.get("mock_test4_full", 0))
                    break
            save_students(students)

        # Upload image
        elif action == "upload_image":
            if "image" in request.files:
                file = request.files["image"]
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(filepath)
                    images.append(filename)
                    save_images(images)

        # Delete image
        elif action == "delete_image":
            filename = request.form["filename"]
            if filename in images:
                images.remove(filename)
                save_images(images)
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)

        return redirect(url_for("admin"))

    return render_template("admin.html", students=students, images=images)


# ---------------- Logout ----------------
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("login"))


# ---------------- Public View Page ----------------
@app.route("/view", methods=["GET", "POST"])
def view():
    students = load_students()

    # --- Keep Sl No fixed (use student ID as roll/serial no) ---
    for i, s in enumerate(students, start=1):
        s["serial_no"] = s.get("id", i)   # use id if available, fallback to index

    # --- Apply Search filter ---
    query = request.args.get("q", "").lower()
    if query:
        students = [
            s for s in students
            if query in s["name"].lower() or query in str(s["phone"]) or query in str(s["guardian_phone"])
        ]

    # --- Apply Class Filter ---
    selected_class = request.args.get("class_filter")
    if selected_class and selected_class != "All":
        students = [s for s in students if s["student_class"] == selected_class]

    # --- Recalculate Rank (Class-wise) ---
    ranked = sorted(students, key=lambda x: float(x["percentage"]), reverse=True)
    current_rank, last_percentage = 0, None
    for s in ranked:
        if s["percentage"] != last_percentage:
            current_rank += 1
        s["rank"] = current_rank
        last_percentage = s["percentage"]


    # --- Collect dropdown values ---
    def class_sort_key(c):
        try:
            return (0, int(c))
        except (ValueError, TypeError):
            return (1, str(c))

    all_students = load_students()
    classes = sorted(set(s["student_class"] for s in all_students), key=class_sort_key)
    schools = sorted(set(s["school"] for s in all_students))

    return render_template(
        "view.html",
        students=ranked,
        classes=classes,
        schools=schools,
        query=query,
        selected_class=selected_class
    )
@app.route("/admin/gallery")
def manage_gallery():
    images = os.listdir(os.path.join(app.static_folder, "uploads"))
    return render_template("gallery.html", images=images)

@app.route("/admin/upload", methods=["POST"])
def upload_image():
    file = request.files["file"]
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.static_folder, "uploads", filename))
    return redirect(url_for("manage_gallery"))

@app.route("/admin/delete/<filename>", methods=["POST"])
def delete_image(filename):
    path = os.path.join(app.static_folder, "uploads", filename)
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for("manage_gallery"))
# ---------------- Forgot Password ----------------
@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        answer = request.form.get("answer", "").strip().lower()
        if answer == SECRET_ANSWER:
            return render_template("reveal.html", user=ADMIN_USER, password=ADMIN_PASS)
        else:
            return render_template("forgot.html", error="❌ Wrong answer, try again.", question=SECRET_QUESTION)
    return render_template("forgot.html", question=SECRET_QUESTION)


# ---------------- Home ----------------
@app.route("/")
def home():
    images = load_images()
    return render_template("index.html", images=images)
if __name__ == "__main__":
    app.run()

