# Import necessary modules
# This file defines the database models for the expense tracking application.

from extensions import db 
from datetime import datetime
from flask_login import UserMixin

# Database Models
# User model to store user credentials for full financial compliance (KYC) and security

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Core Identity (Captured in your Form)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    dob = db.Column(db.Date, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    
    # System Logic (Automatic)
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    base_currency = db.Column(db.String(3), default='UGX')
    total_balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    expenses = db.relationship('Expense', backref='owner', lazy=True)
    budgets = db.relationship('Budget', backref='owner', lazy=True)

# Expense model to store individual expenses
class Expense(db.Model): 
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    # Captures date and time for notifications
    date_to_handle = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_covered = db.Column(db.Boolean, default=False) #Used to track if expense is covered or pending
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Budget model to store budget allocations per category
class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    amount_allocated = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)