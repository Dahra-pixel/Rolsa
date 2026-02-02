from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------- APP SETUP ----------------
app = Flask(__name__)
app.secret_key = "super_secret_key_change_later"
DATABASE = "database.db"




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

@app.route("/energy", methods=["GET", "POST"])
def energy():
    if request.method == "POST":
        # ----- ENERGY -----
        appliance = request.form.get("appliance", "").strip()
        daily_kwh_raw = request.form.get("daily_kwh", "").strip()
        electricity_kwh_raw = request.form.get("electricity_kwh", "0").strip()
        gas_kwh_raw = request.form.get("gas_kwh", "0").strip()

        # ----- CARBON -----
        activity = request.form.get("activity", "").strip()  # e.g. Car, Flight
        amount_raw = request.form.get("amount", "").strip()

        # Validation
        if not appliance or not daily_kwh_raw or not activity or not amount_raw:
            flash("Please fill in all required fields.")
            return redirect(url_for("energy"))

        try:
            daily_kwh = float(daily_kwh_raw)
            electricity_kwh = float(electricity_kwh_raw)
            gas_kwh = float(gas_kwh_raw)
            amount = float(amount_raw)
        except ValueError:
            flash("Please enter valid numbers.")
            return redirect(url_for("energy"))

        monthly_kwh = round(daily_kwh * 30, 2)

        conn = get_db_connection()

        # Save energy
        conn.execute(
            "INSERT INTO energy_usage (appliance, daily_kwh, monthly_kwh) VALUES (?, ?, ?)",
            (appliance, daily_kwh, monthly_kwh)
        )

        # Simple CO2 calculation (example)
        co2_kg = 0
        unit = ""
        if activity.lower() == "electricity":
            co2_kg = amount * 0.233
            unit = "kWh"
        elif activity.lower() == "car":
            co2_kg = amount * 0.121
            unit = "km"
        elif activity.lower() == "flight":
            co2_kg = amount * 0.255
            unit = "km"

        # Save carbon
        conn.execute(
            "INSERT INTO carbon_footprint (activity, amount, co2_kg, unit) VALUES (?, ?, ?, ?)",
            (activity, amount, co2_kg, unit)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("summary"))  # redirect to summary page

    # GET request -> show form
    return render_template("energy_carbon.html")





# @app.route("/energy-summary")
# def energy_summary():
#     conn = get_db_connection()
#     records = conn.execute(
#         "SELECT appliance, daily_kwh, monthly_kwh FROM energy_usage"
#     ).fetchall()

#     totals = conn.execute("""
#         SELECT 
#             ROUND(SUM(daily_kwh), 2) AS total_daily,
#             ROUND(SUM(monthly_kwh), 2) AS total_monthly
#         FROM energy_usage
#     """).fetchone()

#     conn.close()

#     return render_template(
#         "energy_summary.html",
#         records=records,
#         totals=totals
#     )



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
        co2_kg = round(amount * factor, 2)
        unit = "kWh" if activity == "electricity" else "km"

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO carbon_footprint (activity, amount, unit, co2_kg)
            VALUES (?, ?, ?, ?)
        """, (activity, amount, unit, co2_kg))
        conn.commit()
        conn.close()

        return redirect(url_for("summary"))

    return render_template("carbon.html")

# @app.route("/carbon-summary")
# def carbon_summary():
#     conn = get_db_connection()

#     records = conn.execute(
#         "SELECT activity, amount, unit, ROUND(co2_kg, 2) AS co2_kg FROM carbon_footprint"
#     ).fetchall()

#     total = conn.execute(
#         "SELECT ROUND(SUM(co2_kg), 2) AS total_co2 FROM carbon_footprint"
#     ).fetchone()

#     conn.close()

#     return render_template(
#         "carbon_summary.html",
#         records=records,
#         total=total["total_co2"] or 0
#     )

# ---------------- AUTH ----------------
@app.route("/register", methods=["POST"])
def register():
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO users (name, email, phone, password_hash)
            VALUES (?, ?, ?, ?)
        """, (
            request.form["name"],
            request.form["email"],
            request.form["phone"],
            generate_password_hash(request.form["password"])
        ))
        conn.commit()
        flash("Account created successfully")
    except sqlite3.IntegrityError:
        flash("Email already registered")
    finally:
        conn.close()

    return redirect(url_for("home"))

# Show login form
@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]
    next_page = request.form.get("next") or url_for("home")

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE email=?", (email,)
    ).fetchone()
    conn.close()

    if not user:
        flash("No account found with that email. Please register first.", "warning")
        return redirect(url_for("home", show_register_modal=1))

    if check_password_hash(user["password_hash"], password):
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        flash("Logged in successfully", "success")
        return redirect(next_page.split("?")[0])
    else:
        flash("Incorrect password. Try again.", "danger")
        return redirect(url_for("home", show_login_modal=1))




@app.route("/summary")
def summary():
    conn = get_db_connection()

    energy_records = conn.execute(
        "SELECT appliance, daily_kwh, monthly_kwh FROM energy_usage"
    ).fetchall()
    energy_totals = conn.execute(
        "SELECT SUM(daily_kwh) AS total_daily, SUM(monthly_kwh) AS total_monthly FROM energy_usage"
    ).fetchone()

    carbon_records = conn.execute(
        "SELECT activity, amount, co2_kg, unit FROM carbon_footprint"
    ).fetchall()
    carbon_total = conn.execute(
        "SELECT SUM(co2_kg) AS total_co2 FROM carbon_footprint"
    ).fetchone()

    conn.close()

    return render_template(
        "summary.html",
        energy_records=energy_records,
        energy_totals=energy_totals,
        carbon_records=carbon_records,
        carbon_total=carbon_total
    )






@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out")
    return redirect(url_for("home"))

# ---------------- BOOKING ----------------
# ---------------- BOOKING ----------------
@app.route("/booking", methods=["GET", "POST"])
def booking():
    if not session.get("user_id"):
        # Redirect to home with login modal trigger, pass "next" so after login it goes back to booking
        return redirect(url_for("home", login_required="1", next=request.path))
    
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bookings (user_id, service, date, time, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            request.form["service"],
            request.form["date"],
            request.form["time"],
            request.form.get("notes", "")
        ))
        conn.commit()
        booking_id = cursor.lastrowid  # get the ID of the newly created booking
        conn.close()

        # Redirect to confirmation page for this booking
        return redirect(url_for("booking_confirmation", booking_id=booking_id))

    return render_template("booking.html")






@app.route("/booking-confirmation/<int:booking_id>")
def booking_confirmation(booking_id):
    conn = get_db_connection()
    booking = conn.execute(
        "SELECT service, date, time, notes FROM bookings WHERE id=?",
        (booking_id,)
    ).fetchone()
    conn.close()

    return render_template(
        "booking_confirmation.html",
        service=booking["service"],
        date=booking["date"],
        time=booking["time"],
        notes=booking["notes"]
    )





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
    cursor = conn.cursor()
    cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    service TEXT,
    date TEXT,
    time TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

    conn.commit()
    conn.close()

# ---------------- RUN ----------------
# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)


