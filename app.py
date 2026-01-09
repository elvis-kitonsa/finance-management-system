from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from extensions import db 
from datetime import datetime, date
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
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
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        dob_str = request.form.get('dob') # This comes as a string "YYYY-MM-DD"
        
        # Check if email or phone already exists
        if User.query.filter((User.email == email) | (User.phone == phone)).first():
            flash('Email or Phone already registered!', 'danger')
            return redirect(url_for('register'))

        # Create new user with only fields present in /templates/register.html
        try:
            new_user = User(
                email=email,
                phone=phone,
                full_name=full_name,
                password_hash=generate_password_hash(password),
                dob=datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None,
                total_balance=0.0
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'danger')
            return redirect(url_for('register'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')
        
        user = User.query.filter((User.email == identifier) | (User.phone == identifier)).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- MAIN DASHBOARD ROUTES (Multi-user) ---

@app.route('/')
@login_required # Dashboard now requires login
def dashboard():
    # CHANGE: Use current_user.id to filter expenses
    all_expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date_to_handle.desc()).all()
    
    # CHANGE: Use current_user.total_balance
    total_balance = current_user.total_balance
    
    # 1. Sum of everything that is NOT 'Savings' (Actual Costs)
    total_spent = sum(exp.amount for exp in all_expenses if exp.category != 'Savings')
    
    # 2. Sum of everything categorized as 'Savings'
    amount_saved = sum(exp.amount for exp in all_expenses if exp.category == 'Savings')
    
    # 3. Total Remaining = Starting Balance - (Everything Spent + Everything Saved)
    total_remaining = total_balance - (total_spent + amount_saved)

    return render_template('dashboard.html', 
                           expenses=all_expenses, 
                           total_balance=total_balance,
                           total_spent=total_spent,
                           total_remaining=total_remaining,
                           amount_saved=amount_saved)

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
        # We use 'description' to match your JavaScript 'expenseData' object
        new_entry = Expense(
            title=data['title'],
            category=data['category'],
            amount=float(data['amount']),
            user_id=current_user.id, # Link it to the logged-in user
            date_to_handle=datetime.now() # Automatically sets the time to right now
        )
        db.session.add(new_entry)
        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Error saving expense: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/delete_expense/<int:expense_id>', methods=['DELETE'])
@login_required # Always ensure user is logged in first
def delete_expense(expense_id):
    # 1. Find the expense in the database
    expense = Expense.query.get_or_404(expense_id)

    # 2. TINY REFINEMENT: Ownership Check
    if expense.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    try:
        # 3. Delete the record
        db.session.delete(expense)
        db.session.commit()
        return jsonify({"status": "success", "message": "Expense reimbursed and deleted"}), 200
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

# --- DATABASE INITIALIZATION ---

with app.app_context():
    db.create_all()

    # Create admin user if it doesn't exist
    if not User.query.filter_by(email="admin@financeflow.com").first():
        admin = User(
            email="admin@financeflow.com",
            password_hash=generate_password_hash("admin123"),
            full_name="Admin User",
            phone="000000000",
            dob=date(1990, 1, 1),
            home_address="System",
            national_id="ADMIN-001",
            terms_agreed=True,
            privacy_consent=True,
            data_accuracy_declaration=True,
            total_balance=0.0 # Initializing balance at 0
        )
        db.session.add(admin)
        db.session.commit()
        print("Database initialized and Admin created!")

if __name__ == '__main__':
    app.run(debug=True)