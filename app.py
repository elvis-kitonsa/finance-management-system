from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from extensions import db 
from datetime import datetime, date
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import extract
from datetime import timedelta
from collections import defaultdict
import requests
import os



# Initialize the application first
# Flask app setup
app = Flask(__name__)

# Basic Configuration - SECRET_KEY and Database URI for SQLAlchemy to use
# Make sure to change 'your-very-secret-key' to a strong secret key in production
app.config['SECRET_KEY'] = 'your-very-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Database - SQLAlchemy
db.init_app(app)

# Initialize Login Manager
# Manages user sessions and authentication
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirects here if login is required

# Import models AFTER db is defined to avoid circular imports
from models import User, Expense, Budget

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- AUTHENTICATION ROUTES ---

# 1. Registration Route
# Handles new user sign-ups
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Match these fields with your registration form - /templates/register.html
        # force the email to lowercase before it even hits the database
        full_name = request.form.get('full_name')
        email = request.form.get('email').strip().lower() # Add .lower() here to standardize email case to lowercase
        username = request.form.get('username').strip().lower() # Capture username
        password = request.form.get('password')
        dob_str = request.form.get('dob') # This comes as a string "YYYY-MM-DD"
        
        # Check if email or phone already exists
        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash('Username or Email already registered!', 'danger')
            return redirect(url_for('register'))

        # Create new user with only fields present in /templates/register.html
        try:
            new_user = User(
                email=email,
                full_name=full_name,
                username=username,
                password_hash=generate_password_hash(password),
                dob=datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None,
                # total_balance=0.0 #This initializes the user's balance at 0 upon registration

                # Fields REQUIRED by your database but HIDDEN from the user
                total_balance=0.0,  # Initializing balance at 0 for new users
                base_currency="UGX"          # Default currency
            )
            db.session.add(new_user)
            db.session.commit()
            # flash('Account created! Please login.', 'success')
            return redirect(url_for('login', registered=True)) # Add a URL parameter instead
        except Exception as e:
            db.session.rollback()
            # This will show you exactly if any other field is missing
            flash(f'Error creating account: {str(e)}', 'danger')
            return redirect(url_for('register'))
        
    return render_template('register.html')

# 2. Login Route
# Handles user login with email or phone number
# Uses both GET and POST methods because it displays the login form and processes it
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Force the database to refresh its connection
    db.session.remove()

    if request.method == 'POST':
        # 1. Get the specific fields from your modern toggle form
        email_val = request.form.get('email')
        password = request.form.get('password')
        
        user = None

        # 2. Logic: Use email address to find user
        if email_val:
            identifier = email_val.strip().lower()
            # This is the "Dual Auth" magic: checks both columns for the input
            user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()

        # 3. Security Check
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            
            #flash(f'Welcome back!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('No account found or invalid credentials.', 'danger')
        
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ROUTE REDIRECTION LOGIC (The Gatekeeper) ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# --- MAIN DASHBOARD ROUTE ---
@app.route('/dashboard')
@login_required 
def dashboard():
    all_expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date_to_handle.desc()).all()
    total_balance = current_user.total_balance
    
    total_spent = sum(exp.amount for exp in all_expenses if exp.category != 'Savings')
    amount_saved = sum(exp.amount for exp in all_expenses if exp.category == 'Savings')
    total_remaining = total_balance - (total_spent + amount_saved)

    # --- NEW INITIALS LOGIC ---
    # This takes "Mubiru Stuart" and turns it into "MS"
    # It also works for "Ismah Lule" -> "IL" or "John" -> "J"
    name_parts = current_user.full_name.split()
    initials = "".join([part[0].upper() for part in name_parts[:2]])

    return render_template('dashboard.html', 
                           expenses=all_expenses, 
                           total_balance=total_balance,
                           total_spent=total_spent,
                           total_remaining=total_remaining,
                           total_saved=amount_saved,
                           initials=initials) # Send initials to the frontend

@app.route('/update_balance', methods=['POST'])
@login_required
def update_balance():
    data = request.get_json()

    # CHANGE: Directly update current_user
    try:
        # 1. Update the fixed Total Balance
        current_user.total_balance = float(data['balance'])
            
        # 2. Check if the "Reset all" toggle was ON
        if data.get('should_reset'):
            # Only delete expenses for THIS user
            Expense.query.filter_by(user_id=current_user.id).delete()
            
        db.session.commit()
        return jsonify({"status": "success", "new_balance": current_user.total_balance})
    except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    data = request.get_json()
    try:
        amount = float(data['amount'])

        # --- NEW BUDGET GUARD START ---
        # 1. Calculate how much the user has already spent or saved
        all_expenses = Expense.query.filter_by(user_id=current_user.id).all()
        total_spent = sum(exp.amount for exp in all_expenses if exp.category != 'Savings')
        amount_saved = sum(exp.amount for exp in all_expenses if exp.category == 'Savings')
        
        # 2. Determine the actual remaining balance
        total_remaining = current_user.total_balance - (total_spent + amount_saved)

        # 3. Validation: Stop the process if the new amount is too high
        if amount > total_remaining:
            return jsonify({
                "status": "error", 
                "message": f"Insufficient funds. You only have UGX {total_remaining:,.0f} remaining."
            }), 400
        # --- NEW BUDGET GUARD END ---

        new_entry = Expense(
            title=data['title'],
            category=data['category'],
            amount=amount,
            user_id=current_user.id,
            date_to_handle=datetime.now(),
            is_covered=False # TARGET 1: Set to False so it appears as "Pending"
        )
        
        # TARGET 2: Remove the automatic deduction. 
        # Money should only leave the balance when 'Mark as Paid' is clicked
        
        db.session.add(new_entry)
        db.session.commit()
        return jsonify({"status": "success", "new_balance": current_user.total_balance})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/delete_expense/<int:expense_id>', methods=['DELETE'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    try:
        # NEW: If the expense was "covered/paid", add the money back to the balance
        if expense.is_covered:
            current_user.total_balance += expense.amount
            
        db.session.delete(expense)
        db.session.commit()
        return jsonify({"status": "success", "new_balance": current_user.total_balance}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

# Update description with new content set in the Transaction Receipt card
# This is the card that pops up when you click on an already registered expense in the dashboard list

@app.route('/update_expense_description/<int:expense_id>', methods=['POST'])
@login_required
def update_expense_description(expense_id):
    data = request.get_json()
    new_title = data.get('title')
    
    # 1. Find the expense in the database
    expense = Expense.query.get_or_404(expense_id)

    # 2. TINY REFINEMENT: Ownership Check
    if expense.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    if new_title:
        # 3. Update the title/description field
        expense.title = new_title
    
        try:
            # 4. Save changes
            db.session.commit()
            return jsonify({"status": "success", "message": "Description updated"}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500

# MARK AS PAID ROUTE
# Updates the 'is_covered' status of an expense to True
@app.route('/mark_paid/<int:expense_id>', methods=['POST'])
@login_required
def mark_paid(expense_id):
    # 1. Locate the specific expense
    expense = Expense.query.get_or_404(expense_id)

    # 2. Security Check: Ensure this expense belongs to the logged-in user
    if expense.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    try:
        # 3. Update the status and save to the database
        # The dashboard math will automatically handle the "Remaining" display.
        expense.is_covered = True
        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ADDITIONAL PAGES ROUTES ---

def get_live_rates():
    try:
        # Using a free API (Example: ExchangeRate-API)
        # You can get a free key at https://www.exchangerate-api.com/
        API_KEY = "your_api_key_here" 
        url = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/UGX"
        response = requests.get(url)
        data = response.json()
        if data["result"] == "success":
            return data["conversion_rates"]
    except Exception as e:
        print(f"Rate fetch failed: {e}")
    
    # Fallback rates if the API fails or is offline
    return {"USD": 0.00027, "EUR": 0.00025, "GBP": 0.00021, "KES": 0.039}

@app.route('/accounts') # This matches your sidebar link
@login_required
def budgets():

    # 1. Define the mapping for icons and colors
    category_map = {
        # Essential & Home
        'Food': {'name': 'Food & Dining', 'icon': 'bi-cup-straw', 'color': '#ffc107'},
        'Transport': {'name': 'Transport & Fuel', 'icon': 'bi-fuel-pump', 'color': '#0dcaf0'},
        'Bills': {'name': 'Utilities & Bills', 'icon': 'bi-lightning-charge', 'color': '#fd7e14'},
        'Rent': {'name': 'Rent & Mortgage', 'icon': 'bi-house-door', 'color': '#6610f2'},
        'Health': {'name': 'Health & Medical', 'icon': 'bi-capsule', 'color': '#dc3545'},
        'Insurance': {'name': 'Insurance', 'icon': 'bi-shield-shaded', 'color': '#0d6efd'},
        
        # Lifestyle & Personal
        'Shopping': {'name': 'Shopping & Clothes', 'icon': 'bi-bag-heart', 'color': '#e83e8c'},
        'Entertainment': {'name': 'Entertainment & Fun', 'icon': 'bi-ticket-perforated', 'color': '#6f42c1'},
        'Education': {'name': 'Learning & Skills', 'icon': 'bi-book', 'color': '#17a2b8'},
        'PersonalCare': {'name': 'Personal Care', 'icon': 'bi-scissors', 'color': '#adb5bd'},
        'Gifts': {'name': 'Gifts & Donations', 'icon': 'bi-gift', 'color': '#ff6b6b'},
        
        # Financial & Future
        'Savings': {'name': 'Savings Deposit', 'icon': 'bi-bank', 'color': '#198754'},
        'Investment': {'name': 'Investment Fund', 'icon': 'bi-graph-up-arrow', 'color': '#20c997'},
        'Debt': {'name': 'Debt & Loans', 'icon': 'bi-credit-card-2-front', 'color': '#343a40'},
        'Emergency': {'name': 'Emergency Fund', 'icon': 'bi-shield-lock', 'color': '#dc3545'},
        'Crypto': {'name': 'Crypto & Digital Assets', 'icon': 'bi-currency-bitcoin', 'color': '#f7931a'}
    }

    # 2. Fetch actual data from the logged-in user to ensure dashboard sync
    expenses = current_user.expenses
    total_balance = current_user.total_balance
    
    # 3. Process only categories that have expenses
    active_categories = {}
    for exp in expenses:
        cat_key = exp.category
        if cat_key not in active_categories:
            mapping = category_map.get(cat_key, {'name': cat_key, 'icon': 'bi-folder', 'color': '#0047FF'})
            active_categories[cat_key] = {
                'display_name': mapping['name'],
                'icon': mapping['icon'],
                'color': mapping['color'],
                'total': 0,
                'expense_list': []  # RENAME THIS FROM 'items' TO 'expense_list'
            }
        active_categories[cat_key]['total'] += exp.amount
        active_categories[cat_key]['expense_list'].append(exp)

    # 4. Logic for initials (keeping it consistent with the dashboard)
    name_parts = current_user.full_name.split()
    initials = "".join([part[0].upper() for part in name_parts[:2]])

    # 5. Manual Savings Catalog Data (Static for now, can move to DB later)
    # This fulfills your requirement for a deeper detail savings catalog [cite: 2026-01-01]
    savings_goals = [
        {'name': 'Emergency Fund', 'target': 2000000, 'current': 500000, 'icon': 'bi-shield-check'},
        {'name': 'New Laptop', 'target': 3500000, 'current': 1200000, 'icon': 'bi-laptop'}
    ]
    
    rates = get_live_rates()
    # 6. Render the page
    return render_template('accounts.html', 
                           total_balance=total_balance, 
                           categories=active_categories,
                           rates=rates, # Pass the live rates here
                           savings_goals=savings_goals,
                           initials=initials)

# ANALYTICS ROUTE
# Displays charts and graphs pertaining to user expenses
@app.route('/analytics')
@login_required
def analytics():
    # 1. Fetch user expenses
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date_to_handle.asc()).all()
    
    # 2. UI Helpers for Navbar & Date Display
    name_parts = current_user.full_name.split()
    initials = "".join([part[0].upper() for part in name_parts[:2]])
    
    now = datetime.utcnow()
    current_day = now.strftime('%A')
    current_date = now.strftime('%b %d, %Y')
    
    # Handle empty state to avoid division by zero
    if not expenses:
        return render_template('analytics.html', 
                               initials=initials,
                               current_day=current_day,
                               current_date=current_date,
                               daily_data={}, 
                               total_spent=0, 
                               avg_burn=0, 
                               projected_date="N/A", 
                               days_left=0, 
                               total_balance=current_user.total_balance)

    # 3. Process Transactions for the Cumulative Burn Graph
    daily_data = defaultdict(float)
    cumulative_burn = 0
    
    # We sort explicitly to ensure the line graph moves forward in time
    sorted_expenses = sorted(expenses, key=lambda x: x.date_to_handle)

    for e in sorted_expenses:
        date_str = e.date_to_handle.strftime('%Y-%m-%d')
        
        # Logic: If it's NOT a savings deposit, it's a 'Burn' (Spending)
        if e.category != 'Savings':
            # Use abs() to ensure the graph trends UPWARD even if stored as negative
            cumulative_burn += abs(e.amount)
        
        # Capture the cumulative state at the end of this specific date
        daily_data[date_str] = cumulative_burn 

    # 4. Burn Rate & Runway Calculations
    # Calculate days since the very first expense record
    start_date = sorted_expenses[0].date_to_handle.date()
    today = datetime.utcnow().date()
    days_elapsed = (today - start_date).days + 1 # +1 to avoid division by zero on day one
    
    # Avg Daily Burn = Total Outflow / Days Active
    avg_daily_burn = cumulative_burn / days_elapsed
    
    # Current Wallet Balance (This is your UGX 0.00 cash on hand)
    current_wallet_balance = current_user.total_balance
    
    # Runway Calculation: How many days until balance hits 0
    if avg_daily_burn > 0:
        days_left = max(0, current_wallet_balance / avg_daily_burn)
        projected_date_obj = datetime.utcnow() + timedelta(days=days_left)
        projected_date_str = projected_date_obj.strftime('%d %b, %Y')
    else:
        days_left = 0
        projected_date_str = "N/A"

    return render_template('analytics.html', 
                           initials=initials,
                           current_day=current_day,
                           current_date=current_date,
                           daily_data=dict(daily_data), # Convert back to regular dict for JS
                           total_spent=cumulative_burn,
                           avg_burn=avg_daily_burn,
                           projected_date=projected_date_str,
                           days_left=int(days_left),
                           total_balance=current_wallet_balance)

# PRINT RECEIPT ROUTE
# Generates printable expense reports based on user selection
@app.route('/print_receipt')
@login_required
def print_receipt():
    report_type = request.args.get('type')
    period = request.args.get('period') # e.g., "2026-01-22" or "2026-01"
    
    query = Expense.query.filter_by(user_id=current_user.id)

    if report_type == 'weekly':
        start_date = datetime.strptime(period, '%Y-%m-%d').date()
        end_date = start_date + timedelta(days=7)
        expenses = query.filter(Expense.date_to_handle >= start_date, Expense.date_to_handle < end_date).all()
        title = f"Weekly Statement ({start_date} to {end_date})"
    
    elif report_type == 'monthly':
        year, month = map(int, period.split('-'))
        expenses = query.filter(extract('month', Expense.date_to_handle) == month, 
                                extract('year', Expense.date_to_handle) == year).all()
        title = f"Monthly Statement ({period})"
    
    else: # yearly
        expenses = query.filter(extract('year', Expense.date_to_handle) == int(period)).all()
        title = f"Yearly Summary ({period})"

    total_spent = sum(exp.amount for exp in expenses)
    
    return render_template('receipt_template.html', 
                           expenses=expenses, 
                           title=title, 
                           total_spent=total_spent,
                           total_balance=current_user.total_balance)

# --- DATABASE INITIALIZATION ---

with app.app_context():
    db.create_all()

    # Create admin user if it doesn't exist
    if not User.query.filter_by(email="admin@financeflow.com").first():
        admin = User(
            email="admin@financeflow.com",
            username="admin", 
            password_hash=generate_password_hash("admin123"),
            full_name="Admin User",
            dob=date(1990, 1, 1),
            total_balance=0.0 # Initializing balance at 0
        )
        db.session.add(admin)
        db.session.commit()
        print("Database initialized and Admin created!")

if __name__ == '__main__':
    app.run(debug=True)