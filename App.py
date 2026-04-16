import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from datetime import date

DB_FILE = "expense_app.db"

st.set_page_config(
    page_title="Radica Amoeba Expense",
    page_icon="💸",
    layout="wide"
)


def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()


def exec_sql(sql, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    conn.close()


def fetch_one(sql, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    conn.close()
    return row


def fetch_df(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def safe_add_column(table_name, column_def):
    try:
        exec_sql("ALTER TABLE " + table_name + " ADD COLUMN " + column_def)
    except:
        pass


def init_db():
    exec_sql("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, name TEXT, password TEXT, role TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, expense_date TEXT, user_email TEXT, amoeba TEXT, category TEXT, description TEXT, amount REAL, currency TEXT, payment_method TEXT, receipt_name TEXT, status TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS amoebas (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")
    exec_sql("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")
    exec_sql("CREATE TABLE IF NOT EXISTS payment_methods (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")

    safe_add_column("users", "approver_email TEXT")
    safe_add_column("users", "user_amoeba TEXT")
    safe_add_column("expenses", "assigned_approver TEXT")
    safe_add_column("expenses", "approver_comment TEXT")
    safe_add_column("expenses", "approved_by TEXT")
    safe_add_column("expenses", "receipt_data BLOB")
    safe_add_column("expenses", "receipt_type TEXT")

    admin_count = fetch_one("SELECT COUNT(*) FROM users WHERE role = 'admin'")[0]

    if admin_count == 0:
        exec_sql(
            "INSERT INTO users (email, name, password, role, approver_email, user_amoeba) VALUES (?, ?, ?, ?, ?, ?)",
            ("radicafinace", "Radica Finance", hash_pw("radica!23"), "admin", "", "")
        )

    exec_sql(
        "UPDATE users SET email = ?, name = ?, password = ? WHERE role = ?",
        ("radicafinace", "Radica Finance", hash_pw("radica!23"), "admin")
    )

    if fetch_one("SELECT COUNT(*) FROM amoebas")[0] == 0:
        for item in ["Marketing", "Sales", "Finance", "Operations", "Product"]:
            exec_sql("INSERT INTO amoebas (name) VALUES (?)", (item,))

    if fetch_one("SELECT COUNT(*) FROM categories")[0] == 0:
        for item in ["Travel", "Meal", "Software", "Office Supplies", "Other"]:
            exec_sql("INSERT INTO categories (name) VALUES (?)", (item,))

    if fetch_one("SELECT COUNT(*) FROM payment_methods")[0] == 0:
        for item in ["Corporate Card", "Cash", "Personal Card", "Bank Transfer"]:
            exec_sql("INSERT INTO payment_methods (name) VALUES (?)", (item,))


def create_user(email, name, password, role="user", approver_email="", user_amoeba=""):
    try:
        exec_sql(
            "INSERT INTO users (email, name, password, role, approver_email, user_amoeba) VALUES (?, ?, ?, ?, ?, ?)",
            (email, name, hash_pw(password), role, approver_email, user_amoeba)
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
    df = fetch_df("SELECT name FROM " + table_name + " ORDER BY name")
    if df.empty:
        return []
    return df["name"].tolist()


def add_item(table_name, name):
    try:
        exec_sql("INSERT INTO " + table_name + " (name) VALUES (?)", (name,))
        return True, "Added successfully."
    except sqlite3.IntegrityError:
        return False, "This item already exists."


def get_user_profile(user_email):
    row = fetch_one(
        "SELECT approver_email, user_amoeba FROM users WHERE email = ?",
        (user_email,)
    )
    if row:
        approver_email 
