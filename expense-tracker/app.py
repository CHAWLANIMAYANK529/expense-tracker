from flask import Flask, render_template, request, redirect, session, flash, make_response
import sqlite3
import csv
from werkzeug.security import generate_password_hash, check_password_hash
from io import StringIO
app = Flask(__name__)
app.secret_key = 'super_secure_secret_key'

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            budget REAL DEFAULT 5000
        )
    ''')

    # Expenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()


init_db()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("Email already registered!")
            conn.close()
            return redirect('/register')

        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, hashed_password)
        )

        conn.commit()
        conn.close()

        flash("Registration successful! Please login.")
        return redirect('/login')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        )

        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            return redirect('/dashboard')

        flash("Invalid email or password!")

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    search = request.args.get('search', '')
    category = request.args.get('category', '')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Base query
    query = "SELECT * FROM expenses WHERE user_id=?"
    params = [session['user_id']]

    # Search filter
    if search:
        query += " AND title LIKE ?"
        params.append(f"%{search}%")

    # Category filter
    if category:
        query += " AND category=?"
        params.append(category)

    cursor.execute(query, params)
    expenses = cursor.fetchall()

    # Total amount
    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id=?",
        (session['user_id'],)
    )
    total = cursor.fetchone()[0] or 0

    # Count
    cursor.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id=?",
        (session['user_id'],)
    )
    count = cursor.fetchone()[0]

    # Budget
    cursor.execute(
        "SELECT budget FROM users WHERE id=?",
        (session['user_id'],)
    )
    budget = cursor.fetchone()[0]

    # Chart data
    cursor.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE user_id=?
        GROUP BY category
    """, (session['user_id'],))

    category_data = cursor.fetchall()

    conn.close()

    labels = [item[0] for item in category_data]
    values = [item[1] for item in category_data]

    warning = total > budget

    return render_template(
        'dashboard.html',
        name=session['user_name'],
        expenses=expenses,
        total=total,
        count=count,
        labels=labels,
        values=values,
        budget=budget,
        warning=warning,
        search=search,
        category=category
    )

@app.route('/add-expense', methods=['GET', 'POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO expenses (user_id, title, amount, category, date)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            title,
            amount,
            category,
            date
        ))

        conn.commit()
        conn.close()
        flash("Expense added successfully!")

        return redirect('/dashboard')

    return render_template('add_expense.html')

@app.route('/edit-expense/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        title = request.form['title']
        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']

        cursor.execute('''
            UPDATE expenses
            SET title=?, amount=?, category=?, date=?
            WHERE id=? AND user_id=?
        ''', (
            title,
            amount,
            category,
            date,
            id,
            session['user_id']
        ))

        conn.commit()
        conn.close()
        flash("Expense updated successfully!")

        return redirect('/dashboard')

    cursor.execute(
        "SELECT * FROM expenses WHERE id=? AND user_id=?",
        (id, session['user_id'])
    )

    expense = cursor.fetchone()
    conn.close()

    return render_template('edit_expense.html', expense=expense)


@app.route('/delete-expense/<int:id>')
def delete_expense(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM expenses WHERE id=? AND user_id=?",
        (id, session['user_id'])
    )

    conn.commit()
    conn.close()

    return redirect('/dashboard')
@app.route('/export-csv')
def export_csv():
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute(
        "SELECT title, amount, category, date FROM expenses WHERE user_id=?",
        (session['user_id'],)
    )

    expenses = cursor.fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(['Title', 'Amount', 'Category', 'Date'])

    for expense in expenses:
        writer.writerow(expense)

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=expenses.csv"
    response.headers["Content-type"] = "text/csv"

    return response
@app.route('/set-budget', methods=['POST'])
def set_budget():
    if 'user_id' not in session:
        return redirect('/login')

    budget = request.form['budget']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET budget=? WHERE id=?",
        (budget, session['user_id'])
    )

    conn.commit()
    conn.close()
    flash("Expense deleted successfully!")

    return redirect('/dashboard')
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)