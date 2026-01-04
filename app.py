from flask import Flask, render_template, request, jsonify
from extensions import db 
from datetime import datetime, date
from werkzeug.security import generate_password_hash
import os

app = Flask(__name__)

# Basic Configuration
app.config['SECRET_KEY'] = 'your-very-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
db.init_app(app)

# Import models AFTER db is defined to avoid circular imports
from models import User, Expense, Budget

# --- ROUTES ---

@app.route('/')
def dashboard():
    # Fetch the admin user
    user = User.query.filter_by(email="admin@financeflow.com").first()
    all_expenses = Expense.query.order_by(Expense.date_to_handle.desc()).all()
    
    total_balance = user.total_balance if user else 0
    
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
def update_balance():
    data = request.get_json()
    user = User.query.filter_by(email="admin@financeflow.com").first() 
    if user:
        user.total_balance = float(data['balance'])
        db.session.commit()
        return jsonify({"status": "success", "new_balance": user.total_balance})
    return jsonify({"status": "error"}), 404

@app.route('/add_expense', methods=['POST'])
def add_expense():
    data = request.get_json()
    user = User.query.filter_by(email="admin@financeflow.com").first()
    
    if user:
        try:
            # We use 'description' to match your JavaScript 'expenseData' object
            new_entry = Expense(
                description=data['description'],
                category=data['category'],
                amount=float(data['amount']),
                user_id=user.id,
                # Automatically sets the time to right now
                date_to_handle=datetime.now() 
            )
            db.session.add(new_entry)
            db.session.commit()
            return jsonify({"status": "success"})
        except Exception as e:
            print(f"Error saving expense: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
            
    return jsonify({"status": "error", "message": "User not found"}), 404

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