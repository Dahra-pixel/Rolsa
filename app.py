from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message

# ---------------- APP SETUP ----------------
app = Flask(__name__)
app.secret_key = "super_secret_key_change_later"
DATABASE = "database.db"

# ---------------- MAIL CONFIG ----------------
# app.config["MAIL_SERVER"] = "smtp.gmail.com"
# app.config["MAIL_PORT"] = 587
# app.config["MAIL_USE_TLS"] = True
# app.config["MAIL_USERNAME"] = "your_email@gmail.com"
# app.config["MAIL_PASSWORD"] = "your_app_password"
# app.config["MAIL_DEFAULT_SENDER"] = "your_email@gmail.com"

mail = Mail(app)

# ---------------- DATABASE ----------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- BASIC PAGES ----------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/products")
def products():
    return render_template("products.html")

@app.route("/news")
def news():
    return render_template("news.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

# ---------------- ENERGY ----------------
@app.route("/energy", methods=["GET", "POST"])
def energy():
    if request.method == "POST":
        appliance = request.form["appliance"]
        daily_kwh = float(request.form["daily_kwh"])
        monthly_kwh = daily_kwh * 30

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO energy_usage (appliance, daily_kwh, monthly_kwh) VALUES (?, ?, ?)",
            (appliance, daily_kwh, monthly_kwh)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("energy_summary"))

    # GET request: show form + existing data
    conn = get_db_connection()
    records = conn.execute(
        "SELECT appliance, daily_kwh, monthly_kwh FROM energy_usage"
    ).fetchall()
    conn.close()

    return render_template("energy.html", records=records, totals=None)




@app.route("/energy-summary")
def energy_summary():
    conn = get_db_connection()
    records = conn.execute(
        "SELECT appliance, daily_kwh, monthly_kwh FROM energy_usage"
    ).fetchall()
    conn.close()

    if records:
        total_daily = sum(r["daily_kwh"] for r in records)
        total_monthly = sum(r["monthly_kwh"] for r in records)
        totals = {
            "total_daily": round(total_daily, 2),
            "total_monthly": round(total_monthly, 2)
        }
    else:
        totals = None

    return render_template(
        "energy_summary.html",
        records=records,
        totals=totals
    )




# ---------------- CARBON ----------------
EMISSION_FACTORS = {
    "electricity": 0.233,
    "car": 0.171,
    "flight": 0.255
}

@app.route("/carbon", methods=["GET", "POST"])
def carbon():
    if request.method == "POST":
        activity = request.form["activity"]
        amount = float(request.form["amount"])

        factor = EMISSION_FACTORS.get(activity, 0)
        co2_kg = amount * factor

        unit = "kWh" if activity == "electricity" else "km"

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO carbon_footprint (activity, amount, unit, co2_kg)
            VALUES (?, ?, ?, ?)
        """, (activity, amount, unit, co2_kg))
        conn.commit()
        conn.close()

        return redirect(url_for("carbon_summary"))

    # GET request
    return render_template("carbon.html")

@app.route("/carbon-summary")
def carbon_summary():
    conn = get_db_connection()
    records = conn.execute(
        "SELECT activity, amount, unit, co2_kg FROM carbon_footprint"
    ).fetchall()

    total = conn.execute(
        "SELECT SUM(co2_kg) AS total_co2 FROM carbon_footprint"
    ).fetchone()

    conn.close()

    total_co2 = round(total["total_co2"], 2) if total["total_co2"] else 0.00

    records = [
    {**dict(r), "co2_kg": round(r["co2_kg"], 2)}
    for r in records
    ]


    return render_template(
        "carbon_summary.html",
        records=records,
        total=total_co2
    )





# ---------------- AUTH ----------------
@app.route("/register", methods=["POST"])
def register():
    name = request.form["name"]
    email = request.form["email"]
    phone = request.form["phone"]
    password = request.form["password"]

    password_hash = generate_password_hash(password)
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO users (name, email, phone, password_hash)
            VALUES (?, ?, ?, ?)
        """, (name, email, phone, password_hash))
        conn.commit()
        flash("Account created successfully")
    except sqlite3.IntegrityError:
        flash("Email already registered")
    finally:
        conn.close()
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    if user and check_password_hash(user["password_hash"], password):
        flash("Logged in successfully")
    else:
        flash("Invalid email or password")
    return redirect(url_for("home"))

# ---------------- BOOKING ----------------
@app.route("/booking", methods=["GET", "POST"])
def booking():
    if request.method=="POST":
        name = request.form["name"]
        email = request.form["email"]
        service = request.form["service"]
        date = request.form["date"]
        time = request.form["time"]
        msg = Message(
            subject="Your Booking Confirmation – Rolsa",
            recipients=[email],
            body=f"Hi {name},\n\nYour {service} has been successfully booked.\nDate: {date}\nTime: {time}\n\nThank you for choosing Rolsa."
        )
        mail.send(msg)
        flash("Booking confirmed, email sent!")
        return render_template("booking.html", show_modal=True)
    return render_template("booking.html")

# ---------------- DB INIT ----------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            phone TEXT,
            password_hash TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS energy_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appliance TEXT,
            watts REAL,
            hours REAL,
            daily_kwh REAL,
            monthly_kwh REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS carbon_footprint (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity TEXT,
            amount REAL,
            unit TEXT,
            co2_kg REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# ---------------- RUN ----------------
if __name__=="__main__":
    init_db()
    app.run(debug=True)
