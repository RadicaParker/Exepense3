import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from datetime import date

DB_FILE = "expense_app.db"

st.set_page_config(page_title="TaxHacker Expense Module", page_icon="💸", layout="wide")


def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            name TEXT,
            password TEXT,
            role TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date TEXT,
            user_email TEXT,
            amoeba TEXT,
            category TEXT,
            description TEXT,
            amount REAL,
            payment_method TEXT,
            receipt_name TEXT,
            status TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS amoebas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)

    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    admin_count = cur.fetchone()[0]

    if admin_count == 0:
        cur.execute("""
            INSERT OR IGNORE INTO users (email, name, password, role)
            VALUES (?, ?, ?, ?)
        """, (
            "admin@taxhacker.com",
            "Admin",
            hash_password("Admin123!"),
            "admin"
        ))

    cur.execute("SELECT COUNT(*) FROM amoebas")
    if cur.fetchone()[0] == 0:
        default_amoebas = [("Marketing",), ("Sales",), ("Finance",), ("Operations",), ("Product",)]
        cur.executemany("INSERT INTO amoebas (name) VALUES (?)", default_amoebas)

    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        default_categories = [("Travel",), ("Meal",), ("Software",), ("Office Supplies",), ("Other",)]
        cur.executemany("INSERT INTO categories (name) VALUES (?)", default_categories)

    cur.execute("SELECT COUNT(*) FROM payment_methods")
    if cur.fetchone()[0] == 0:
        default_methods = [("Corporate Card",), ("Cash",), ("Personal Card",), ("Bank Transfer",)]
        cur.executemany("INSERT INTO payment_methods (name) VALUES (?)", default_methods)

    conn.commit()
    conn.close()


def create_user(email, name, password, role="user"):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users (email, name, password, role)
            VALUES (?, ?, ?, ?)
        """, (email, name, hash_password(password), role))
        conn.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "This email is already registered."
    finally:
        conn.close()


def login_user(email, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, email, name, role
        FROM users
        WHERE email = ? AND password = ?
    """, (email, hash_password(password)))
    user = cur.fetchone()
    conn.close()
    return user


def get_all_users():
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT id, email, name, role
        FROM users
        ORDER BY id
    """, conn)
    conn.close()
    return df


def delete_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ? AND role != 'admin'", (user_id,))
    conn.commit()
    conn.close()


def insert_expense(expense_date, user_email, amoeba, category, description, amount, payment_method, receipt_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO expenses (
            expense_date, user_email, amoeba, category, description,
            amount, payment_method, receipt_name, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(expense_date), user_email, amoeba, category, description,
        amount, payment_method, receipt_name, "Submitted"
    ))
    conn.commit()
    conn.close()


def get_user_expenses(user_email):
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT id, expense_date, user_email, amoeba, category, description,
               amount, payment_method, receipt_name, status
        FROM expenses
        WHERE user_email = ?
        ORDER BY id DESC
    """, conn, params=(user_email,))
    conn.close()
    return df


def get_all_expenses():
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT id, expense_date, user_email, amoeba, category, description,
               amount, payment_method, receipt_name, status
        FROM expenses
        ORDER BY id DESC
    """, conn)
    conn.close()
    return df


def get_master_data(table_name):
    conn = get_conn()
    df = pd.read_sql_query(f"SELECT id, name FROM {table_name} ORDER BY name", conn)
    conn.close()
    return df


def get_master_names(table_name):
    df = get_master_data(table_name)
    return df["name"].tolist()


def add_master_item(table_name, name):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f"INSERT INTO {table_name} (name) VALUES (?)", (name,))
        conn.commit()
        return True, "Added successfully."
    except sqlite3.IntegrityError:
        return False, "This item already exists."
    finally:
        conn.close()


def delete_master_item(table_name, item_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {table_name} WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def logout():
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_email = ""
    st.session_state.user_role = ""


init_db()

for key in ["logged_in", "user_name", "user_email", "user_role"]:
    if key not in st.session_state:
        st.session_state[key] = False if key == "logged_in" else ""

st.title("💸 TaxHacker Expense Module")

if not st.session_state.logged_in:
    st.info("Please log in to continue.")

    tab1, tab2 = st.tabs(["Login", "Create Account"])

    with tab1:
        st.subheader("Login")
        st.caption("Default admin login: admin@taxhacker.com / Admin123!")

        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

            if submitted:
                user = login_user(email, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_email = user[1]
                    st.session_state.user_name = user[2]
                    st.session_state.user_role = user[3]
                    st.success("Login successful.")
                    st.rerun()
                else:
                    st.error("Incorrect email or password.")

    with tab2:
        st.subheader("Create User Account")

        with st.form("signup_form"):
            name = st.text_input("Full Name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Create Account")

            if submitted:
                if not name or not email or not password:
                    st.error("Please fill in all fields.")
                elif password != confirm_password:
                    st.error("Passwords do not match.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    ok, msg = create_user(email, name, password, role="user")
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

else:
    st.sidebar.success(f"Logged in as {st.session_state.user_name}")
    st.sidebar.write(f"Role: {st.session_state.user_role}")

    if st.session_state.user_role == "admin":
        menu = st.sidebar.radio(
            "Navigation",
            ["Expense Form", "My Expenses", "All Expenses", "User Management", "Master Data"]
        )
    else:
        menu = st.sidebar.radio("Navigation", ["Expense Form", "My Expenses"])

    if st.sidebar.button("Logout"):
        logout()
        st.rerun()

    if menu == "Expense Form":
        st.subheader("Submit Expense")

        amoeba_options = get_master_names("amoebas")
        category_options = get_master_names("categories")
        payment_method_options = get_master_names("payment_methods")

        with st.form("expense_form"):
            col1, col2 = st.columns(2)

            with col1:
                expense_date = st.date_input("Expense Date", value=date.today())
                amoeba = st.selectbox("Amoeba / Department", amoeba_options)
                category = st.selectbox("Expense Category", category_options)

            with col2:
                amount = st.number_input("Amount", min_value=0.0, step=1.0, format="%.2f")
                payment_method = st.selectbox("Payment Method", payment_method_options)
                receipt = st.file_uploader("Upload Receipt (optional)", type=["pdf", "png", "jpg", "jpeg"])

            description = st.text_area("Description")
            submitted = st.form_submit_button("Save Expense")

            if submitted:
                if amount <= 0:
                    st.error("Amount must be greater than 0.")
                else:
                    receipt_name = receipt.name if receipt is not None else ""
                    insert_expense(
                        expense_date=expense_date,
                        user_email=st.session_state.user_email,
                        amoeba=amoeba,
                        category=category,
                        description=description,
                        amount=amount,
                        payment_method=payment_method,
                        receipt_name=receipt_name
                    )
                    st.success("Expense saved successfully.")
                    st.rerun()

    elif menu == "My Expenses":
        st.subheader("My Expenses")
        df = get_user_expenses(st.session_state.user_email)

        if df.empty:
            st.info("No expenses submitted yet.")
        else:
            st.metric("My Total Expenses", f"${df['amount'].sum():,.2f}")
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download My Expenses CSV",
                data=csv,
                file_name="my_expenses.csv",
                mime="text/csv"
            )

    elif menu == "All Expenses" and st.session_state.user_role == "admin":
        st.subheader("All Expenses")
        df = 