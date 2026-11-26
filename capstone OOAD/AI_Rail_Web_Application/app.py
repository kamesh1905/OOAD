from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os, uuid, random
from datetime import datetime, date, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-demo-secret")
DB = os.path.join(os.path.dirname(__file__), "railway.db")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS passengers(
      id INTEGER PRIMARY KEY AUTOINCREMENT, passenger_id TEXT UNIQUE,
      name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT NOT NULL,
      password TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS trains(
      id INTEGER PRIMARY KEY AUTOINCREMENT, train_no TEXT UNIQUE, name TEXT,
      source TEXT, destination TEXT, departure TEXT, arrival TEXT,
      duration TEXT, running_days TEXT, status TEXT DEFAULT 'On Time'
    );
    CREATE TABLE IF NOT EXISTS seats(
      id INTEGER PRIMARY KEY AUTOINCREMENT, train_id INTEGER, journey_date TEXT,
      seat_class TEXT, seat_no TEXT, fare REAL, state TEXT DEFAULT 'AVAILABLE',
      UNIQUE(train_id, journey_date, seat_class, seat_no),
      FOREIGN KEY(train_id) REFERENCES trains(id)
    );
    CREATE TABLE IF NOT EXISTS bookings(
      id INTEGER PRIMARY KEY AUTOINCREMENT, pnr TEXT UNIQUE, passenger_id INTEGER,
      train_id INTEGER, journey_date TEXT, seat_id INTEGER, seat_class TEXT,
      fare REAL, status TEXT DEFAULT 'BOOKED', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(passenger_id) REFERENCES passengers(id),
      FOREIGN KEY(train_id) REFERENCES trains(id), FOREIGN KEY(seat_id) REFERENCES seats(id)
    );
    CREATE TABLE IF NOT EXISTS refunds(
      id INTEGER PRIMARY KEY AUTOINCREMENT, booking_id INTEGER, amount REAL,
      deduction REAL, status TEXT DEFAULT 'PROCESSED', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(booking_id) REFERENCES bookings(id)
    );
    CREATE TABLE IF NOT EXISTS notifications(
      id INTEGER PRIMARY KEY AUTOINCREMENT, passenger_id INTEGER, message TEXT,
      kind TEXT, status TEXT DEFAULT 'DELIVERED', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(passenger_id) REFERENCES passengers(id)
    );
    """)
    if con.execute("SELECT COUNT(*) FROM trains").fetchone()[0] == 0:
        trains = [
          ("12675","Kovai Express","Chennai","Coimbatore","06:10","13:50","7h 40m","Daily","On Time"),
          ("12676","Kovai Express","Coimbatore","Chennai","15:15","23:00","7h 45m","Daily","On Time"),
          ("12609","Mysuru Express","Chennai","Bengaluru","22:30","05:30","7h","Daily","On Time"),
          ("12678","Intercity Express","Chennai","Bengaluru","07:15","13:00","5h 45m","Daily","Delayed 10 min"),
          ("16127","Guruvayur Express","Chennai","Madurai","07:40","15:30","7h 50m","Daily","On Time"),
          ("12635","Vaigai Express","Chennai","Madurai","13:50","21:15","7h 25m","Daily","On Time"),
          ("22671","Tejas Express","Chennai","Coimbatore","06:00","11:50","5h 50m","Except Tue","On Time"),
          ("12631","Nellai Express","Chennai","Tirunelveli","19:50","07:40","11h 50m","Daily","On Time"),
          ("12605","Pallavan Express","Chennai","Karaikudi","15:45","22:20","6h 35m","Daily","On Time"),
        ]
        con.executemany("INSERT INTO trains(train_no,name,source,destination,departure,arrival,duration,running_days,status) VALUES(?,?,?,?,?,?,?,?,?)", trains)
    con.commit()
    con.close()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    con=db()
    trains=con.execute("SELECT * FROM trains ORDER BY departure LIMIT 6").fetchall()
    con.close()
    return render_template("index.html", trains=trains, today=date.today().isoformat())

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("name","").strip()
        email=request.form.get("email","").strip().lower()
        phone=request.form.get("phone","").strip()
        password=request.form.get("password","")
        if not all([name,email,phone,password]):
            flash("Please complete every field.", "danger")
        else:
            con=db()
            try:
                pid="PAX"+uuid.uuid4().hex[:7].upper()
                cur=con.execute("INSERT INTO passengers(passenger_id,name,email,phone,password) VALUES(?,?,?,?,?)",(pid,name,email,phone,password))
                con.commit()
                session["user_id"]=cur.lastrowid; session["name"]=name
                flash("Account created successfully.", "success")
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                flash("An account with this email already exists.", "danger")
            finally: con.close()
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        con=db()
        user=con.execute("SELECT * FROM passengers WHERE email=? AND password=?",(request.form.get("email","").lower(),request.form.get("password",""))).fetchone()
        con.close()
        if user:
            session["user_id"]=user["id"]; session["name"]=user["name"]
            return redirect(url_for("index"))
        flash("Invalid email or password.", "danger")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/search")
def search():
    source=request.args.get("source","").strip()
    destination=request.args.get("destination","").strip()
    journey=request.args.get("date","")
    cls=request.args.get("class","Sleeper")
    con=db()
    trains=con.execute("SELECT * FROM trains WHERE lower(source)=lower(?) AND lower(destination)=lower(?) ORDER BY departure",(source,destination)).fetchall() if source and destination else []
    results=[]
    for t in trains:
        seats=ensure_seats(con,t["id"],journey,cls)
        results.append({"train":t,"available":seats,"fare":fare_for(cls)})
    con.commit(); con.close()
    return render_template("search.html", results=results, source=source, destination=destination, journey=journey, cls=cls)

def fare_for(cls):
    return {"Sleeper":350,"3A":850,"2A":1250,"CC":500,"2S":180}.get(cls,350)

def ensure_seats(con, train_id, journey, cls):
    if not journey: return 0
    count=con.execute("SELECT COUNT(*) FROM seats WHERE train_id=? AND journey_date=? AND seat_class=?",(train_id,journey,cls)).fetchone()[0]
    if count==0:
        n=20 if cls in ("Sleeper","3A","2A") else 30
        for i in range(1,n+1):
            con.execute("INSERT OR IGNORE INTO seats(train_id,journey_date,seat_class,seat_no,fare) VALUES(?,?,?,?,?)",(train_id,journey,cls,f"{cls}-{i:02d}",fare_for(cls)))
    return con.execute("SELECT COUNT(*) FROM seats WHERE train_id=? AND journey_date=? AND seat_class=? AND state='AVAILABLE'",(train_id,journey,cls)).fetchone()[0]

@app.route("/book/<int:train_id>", methods=["POST"])
@login_required
def book(train_id):
    journey=request.form.get("journey_date")
    cls=request.form.get("seat_class","Sleeper")
    con=db()
    train=con.execute("SELECT * FROM trains WHERE id=?",(train_id,)).fetchone()
    if not train or not journey or journey < date.today().isoformat():
        con.close(); flash("Please select a valid journey date.", "danger"); return redirect(url_for("index"))
    ensure_seats(con,train_id,journey,cls)
    try:
        con.execute("BEGIN IMMEDIATE")
        seat=con.execute("SELECT * FROM seats WHERE train_id=? AND journey_date=? AND seat_class=? AND state='AVAILABLE' ORDER BY id LIMIT 1",(train_id,journey,cls)).fetchone()
        if not seat:
            con.rollback(); flash("Sorry, no seats are available.", "warning"); return redirect(url_for("index"))
        con.execute("UPDATE seats SET state='BOOKED' WHERE id=? AND state='AVAILABLE'",(seat["id"],))
        if con.execute("SELECT changes()").fetchone()[0] != 1:
            con.rollback(); flash("Seat was just booked. Please try again.", "warning"); return redirect(url_for("index"))
        pnr="PNR"+uuid.uuid4().hex[:9].upper()
        fare=seat["fare"]
        con.execute("INSERT INTO bookings(pnr,passenger_id,train_id,journey_date,seat_id,seat_class,fare) VALUES(?,?,?,?,?,?,?)",(pnr,session["user_id"],train_id,journey,seat["id"],cls,fare))
        con.execute("INSERT INTO notifications(passenger_id,message,kind) VALUES(?,?,?)",(session["user_id"],f"Booking confirmed. Your PNR is {pnr}.","BOOKING"))
        con.commit()
        booking=con.execute("SELECT b.*,t.name,t.train_no,t.source,t.destination,t.departure,t.arrival,s.seat_no,p.name AS passenger_name,p.passenger_id AS pax_code FROM bookings b JOIN trains t ON b.train_id=t.id JOIN seats s ON b.seat_id=s.id JOIN passengers p ON b.passenger_id=p.id WHERE b.pnr=?",(pnr,)).fetchone()
        con.close()
        return render_template("ticket.html", booking=booking)
    except Exception:
        con.rollback(); con.close()
        flash("Booking could not be completed. Please retry.", "danger")
        return redirect(url_for("index"))

@app.route("/my-bookings")
@login_required
def my_bookings():
    con=db()
    rows=con.execute("""SELECT b.*,t.train_no,t.name,t.source,t.destination,t.departure,t.arrival,s.seat_no
    FROM bookings b JOIN trains t ON b.train_id=t.id JOIN seats s ON b.seat_id=s.id
    WHERE b.passenger_id=? ORDER BY b.id DESC""",(session["user_id"],)).fetchall()
    con.close()
    return render_template("bookings.html", bookings=rows)

@app.route("/cancel/<int:booking_id>", methods=["POST"])
@login_required
def cancel(booking_id):
    con=db()
    con.execute("BEGIN IMMEDIATE")
    b=con.execute("SELECT * FROM bookings WHERE id=? AND passenger_id=?",(booking_id,session["user_id"])).fetchone()
    if not b or b["status"]!="BOOKED":
        con.rollback(); con.close(); flash("This ticket cannot be cancelled.", "warning"); return redirect(url_for("my_bookings"))
    deduction=round(b["fare"]*0.10,2); refund=round(b["fare"]-deduction,2)
    con.execute("UPDATE bookings SET status='CANCELLED' WHERE id=?",(booking_id,))
    con.execute("UPDATE seats SET state='AVAILABLE' WHERE id=?",(b["seat_id"],))
    con.execute("INSERT INTO refunds(booking_id,amount,deduction,status) VALUES(?,?,?,'PROCESSED')",(booking_id,refund,deduction))
    con.execute("INSERT INTO notifications(passenger_id,message,kind) VALUES(?,?,?)",(session["user_id"],f"Ticket {b['pnr']} cancelled. Demo refund: ₹{refund:.2f}.","REFUND"))
    con.commit(); con.close()
    flash(f"Ticket cancelled. Demo refund ₹{refund:.2f} (10% demo deduction).", "success")
    return redirect(url_for("my_bookings"))

@app.route("/notifications")
@login_required
def notifications():
    con=db(); rows=con.execute("SELECT * FROM notifications WHERE passenger_id=? ORDER BY id DESC",(session["user_id"],)).fetchall(); con.close()
    return render_template("notifications.html", notifications=rows)

@app.route("/admin")
def admin():
    con=db()
    stats={
      "passengers":con.execute("SELECT COUNT(*) FROM passengers").fetchone()[0],
      "bookings":con.execute("SELECT COUNT(*) FROM bookings WHERE status='BOOKED'").fetchone()[0],
      "cancelled":con.execute("SELECT COUNT(*) FROM bookings WHERE status='CANCELLED'").fetchone()[0],
      "revenue":con.execute("SELECT COALESCE(SUM(fare),0) FROM bookings WHERE status='BOOKED'").fetchone()[0]
    }
    trains=con.execute("SELECT t.*,COUNT(s.id) AS seats_total,SUM(CASE WHEN s.state='BOOKED' THEN 1 ELSE 0 END) AS seats_booked FROM trains t LEFT JOIN seats s ON t.id=s.train_id GROUP BY t.id ORDER BY t.train_no").fetchall()
    recent=con.execute("SELECT b.*,p.name,t.name AS train_name FROM bookings b JOIN passengers p ON b.passenger_id=p.id JOIN trains t ON b.train_id=t.id ORDER BY b.id DESC LIMIT 8").fetchall()
    refunds=con.execute("SELECT COALESCE(SUM(amount),0) FROM refunds").fetchone()[0]
    con.close()
    # Transparent sample-data heuristic used as an AI-style decision-support demo.
    demand=[]
    for t in trains:
        booked=t["seats_booked"] or 0; total=t["seats_total"] or 0
        pct=round(booked/total*100) if total else 0
        recommendation="Consider adding capacity" if pct>=70 else ("Monitor demand" if pct>=35 else "Current capacity appears sufficient")
        demand.append({"train":t,"pct":pct,"recommendation":recommendation})
    return render_template("admin.html",stats=stats,trains=trains,recent=recent,refunds=refunds,demand=demand)

@app.route("/admin/add-train", methods=["POST"])
def add_train():
    fields=[request.form.get(k,"").strip() for k in ["train_no","name","source","destination","departure","arrival","duration"]]
    if not all(fields):
        flash("Complete all train fields.", "danger"); return redirect(url_for("admin"))
    con=db()
    try:
        con.execute("INSERT INTO trains(train_no,name,source,destination,departure,arrival,duration,running_days,status) VALUES(?,?,?,?,?,?,?,'Daily','On Time')",fields)
        con.commit(); flash("Train added.", "success")
    except sqlite3.IntegrityError: flash("Train number already exists.", "danger")
    con.close(); return redirect(url_for("admin"))

@app.route("/admin/status/<int:train_id>", methods=["POST"])
def train_status(train_id):
    status=request.form.get("status","On Time")
    if status not in ["On Time","Delayed 10 min","Delayed 30 min","Cancelled"]: status="On Time"
    con=db(); con.execute("UPDATE trains SET status=? WHERE id=?",(status,train_id)); con.commit(); con.close()
    flash("Train status updated.", "success"); return redirect(url_for("admin"))

@app.route("/health")
def health():
    return {"status":"ok","application":"AI Rail","database":"SQLite"}

init_db()
if __name__=="__main__":
    app.run(debug=True)
