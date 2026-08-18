from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from werkzeug.utils import secure_filename

import datetime
import os
import cv2
import face_recognition
import numpy as np
import PIL.Image


# =========================================================
# IMAGE LOADER
# =========================================================

def load_image_file(file, mode="RGB"):
    image = PIL.Image.open(file)

    if mode:
        image = image.convert(mode)

    return np.array(image)


# =========================================================
# FLASK CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = "SRMU_Attendance_System_2026"

bcrypt = Bcrypt(app)

UPLOAD_FOLDER = "uploads"

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================================================
# MONGODB CONNECTION
# =========================================================

client = MongoClient(
    "mongodb://localhost:27017/"
)

db = client["attendance_db"]

students_collection = db["students"]
teachers_collection = db["teachers"]
users_collection = db["users"]
attendance_collection = db["attendance"]


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def get_current_user():

    roll = session.get("user")

    if not roll:
        return None

    user = (
        students_collection.find_one({"roll": roll})
        or teachers_collection.find_one({"roll": roll})
        or users_collection.find_one({"roll": roll})
    )

    return user


def user_exists(roll, erp_id):

    student = students_collection.find_one({
        "$or": [
            {"roll": roll},
            {"erp_id": erp_id}
        ]
    })

    if student:
        return True

    teacher = teachers_collection.find_one({
        "$or": [
            {"roll": roll},
            {"erp_id": erp_id}
        ]
    })

    if teacher:
        return True

    user = users_collection.find_one({
        "$or": [
            {"roll": roll},
            {"erp_id": erp_id}
        ]
    })

    return bool(user)


def save_uploaded_image(image):

    if not image:
        return None

    if image.filename == "":
        return None

    if not allowed_file(image.filename):
        return None

    filename = secure_filename(image.filename)

    name, extension = os.path.splitext(filename)

    timestamp = datetime.datetime.now().strftime(
        "%Y%m%d%H%M%S%f"
    )

    filename = (
        f"{name}_{timestamp}{extension}"
    )

    path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    image.save(path)

    return path


def insert_user(data):

    role = data["role"].lower()

    if role == "student":

        students_collection.insert_one(data)

    elif role == "teacher":

        teachers_collection.insert_one(data)

    else:

        users_collection.insert_one(data)


# =========================================================
# LOGIN
# =========================================================

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        roll = request.form.get(
            "roll",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = (
            students_collection.find_one(
                {"roll": roll}
            )
            or teachers_collection.find_one(
                {"roll": roll}
            )
            or users_collection.find_one(
                {"roll": roll}
            )
        )

        if user:

            stored_password = user.get(
                "password"
            )

            if stored_password:

                try:

                    password_valid = (
                        bcrypt.check_password_hash(
                            stored_password,
                            password
                        )
                    )

                except Exception:

                    password_valid = False

                if password_valid:

                    session["user"] = roll

                    flash(
                        f"Welcome back, {user.get('name', 'User')}!",
                        "success"
                    )

                    return redirect(
                        url_for("admin")
                    )

        flash(
            "Invalid Roll Number or Password.",
            "danger"
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out successfully.",
        "success"
    )

    return redirect(
        url_for("login")
    )


# =========================================================
# SIGNUP
# =========================================================

@app.route(
    "/signup",
    methods=["GET", "POST"]
)
def signup():

    if request.method == "POST":

        erp_id = request.form.get(
            "erp_id",
            ""
        ).strip()

        name = request.form.get(
            "name",
            ""
        ).strip()

        course = request.form.get(
            "course",
            ""
        ).strip()

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        role = request.form.get(
            "role",
            ""
        ).strip().lower()

        roll = request.form.get(
            "roll",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not all([
            erp_id,
            name,
            course,
            subject,
            role,
            roll,
            password
        ]):

            flash(
                "Please fill all required fields.",
                "danger"
            )

            return render_template(
                "signup.html"
            )

        if role not in [
            "student",
            "teacher"
        ]:

            flash(
                "Invalid role selected.",
                "danger"
            )

            return render_template(
                "signup.html"
            )

        if user_exists(
            roll,
            erp_id
        ):

            flash(
                "Roll Number or ERP ID already exists.",
                "warning"
            )

            return render_template(
                "signup.html"
            )

        data = {
            "erp_id": erp_id,
            "name": name,
            "course": course,
            "subject": subject,
            "role": role,
            "roll": roll,
            "password": bcrypt.generate_password_hash(
                password
            ).decode("utf-8"),
            "created_at": datetime.datetime.now()
        }

        image = request.files.get(
            "image"
        )

        if image and image.filename:

            image_path = save_uploaded_image(
                image
            )

            if not image_path:

                flash(
                    "Invalid image. Use JPG, JPEG, PNG or WEBP.",
                    "danger"
                )

                return render_template(
                    "signup.html"
                )

            data["image_path"] = image_path

        insert_user(data)

        flash(
            "Account created successfully. Please login.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "signup.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
def admin():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    current_user = get_current_user()

    total_students = (
        students_collection.count_documents({})
    )

    total_teachers = (
        teachers_collection.count_documents({})
    )

    today = datetime.date.today().strftime(
        "%Y-%m-%d"
    )

    today_present = (
        attendance_collection.count_documents({
            "date": today,
            "status": "Present"
        })
    )

    total_people = (
        total_students + total_teachers
    )

    if total_people > 0:

        attendance_percentage = round(
            (
                today_present
                / total_people
            ) * 100,
            1
        )

    else:

        attendance_percentage = 0

    recent_attendance = list(
        attendance_collection.find()
        .sort("_id", -1)
        .limit(8)
    )

    for record in recent_attendance:

        person = (
            students_collection.find_one(
                {"roll": record.get("roll")}
            )
            or teachers_collection.find_one(
                {"roll": record.get("roll")}
            )
        )

        if person:

            record["name"] = person.get(
                "name",
                "Unknown"
            )

            record["role"] = person.get(
                "role",
                "User"
            )

        else:

            record["name"] = record.get(
                "name",
                "Unknown"
            )

            record["role"] = "User"

    return render_template(
        "admin.html",
        user=current_user,
        total_students=total_students,
        total_teachers=total_teachers,
        today_present=today_present,
        attendance_percentage=attendance_percentage,
        recent_attendance=recent_attendance
    )


# =========================================================
# ADD USER
# =========================================================

@app.route(
    "/add_user",
    methods=["GET", "POST"]
)
def add_user():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        erp_id = request.form.get(
            "erp_id",
            ""
        ).strip()

        name = request.form.get(
            "name",
            ""
        ).strip()

        course = request.form.get(
            "course",
            ""
        ).strip()

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        role = request.form.get(
            "role",
            ""
        ).strip().lower()

        roll = request.form.get(
            "roll",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not all([
            erp_id,
            name,
            course,
            subject,
            role,
            roll,
            password
        ]):

            flash(
                "Please fill all required fields.",
                "danger"
            )

            return render_template(
                "add_user.html"
            )

        if role not in [
            "student",
            "teacher"
        ]:

            flash(
                "Invalid role.",
                "danger"
            )

            return render_template(
                "add_user.html"
            )

        if user_exists(
            roll,
            erp_id
        ):

            flash(
                "Roll Number or ERP ID already exists.",
                "warning"
            )

            return render_template(
                "add_user.html"
            )

        data = {
            "erp_id": erp_id,
            "name": name,
            "course": course,
            "subject": subject,
            "role": role,
            "roll": roll,
            "password": bcrypt.generate_password_hash(
                password
            ).decode("utf-8"),
            "created_at": datetime.datetime.now()
        }

        image = request.files.get(
            "image"
        )

        if image and image.filename:

            image_path = save_uploaded_image(
                image
            )

            if not image_path:

                flash(
                    "Invalid image format.",
                    "danger"
                )

                return render_template(
                    "add_user.html"
                )

            data["image_path"] = image_path

        insert_user(data)

        flash(
            f"{role.title()} added successfully.",
            "success"
        )

        return redirect(
            url_for("admin")
        )

    return render_template(
        "add_user.html"
    )


# =========================================================
# MANUAL ATTENDANCE
# =========================================================

@app.route(
    "/attendance",
    methods=["GET", "POST"]
)
def attendance():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        roll = request.form.get(
            "roll",
            ""
        ).strip()

        person = (
            students_collection.find_one(
                {"roll": roll}
            )
            or teachers_collection.find_one(
                {"roll": roll}
            )
        )

        if not person:

            flash(
                "No student or teacher found with this Roll Number.",
                "danger"
            )

            return redirect(
                url_for("attendance")
            )

        today = datetime.date.today().strftime(
            "%Y-%m-%d"
        )

        # -------------------------------------------------
        # SUBJECT
        # -------------------------------------------------

        subject = person.get(
            "subject",
            "General"
        )

        if not subject:
            subject = "General"

        # -------------------------------------------------
        # CHECK DUPLICATE
        # -------------------------------------------------

        already_marked = (
            attendance_collection.find_one({
                "roll": roll,
                "date": today,
                "subject": subject
            })
        )

        if already_marked:

            flash(
                f"Attendance already marked for "
                f"{person.get('name', roll)} "
                f"for {subject}.",
                "warning"
            )

            return redirect(
                url_for("attendance")
            )

        # -------------------------------------------------
        # INSERT ATTENDANCE
        # -------------------------------------------------

        attendance_collection.insert_one({

            "roll": roll,

            "name": person.get(
                "name",
                "Unknown"
            ),

            "subject": subject,

            "date": today,

            "status": "Present",

            "method": "Manual",

            "time": datetime.datetime.now().strftime(
                "%H:%M:%S"
            )
        })

        flash(
            f"Attendance marked for "
            f"{person.get('name', roll)} "
            f"({subject}).",
            "success"
        )

        return redirect(
            url_for("attendance")
        )

    return render_template(
        "attendance.html"
    )


# =========================================================
# FACE ATTENDANCE PAGE
# =========================================================

@app.route("/face_attendance")
def face_attendance():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    return render_template(
        "face_attendance.html"
    )


# =========================================================
# FACE RECOGNITION
# =========================================================

@app.route("/start_camera")
def start_camera():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    video = cv2.VideoCapture(0)

    if not video.isOpened():

        flash(
            "Camera could not be opened.",
            "danger"
        )

        return redirect(
            url_for("face_attendance")
        )

    known_encodings = []
    known_rolls = []

    users = (
        list(
            students_collection.find({
                "image_path": {
                    "$exists": True
                }
            })
        )
        +
        list(
            teachers_collection.find({
                "image_path": {
                    "$exists": True
                }
            })
        )
    )

    for user in users:

        image_path = user.get(
            "image_path"
        )

        if not image_path:
            continue

        if not os.path.exists(image_path):
            continue

        try:

            image = load_image_file(
                image_path
            )

            encodings = (
                face_recognition.face_encodings(
                    image
                )
            )

            if encodings:

                known_encodings.append(
                    encodings[0]
                )

                known_rolls.append(
                    user.get("roll")
                )

        except Exception as error:

            print(
                "Face image error:",
                error
            )

    if not known_encodings:

        video.release()

        flash(
            "No valid face images found. Please upload student/teacher face images first.",
            "danger"
        )

        return redirect(
            url_for("face_attendance")
        )

    while True:

        ret, frame = video.read()

        if not ret:
            break

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        faces = (
            face_recognition.face_locations(
                rgb_frame
            )
        )

        encodings = (
            face_recognition.face_encodings(
                rgb_frame,
                faces
            )
        )

        for encoding in encodings:

            matches = (
                face_recognition.compare_faces(
                    known_encodings,
                    encoding,
                    tolerance=0.5
                )
            )

            if True not in matches:
                continue

            index = matches.index(True)

            roll = known_rolls[index]

            today = datetime.date.today().strftime(
                "%Y-%m-%d"
            )

            person = (
                students_collection.find_one(
                    {"roll": roll}
                )
                or teachers_collection.find_one(
                    {"roll": roll}
                )
            )

            if not person:
                continue

            # -------------------------------------------------
            # SUBJECT
            # -------------------------------------------------

            subject = person.get(
                "subject",
                "General"
            )

            if not subject:
                subject = "General"

            # -------------------------------------------------
            # CHECK DUPLICATE
            # -------------------------------------------------

            already_marked = (
                attendance_collection.find_one({
                    "roll": roll,
                    "date": today,
                    "subject": subject
                })
            )

            if already_marked:

                video.release()
                cv2.destroyAllWindows()

                return render_template(
                    "face_attendance.html",
                    already_name=person.get(
                        "name",
                        roll
                    ),
                    already_roll=roll
                )

            # -------------------------------------------------
            # INSERT FACE ATTENDANCE
            # -------------------------------------------------

            attendance_collection.insert_one({

                "roll": roll,

                "name": person.get(
                    "name",
                    "Unknown"
                ),

                "subject": subject,

                "date": today,

                "status": "Present",

                "method": "Face Recognition",

                "time": datetime.datetime.now().strftime(
                    "%H:%M:%S"
                )
            })

            video.release()
            cv2.destroyAllWindows()

            return render_template(
                "face_attendance.html",
                success_name=person.get(
                    "name",
                    roll
                ),
                success_roll=roll
            )

        cv2.imshow(
            "SRMU Face Attendance Scanner",
            frame
        )

        if (
            cv2.waitKey(1) & 0xFF
            == ord("q")
        ):
            break

    video.release()
    cv2.destroyAllWindows()

    return render_template(
        "face_attendance.html",
        no_match=True
    )


# =========================================================
# STUDENTS
# =========================================================

@app.route("/students")
def show_students():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    students = list(
        students_collection.find()
        .sort("name", 1)
    )

    return render_template(
        "students.html",
        students=students
    )


# =========================================================
# TEACHERS
# =========================================================

@app.route("/teachers")
def show_teachers():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    teachers = list(
        teachers_collection.find()
        .sort("name", 1)
    )

    return render_template(
        "teachers.html",
        teachers=teachers
    )


# =========================================================
# ATTENDANCE ANALYTICS
# =========================================================

@app.route("/graph")
def graph():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    # -----------------------------------------------------
    # GET ALL STUDENTS
    # -----------------------------------------------------

    students = list(
        students_collection.find()
        .sort("name", 1)
    )

    selected_roll = request.args.get(
        "roll",
        ""
    ).strip()

    selected_student = None

    subject_data = []

    # -----------------------------------------------------
    # STUDENT SELECTED
    # -----------------------------------------------------

    if selected_roll:

        selected_student = (
            students_collection.find_one({
                "roll": selected_roll
            })
        )

        if selected_student:

            attendance_records = list(
                attendance_collection.find({
                    "roll": selected_roll
                })
                .sort("date", 1)
            )

            # -------------------------------------------------
            # GROUP BY SUBJECT
            # -------------------------------------------------

            subject_stats = {}

            for record in attendance_records:

                subject = record.get(
                    "subject"
                )

                # ---------------------------------------------
                # FALLBACK FOR OLD RECORDS
                # ---------------------------------------------

                if not subject:

                    subject = selected_student.get(
                        "subject",
                        "General"
                    )

                if not subject:

                    subject = "General"

                if subject not in subject_stats:

                    subject_stats[subject] = {

                        "present": 0,

                        "absent": 0,

                        "total": 0

                    }

                subject_stats[subject]["total"] += 1

                if record.get("status") == "Present":

                    subject_stats[
                        subject
                    ]["present"] += 1

                elif record.get("status") == "Absent":

                    subject_stats[
                        subject
                    ]["absent"] += 1

            # -------------------------------------------------
            # CONVERT DICTIONARY TO LIST
            # -------------------------------------------------

            for subject, stats in subject_stats.items():

                total = stats["total"]

                present = stats["present"]

                absent = stats["absent"]

                if total > 0:

                    percentage = round(
                        (
                            present
                            / total
                        ) * 100,
                        1
                    )

                else:

                    percentage = 0

                subject_data.append({

                    "subject": subject,

                    "present": present,

                    "absent": absent,

                    "total": total,

                    "percentage": percentage

                })

    # -----------------------------------------------------
    # SORT SUBJECT DATA
    # -----------------------------------------------------

    subject_data.sort(
        key=lambda item: item["subject"].lower()
    )

    return render_template(
        "graph.html",
        students=students,
        selected_roll=selected_roll,
        selected_student=selected_student,
        subject_data=subject_data
    )


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    flash(
        "Image size must be less than 5 MB.",
        "danger"
    )

    return redirect(
        request.referrer
        or url_for("signup")
    )


@app.errorhandler(404)
def page_not_found(error):

    return """
    <!DOCTYPE html>
    <html>

    <head>

        <title>
            404 - Page Not Found
        </title>

        <style>

            body {

                margin: 0;

                min-height: 100vh;

                display: flex;

                align-items: center;

                justify-content: center;

                background: #07111f;

                color: white;

                font-family: Arial, sans-serif;

            }

            .box {

                text-align: center;

                padding: 50px;

                border: 1px solid #1e88e5;

                border-radius: 20px;

                background: #0d1b2a;

            }

            h1 {

                font-size: 70px;

                margin: 0;

                color: #38bdf8;

            }

            a {

                color: #38bdf8;

                text-decoration: none;

            }

        </style>

    </head>

    <body>

        <div class="box">

            <h1>
                404
            </h1>

            <h2>
                Page Not Found
            </h2>

            <p>
                The page you requested does not exist.
            </p>

            <a href="/">
                Back to Login
            </a>

        </div>

    </body>

    </html>
    """, 404


# =========================================================
# APPLICATION START
# =========================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )