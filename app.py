import requests
import calendar

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from extensions import db 
from datetime import datetime, date
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import extract
from datetime import datetime, timedelta
from collections import defaultdict




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
    return db.session.get(User, int(user_id))

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

            # --- NEW: Reactivation Logic ---
            # Allows a user that deactivated their account to be able to to get it back
            if hasattr(user, 'status') and user.status == "Deactivated":
                user.status = "Active"
                try:
                    db.session.commit()
                    flash("Welcome back! Your account has been reactivated.", "success")
                except Exception:
                    db.session.rollback()
            # -------------------------------

            login_user(user)
            return redirect(url_for('dashboard'))
        
            #flash(f'Welcome back!', 'success')
        
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
    
    # This is your fixed budget that you set yourself
    budget_ceiling = current_user.total_balance
    
    # Calculate what has actually been spent
    total_spent = sum(exp.amount for exp in all_expenses if exp.category != 'Savings')
    amount_saved = sum(exp.amount for exp in all_expenses if exp.category == 'Savings')

    # FIX: The "Remaining" is the Budget minus what is gone
    total_remaining = budget_ceiling - (total_spent + amount_saved)

    # --- NEW INITIALS LOGIC ---
    # This takes "Mubiru Stuart" and turns it into "MS"
    # It also works for "Ismah Lule" -> "IL" or "John" -> "J"
    name_parts = current_user.full_name.split()
    initials = "".join([part[0].upper() for part in name_parts[:2]])

    return render_template('dashboard.html', 
                           expenses=all_expenses, 
                           total_balance=budget_ceiling, # This stays fixed at the amount you set
                           total_spent=total_spent,
                           total_remaining=total_remaining,
                           total_saved=amount_saved,
                           initials=initials) # Send initials to the frontend

# --- EXPENSE MANAGEMENT ROUTES ---
# 1. Update Balance Route
# Updates the user's total balance and optionally resets expenses
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

# 2. Add Expense Route
# Adds a new expense entry for the logged-in user
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

# 3. Delete Expense Route
# Deletes an expense entry by its ID
@app.route('/delete_expense/<int:expense_id>', methods=['DELETE'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    try:
        # We want the budget to stay exactly what the user set it to initially.    
        db.session.delete(expense)
        db.session.commit()

        # Return the original, unchanged balance
        return jsonify({"status": "success", "new_balance": current_user.total_balance}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

# 4. Update Expense Description Route
# Updates the title/description of an existing expense
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

# 5. MARK AS PAID ROUTE
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

    # NEW: Initialize category_data for the doughnut chart
    category_data = defaultdict(float)
    
    # Handle empty state to avoid division by zero
    if not expenses:
        return render_template('analytics.html', 
                               initials=initials,
                               current_day=current_day,
                               current_date=current_date,
                               expenses=[], # Keep as empty list
                               daily_data={},
                               category_data={'No Data': 0}, # Add a placeholder 
                               total_spent=0, 
                               avg_burn=0, 
                               projected_date="N/A", 
                               days_left=0, 
                               savings_ratio=100, # Added: 100% of budget is "saved" if nothing is spent
                               spend_ratio=0,     # Added: 0% spent
                               days_remaining=max(1, calendar.monthrange(now.year, now.month)[1] - now.day),
                               daily_limit=current_user.total_balance / max(1, calendar.monthrange(now.year, now.month)[1] - now.day),
                               total_budget=current_user.total_balance,
                               total_remaining=current_user.total_balance)

    # 3. Process Transactions for the Cumulative Burn Graph
    daily_data = defaultdict(float)
    cumulative_burn = 0
    
    # We sort explicitly to ensure the line graph moves forward in time
    sorted_expenses = sorted(expenses, key=lambda x: x.date_to_handle)

    for e in sorted_expenses:
        date_str = e.date_to_handle.strftime('%Y-%m-%d')
        
        # We only 'burn' money on spending, not savings allocations
        if e.category != 'Savings':

            # 1. DEFINE THE AMOUNT HERE
            amount = abs(e.amount)

            # Use abs() to ensure the graph trends UPWARD even if stored as negative
            cumulative_burn += abs(e.amount)

            # NEW: Group amounts by category for the doughnut chart
            category_data[e.category] += amount
        
        # Capture the cumulative state at the end of this specific date
        daily_data[date_str] = cumulative_burn 

    # 4. Burn Rate & Runway Calculations
    # Calculate days since the very first expense record
    start_date = sorted_expenses[0].date_to_handle.date()
    today = datetime.utcnow().date()
    days_elapsed = (today - start_date).days + 1 # +1 to avoid division by zero on day one
    
    # Avg Daily Burn = Total Outflow / Days Active
    avg_daily_burn = cumulative_burn / days_elapsed
    
    # 4. THE FIX: Calculate Real Remaining Cash
    # Matches Dashboard: Total Set - (Spent + Saved)
    total_spent_so_far = sum(abs(e.amount) for e in expenses if e.category != 'Savings')
    total_saved_so_far = sum(abs(e.amount) for e in expenses if e.category == 'Savings')
    effective_balance = current_user.total_balance - (total_spent_so_far + total_saved_so_far)

    # --- ADD THIS NEW LOGIC HERE ---
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    days_remaining = max(1, days_in_month - now.day) 
    daily_limit = effective_balance / days_remaining
    # -------------------------------

    # 5. Calculate Real Runway
    # 625,000 / 491,667 = ~1.27 Days
    if avg_daily_burn > 0:
        days_left = round(effective_balance / avg_daily_burn) # Use 'effective_balance' because that's what you defined
        projected_date = now + timedelta(days=days_left)
        projected_date_str = projected_date.strftime('%d %b, %Y')
    else:
        days_left = 0
        projected_date_str = "N/A"

    # 6. Savings Ratio Calculation
    # Your "Budget" is the original total_balance you set
    starting_budget = current_user.total_balance
    
    if starting_budget > 0:
        # Savings Ratio = (Remaining Cash + Savings) / Total Starting Budget
        # This shows what % of your original money isn't "burned" yet
        savings_ratio = ((effective_balance + total_saved_so_far) / starting_budget) * 100
        spend_ratio = 100 - savings_ratio
    else:
        savings_ratio = 0
        spend_ratio = 0

    return render_template('analytics.html', 
                           initials=initials,
                           current_day=now.strftime('%A'),
                           current_date=now.strftime('%b %d, %Y'),
                           daily_data=dict(daily_data),
                           total_spent=cumulative_burn,
                           avg_burn=avg_daily_burn,
                           projected_date=projected_date_str,
                           days_left=int(days_left), # Will now show 1 Day
                           savings_ratio=savings_ratio, 
                           spend_ratio=spend_ratio,
                           days_remaining=days_remaining, # For daily limit display (Used to indicate how many days are left in the month)
                           daily_limit=daily_limit,
                           category_data=dict(category_data),
                           total_budget=current_user.total_balance, # stays fixed at the set amount - 2.5M
                           total_remaining=effective_balance) # actual balance with some expenses added

# PRINT RECEIPT ROUTE - Used in the accounts.html section
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

# USER PROFILE ROUTE
# Displays the user's profile page with editable and non-editable fields
@app.route('/profile')
@login_required
def profile():
    user = current_user
    now = datetime.now() 

    # 1. Initials Logic (Safe check for KE initials)
    # This keeps your top-right avatar style consistent
    names = user.full_name.split() if user.full_name else []
    initials = "".join([n[0].upper() for n in names[:2]]) if names else "??"

    # 2. Safe Data Fetching
    # We use 'getattr' to provide a fallback value if the column is missing in DB
    total_budget = getattr(user, 'total_budget', 2500000) 
    
    # Check if 'created_at' exists, otherwise use a default string
    if hasattr(user, 'created_at') and user.created_at:
        date_joined = user.created_at.strftime("%B %d, %Y")
    else:
        date_joined = "January 2026"

    # 3. DOB Fetching (Safe)
    dob_value = getattr(user, 'dob', 'Not Provided')

    return render_template('profile.html', 
                           full_name=user.full_name,
                           username=user.username,
                           email=user.email,
                           dob=getattr(user, 'dob', '2000-08-10'),
                           date_joined=date_joined,
                           total_budget=total_budget,
                           user_initials=initials,
                           day_name=now.strftime("%A"),
                           current_date=now.strftime("%b %d, %Y"))

# UPDATE PROFILE ROUTE
# When accessed, this route will display a form to update the user's profile
# The form will be pre-filled with the current user's information
@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    user = current_user
    new_username = request.form.get('username')
    new_email = request.form.get('email')
    
    # 1. Validation for empty fields
    if not new_username or not new_email:
        flash("Username and Email cannot be empty.", "danger")
        return redirect(url_for('profile'))
        
    # 2. Check if the data is actually different from what is already saved
    if new_username == user.username and new_email == user.email:
        flash("No changes were made.", "info")
        return redirect(url_for('profile'))
    
    # 3. Apply changes only if they are new
    user.username = new_username
    user.email = new_email
    
    # 4. Commit with Error Handling
    try:
        db.session.commit()
        flash("Profile updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error: Username or email is already in use by another account.", "danger")
    
    return redirect(url_for('profile'))

# DEACTIVATE ACCOUNT ROUTE
# This logic will flip the status and log the user out immediately.
@app.route('/profile/deactivate', methods=['POST'])
@login_required
def deactivate_account():
    user = current_user
    
    # Optional: You could set user.is_active = False here if your model supports it
    # For now, we will perform a safe deletion or status update
    try:
        # If you want to completely remove them:
        # db.session.delete(user) 
        
        # Recommendation: Just flag them as inactive
        user.status = "Deactivated" 
        db.session.commit()
        
        logout_user() # Import this from flask_login
        flash("Your account has been deactivated. We're sorry to see you go.", "info")
        return redirect(url_for('login'))
    except Exception as e:
        db.session.rollback()
        flash("An error occurred during deactivation.", "danger")
        return redirect(url_for('profile'))
    
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