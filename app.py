from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.message import EmailMessage

EMAIL_ADDRESS = "yourprojectemail@gmail.com"
EMAIL_PASSWORD = "your_app_password"



app = Flask(__name__)
app.secret_key = "super_secret_key_change_later"
DATABASE = "database.db"


# ---------------- DATABASE ----------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- ROUTES ----------------
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


EMISSION_FACTORS = {
    "electricity": 0.233,   # kg CO2 per kWh (UK average)
    "car": 0.171,           # kg CO2 per km
    "flight": 0.255         # kg CO2 per km
}


# ---------------- CARBON CALCULATOR ----------------
@app.route("/carbon", methods=["GET", "POST"])
def carbon():
    if request.method == "POST":
        activity = request.form["activity"]
        amount = float(request.form["amount"])

        factor = EMISSION_FACTORS.get(activity, 0)
        co2_kg = amount * factor

        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO carbon_footprint (activity, amount, unit, co2_kg)
            VALUES (?, ?, ?, ?)
            """,
            (
                activity,
                amount,
                "km" if activity != "electricity" else "kWh",
                co2_kg
            )
        )
        conn.commit()
        conn.close()

        return redirect(url_for("carbon_summary"))

    return render_template("carbon.html")


@app.route("/carbon-summary")
def carbon_summary():
    conn = get_db_connection()
    records = conn.execute(
        "SELECT * FROM carbon_footprint ORDER BY created_at DESC"
    ).fetchall()

    total = conn.execute(
        "SELECT SUM(co2_kg) AS total_co2 FROM carbon_footprint"
    ).fetchone()

    conn.close()

    return render_template(
        "carbon_summary.html",
        records=records,
        total=total
    )



# ---------------- REGISTER ----------------
@app.route("/register", methods=["POST"])
def register():
    name = request.form["name"]
    email = request.form["email"]
    phone = request.form["phone"]
    password = request.form["password"]

    password_hash = generate_password_hash(password)

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO users (name, email, phone, password_hash)
            VALUES (?, ?, ?, ?)
            """,
            (name, email, phone, password_hash)
        )
        conn.commit()
        flash("Account created successfully")
    except sqlite3.IntegrityError:
        flash("Email already registered")
    finally:
        conn.close()

    return redirect(url_for("home"))


# ---------------- LOGIN ----------------
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


# ---------------- ENERGY TOOL ----------------
@app.route("/energy", methods=["GET", "POST"])
def energy():
    if request.method == "POST":
        appliance = request.form["appliance"]
        watts = float(request.form["watts"])
        hours = float(request.form["hours"])

        daily_kwh = (watts * hours) / 1000
        monthly_kwh = daily_kwh * 30

        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO energy_usage (appliance, watts, hours, daily_kwh, monthly_kwh)
            VALUES (?, ?, ?, ?, ?)
            """,
            (appliance, watts, hours, daily_kwh, monthly_kwh)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("energy_summary"))

    return render_template("energy.html")

@app.route("/email-energy", methods=["POST"])
def email_energy():
    email = request.form["email"]

    conn = get_db_connection()
    totals = conn.execute(
        "SELECT SUM(daily_kwh) AS daily, SUM(monthly_kwh) AS monthly FROM energy_usage"
    ).fetchone()
    conn.close()

    body = f"""
Energy Usage Summary

Daily usage: {round(totals['daily'] or 0, 2)} kWh
Monthly usage: {round(totals['monthly'] or 0, 2)} kWh

Thank you for using Rolsa Energy Tools.
"""

    send_email(email, "Your Energy Usage Summary", body)
    flash("Energy summary emailed successfully")

    return redirect(url_for("energy_summary"))



@app.route("/energy-summary")
def energy_summary():
    conn = get_db_connection()
    records = conn.execute(
        "SELECT * FROM energy_usage ORDER BY created_at DESC"
    ).fetchall()

    totals = conn.execute(
        """
        SELECT 
            SUM(daily_kwh) AS total_daily,
            SUM(monthly_kwh) AS total_monthly
        FROM energy_usage
        """
    ).fetchone()

    conn.close()

    return render_template(
        "energy_summary.html",
        records=records,
        totals=totals
    )

@app.route("/email-carbon", methods=["POST"])
def email_carbon():
    email = request.form["email"]

    conn = get_db_connection()
    total = conn.execute(
        "SELECT SUM(co2_kg) AS total FROM carbon_footprint"
    ).fetchone()
    conn.close()

    body = f"""
Carbon Footprint Summary

Total CO₂ emissions: {round(total['total'] or 0, 2)} kg

Small changes add up. Thank you for tracking your impact.
"""

    send_email(email, "Your Carbon Footprint Summary", body)
    flash("Carbon summary emailed successfully")

    return redirect(url_for("carbon_summary"))


def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)






def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS energy_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appliance TEXT NOT NULL,
            watts REAL NOT NULL,
            hours REAL NOT NULL,
            daily_kwh REAL NOT NULL,
            monthly_kwh REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
                 
    
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS carbon_footprint (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity TEXT NOT NULL,
        amount REAL NOT NULL,
        unit TEXT NOT NULL,
        co2_kg REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)


    conn.commit()
    conn.close()



# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
