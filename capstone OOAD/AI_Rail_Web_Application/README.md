# AI Rail – Railway Reservation & Train Scheduling Prototype

A two-member OOAD academic prototype following the PPT's selected **layered Python application + relational SQL database** architecture.

## Run locally
1. Install Python 3.10 or later.
2. Open a terminal in this folder.
3. Create and activate a virtual environment (recommended).
4. Install dependencies:
   `pip install -r requirements.txt`
5. Start:
   `python app.py`
6. Open `http://127.0.0.1:5000`.

The SQLite database (`railway.db`) is created automatically and seeded with sample train routes on first run.

## Demonstration flow
1. Register a passenger account.
2. Search Chennai → Coimbatore (or another seeded route) for today's or a future date.
3. Select a class and book a seat.
4. Show the generated PNR/e-ticket.
5. Open My Bookings and cancel the ticket.
6. Show the refund record via the cancellation message and notifications.
7. Open Admin & AI Insights to show occupancy-based demand suggestions, train status updates, adding trains, and booking reports.

## OOAD mapping
- Domain classes/tables: Passenger, Train, Seat, Booking, Refund, Notification.
- Encapsulation / separation of concerns: route handlers coordinate validation and persistence; database schema stores domain state.
- Relationships: Passenger 1..* Booking; Train 1..* Seat; Booking 1..1 Seat for this single-passenger ticket prototype.
- State transitions: BOOKED → CANCELLED; seat AVAILABLE → BOOKED → AVAILABLE.
- Correctness: seat allocation uses a database write transaction and an availability check to reduce double allocation.
- Reports: bookings, cancellations, revenue and seat occupancy.
- AI decision support: transparent occupancy-threshold heuristic for schedule/capacity recommendations. It is illustrative, not a trained ML model.

## Important limitations
- Sample timetable and fares only; no IRCTC or live railway API integration.
- Demo password storage is plain text for classroom simplicity. Do not deploy publicly; production requires password hashing, CSRF protection, authorization, input hardening and secure configuration.
- No real payment gateway or bank refund; refund is a simulated database record.
- The admin page is open for classroom demonstration; production requires role-based admin authentication.
- The demand insight is a rule-based demonstration, not a validated predictive model.
