from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from flask import Flask, render_template, request, redirect, session, abort, url_for
import sqlite3
from datetime import datetime
import os
import secrets
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps


# ---------------- APP SETUP ----------------
app = Flask(__name__)
app.secret_key = "super_secret_key_change_later"
DATABASE = "database.db"
app.run(host='0.0.0.0', port=5000, debug=True) #For other people to test

# ---------------- MAIL CONFIG ----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'yourgmail@gmail.com'
app.config['MAIL_PASSWORD'] = 'the_app_password_not_your_real_one'
app.config['MAIL_DEFAULT_SENDER'] = 'yourgmail@gmail.com'






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
@app.route("/energy")
def energy():
    conn = get_db_connection()

    records = conn.execute(
        "SELECT * FROM energy_usage"
    ).fetchall()

    totals = conn.execute("""
        SELECT 
            COALESCE(SUM(daily_kwh), 0) AS total_daily,
            COALESCE(SUM(monthly_kwh), 0) AS total_monthly
        FROM energy_usage
    """).fetchone()

    conn.close()

    return render_template(
        "energy.html",
        records=records,
        totals=totals
    )



@app.route("/email-energy", methods=["POST"])
def email_energy_summary():
    conn = get_db_connection()

    records = conn.execute("SELECT * FROM energy_usage").fetchall()
    totals = conn.execute("""
        SELECT 
            SUM(daily_kwh) AS total_daily,
            SUM(monthly_kwh) AS total_monthly
        FROM energy_usage
    """).fetchone()

    conn.close()

    body = (
        f"Energy Usage Summary\n\n"
        f"Daily Total: {round(totals['total_daily'] or 0, 2)} kWh\n"
        f"Monthly Total: {round(totals['total_monthly'] or 0, 2)} kWh\n\n"
    )

    for r in records:
        body += (
            f"{r['appliance']} "
            f"{round(r['daily_kwh'], 2)} kWh/day, "
            f"{round(r['monthly_kwh'], 2)} kWh/month\n"
        )

    msg = Message(
        subject="Your Energy Usage Summary",
        recipients=[app.config["MAIL_USERNAME"]],

        body=body
    )

    mail.send(msg)
    flash("Energy summary emailed successfully")
    return redirect(url_for("energy"))

# ---------------- CARBON ----------------
EMISSION_FACTORS = {
    "electricity": 0.233,
    "car": 0.171,
    "flight": 0.255
}

@app.route("/carbon", methods=["GET", "POST"])
def carbon():
    conn = get_db_connection()
    records = conn.execute("SELECT * FROM carbon_footprint").fetchall()
    total = conn.execute("SELECT SUM(co2_kg) AS total_co2 FROM carbon_footprint").fetchone()
    conn.close()

    if request.method == "POST":
        activity = request.form["activity"]
        amount = float(request.form["amount"])

        factor = EMISSION_FACTORS.get(activity, 0)
        co2_kg = amount * factor

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO carbon_footprint (activity, amount, unit, co2_kg)
            VALUES (?, ?, ?, ?)
        """, (
            activity,
            amount,
            "kWh" if activity == "electricity" else "km",
            co2_kg
        ))
        conn.commit()
        conn.close()

        return redirect(url_for("carbon"))

    return render_template("carbon.html", records=records, total=total)


@app.route("/email-carbon", methods=["POST"])
def email_carbon_summary():
    conn = get_db_connection()

    records = conn.execute("SELECT * FROM carbon_footprint").fetchall()
    total = conn.execute(
        "SELECT SUM(co2_kg) AS total_co2 FROM carbon_footprint"
    ).fetchone()

    conn.close()

    body = f"Carbon Footprint Summary\n\nTotal CO2S: {round(total['total_co2'] or 0, 2)} kg\n\n"

    for r in records:
        body += (
            f"{r['activity']} - {r['amount']} {r['unit']} : "
            f"{round(r['co2_kg'], 2)} kg\n"
        )

    msg = Message(
        subject="Your Carbon Footprint Summary",
        recipients=[app.config["MAIL_USERNAME"]],
        body=body
    )

    mail.send(msg)
    flash("Carbon summary emailed successfully")
    return redirect(url_for("carbon"))

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
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    if user and check_password_hash(user["password_hash"], password):
        flash("Logged in successfully")
    else:
        flash("Invalid email or password")

    return redirect(url_for("home"))

# ---------------- BOOKING ----------------
@app.route("/booking", methods=["GET", "POST"])
def booking():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        service = request.form["service"]
        date = request.form["date"]
        time = request.form["time"]

        msg = Message(
            subject="Your Booking Confirmation - Rolsa",
            recipients=[email],
            body=(
    f"Hi {name},\n\n"
    f"Your {service} has been successfully booked.\n\n"
    f"Date: {date}\n"
    f"Time: {time}\n\n"
    f"Thank you for choosing Rolsa."
)

        )

        mail.send(msg)
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
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
