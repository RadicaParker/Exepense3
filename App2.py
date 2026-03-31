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


def run_sql(sql, params=None, fetch=False):
    conn = get_conn()
    cur = conn.cursor()
    if params:
        cur.execute(sql, params)
    else:
        cur.execute(sql)
    rows = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return rows


def get_df(sql, params=None):
    conn = get_conn()
    if params:
        df = pd.read_sql_query(sql, conn, params=params)
    else:
        df = pd.read_sql_query(sql, conn)
    conn.close()
    return df


def create_table_users():
    run_sql("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            name TEXT,
            password TEXT,
            role TEXT
        )
    """)


def create_table_expenses():
    run_sql("""
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


def create_table_amoebas():
    run_sql("""
        CREATE TABLE IF NOT EXISTS amoebas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)


def create_table_categories():
    run_sql("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)


def create_table_payment_methods():
    run_sql("""
        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)


def ensure_default_admin():
    rows = run_sql("SELECT COUNT(*) FROM users WHERE role = 'admin'", fetch=True)
    if rows[0][0] == 0:
        run_sql(
            "INSERT INTO users (email, name, password, role) VALUES (?, ?, ?, ?)",
            ("admin@taxhacker.com", "Admin", hash_password("Admin123!"), "admin")
        )


def ensure_default_master_data():
    if run_sql("SELECT COUNT(*) FROM amoebas", fetch=True)[0][0] == 0:
        run_sql("INSERT INTO amoebas (name) VALUES (?)", ("Marketing",))
        run_sql("INSERT INTO amoebas (name) VALUES (?)", ("Sales",))
        run_sql("INSERT INTO amoebas (name) VALUES (?)", ("Finance",))
        run_sql("INSERT INTO amoebas (name) VALUES (?)", ("Operations",))
        run_sql("INSERT INTO amoebas (name) VALUES (?)", ("Product",))

    if run_sql("SELECT COUNT(*) FROM categories", fetch=True)[0][0] == 0:
        run_sql("INSERT INTO categories (name) VALUES (?)", ("Travel",))
        run_sql("INSERT INTO categories (name) VALUES (?)", ("Meal",))
        run_sql("INSERT INTO categories (name) VALUES (?)", ("Software",))
        run_sql("INSERT INTO categories (name) VALUES (?)", ("Office Supplies",))
        run_sql("INSERT INTO categories (name) VALUES (?)", ("Other",))

    if run_sql("SELECT COUNT(*) FROM payment_methods", fetch=True)[0][0] == 0:
        run_sql("INSERT INTO payment_methods (name) VALUES (?)", ("Corporate Card",))
        run_sql("INSERT INTO payment_methods (name) VALUES (?)", ("Cash",))
        run_sql("INSERT INTO payment_methods (name) VALUES 