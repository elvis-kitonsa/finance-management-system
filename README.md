FinanceFlow | FMS

FinanceFlow is a modern Finance Management System (FMS) designed to help users track expenses, allocate budgets, and manage financial health with a clean, intuitive interface. Built with Flask, it features real-time analytics and secure authentication.

🚀 Features

    Secure Authentication: Robust Login and Register portal designed for future-proof biometric integration.

    Expense Tracking: Add and manage expenses with specific "dates to handle" and category-based allocation.

    Smart Analytics: Dynamic charts visualizing "Cumulative Burn Rate," savings ratios, and daily spending limits.

    Budget Allocation: Set a total monthly budget and track your effective balance in real-time.

    Notifications: Automated in-app system to alert users of upcoming expense deadlines.

    Currency & Payments: Support for currency conversion and integrated workflows for PayPal and Mobile Money.

🛠️ Tech Stack

    Backend: Python (Flask)

    Database: SQLAlchemy (SQLite/PostgreSQL)

    Frontend: HTML5, CSS3 (Custom variables), Bootstrap 5, Lucide Icons

    Charting: Chart.js / DefaultDict logic for data processing

📂 Project Structure

    ├── app.py              # Main application logic and routes
    ├── models.py           # Database schemas (User, Expense)
    ├── static/
    │   ├── css/            # Custom styling (edits.css)
    │   └── js/             # Frontend logic
    └── templates/          # Jinja2 HTML templates

⚙️ Installation & Setup

    1. Clone the repository:

    git clone https://github.com/your-username/FinanceFlow.git
    cd FinanceFlow

    2. Set up a virtual environment:

    python -m venv venv
    source venv/Scripts/activate  # Windows

    3. Install dependencies:

    pip install flask flask_sqlalchemy flask_login

    4. Initialize the database:

    from app import app, db
    with app.app_context():
        db.create_all()

    5. Run the app:

    python app.py

💡 Future Roadmap

    Complete implementation of the PayPal and Mobile Money APIs - to handle and allocate real money.

    Refine the Settings panel for custom notification lead times.

    Advanced currency conversion via external API integration.

🛡️ Security Architecture

    Session Management: Implements Flask-Login for secure user session handling and protected routes.

    Password Hashing: Uses Werkzeug security helpers to ensure passwords are never stored in plain text.

    CSRF Protection: All forms are protected against Cross-Site Request Forgery to prevent unauthorized actions.

    Data Integrity: Foreign key constraints ensure that expenses are strictly tied to the authenticated user.

📊 Application Workflow

    Onboarding: User registers via the secure portal.

    Budgeting: User sets a total balance in the "Accounts" section.

    Tracking: Expenses are recorded with specific categories (Food, Transport, Savings, etc.).

    Analytics: The system processes raw data to provide burn rates and runway projections.

    Accounts: The system allows user to set budgets in other currencies, and print out expense receipts.

📝 Environment Variables

    Create a .env file in the root directory to store sensitive configurations:

    FLASK_APP=app.py
    FLASK_ENV=development
    SECRET_KEY=your_super_secret_key_here
    DATABASE_URL=sqlite:///finance.db

📱 Usage Guide

    Recording Expenses: Click the "Record Expense" button on the dashboard. Ensure you select the correct "Date to Handle" to trigger the notification system.

    Reading Analytics: The "Cumulative Burn" graph shows your total spending over time. If the line is too steep, the "Daily Limit" card will automatically adjust to help you stay within budget.

🤝 Contributing

Contributions are welcome! If you'd like to improve the Currency Conversion logic or Notification UI:

    Fork the Project.

    Create your Feature Branch (git checkout -b feature/AmazingFeature).

    Commit your Changes (git commit -m 'Add some AmazingFeature').

    Push to the Branch (git push origin feature/AmazingFeature).

    Open a Pull Request.

📸 App Preview

<table border="0">
  <tr>
    <td><b align="center">Main Dashboard</b><br><img src="static/img/dashboard.png" width="400"></td>
    <td><b align="center">Analytics & Burn Rate</b><br><img src="static/img/analytics.png" width="400"></td>
  </tr>
  <tr>
    <td colspan="2" align="center"><b align="center">Account & Budget Allocation</b><br><img src="static/img/accounts.png" width="600"></td>
  </tr>
</table>
