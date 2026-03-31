import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from datetime import date

DB_FILE = "expense_app.db"

st.set_page_config(page_title="TaxHacker Expense Module", page_icon="💸", layout="wide")


def conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()


def exec_sql(sql, params=()):
    c = conn()
    cur = c.cursor()
    cur.execute(sql, params)
    c.commit()
    c.close()


def fetch_df(sql, params=()):
    c = conn()
    df = pd.read_sql_query(sql, c, params=params)
    c.close()
    return df


def fetch_one(sql, params=()):
    c = conn()
    cur = c.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    c.close()
    return row


def init_db():
    exec_sql("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, name TEXT, password TEXT, role TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, expense_date TEXT, user_email TEXT, amoeba TEXT, category TEXT, description TEXT, amount REAL, payment_method TEXT, receipt_name TEXT, status TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS amoebas (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")
    exec_sql("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")
    exec_sql("CREATE TABLE IF NOT EXISTS payment_methods (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")

    admin_count = fetch_one("SELECT COUNT(*) FROM users WHERE role = 'admin'")[0]
    if admin_count == 0:
        exec_sql(
            "INSERT INTO users (email, name, password, role) VALUES (?, ?, ?, ?)",
            ("admin@taxhacker.com", "Admin", hash_pw("Admin123!"), "admin")
        )

    amoeba_count = fetch_one("SELECT COUNT(*) FROM amoebas")[0]
    if amoeba_count == 0:
        exec_sql("INSERT INTO amoebas (name) VALUES (?)", ("Marketing",))
        exec_sql("INSERT INTO amoebas (name) VALUES (?)", ("Sales",))
        exec_sql("INSERT INTO amoebas (name) VALUES (?)", ("Finance",))
        exec_sql("INSERT INTO amoebas (name) VALUES (?)", ("Operations",))
        exec_sql("INSERT INTO amoebas (name) VALUES (?)", ("Product",))

    category_count = fetch_one("SELECT COUNT(*) FROM categories")[0]
    if category_count == 0:
        exec_sql("INSERT INTO categories (name) VALUES (?)", ("Travel",))
        exec_sql("INSERT INTO categories (name) VALUES (?)", ("Meal",))
        exec_sql("INSERT INTO categories (name) VALUES (?)", ("Software",))
        exec_sql("INSERT INTO categories (name) VALUES (?)", ("Office Supplies",))
        exec_sql("INSERT INTO categories (name) VALUES (?)", ("Other",))

    payment_count = fetch_one("SELECT COUNT(*) FROM payment_methods")[0]
    if payment_count == 0:
        exec_sql("INSERT INTO payment_methods (name) VALUES (?)", ("Corporate Card",))
        exec_sql("INSERT INTO payment_methods (name) VALUES (?)", ("Cash",))
        exec_sql("INSERT INTO payment_methods (name) VALUES (?)", ("Personal Card",))
        exec_sql("INSERT INTO payment_methods (name) VALUES (?)", ("Bank Transfer",))


def create_user(email, name, password, role="user"):
    try:
        exec_sql(
            "INSERT INTO users (email, name, password, role) VALUES (?, ?, ?, ?)",
            (email, name, hash_pw(password), role)
        )
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "This email is already registered."


def login_user(email, password):
    return fetch_one(
        "SELECT email, name, role FROM users WHERE email = ? AND password = ?",
        (email, hash_pw(password))
    )


def get_names(table_name):
    df = fetch_df(f"SELECT name FROM {table_name} ORDER BY name")
    if df.empty:
        return []
    return df["name"].tolist()


def add_item(table_name, name):
    try:
        exec_sql(f"INSERT INTO {table_name} (name) VALUES (?)", (name,))
        return True, "Added successfully."
    except sqlite3.IntegrityError:
        return False, "This item already exists."


def logout():
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.user_role = ""


init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
