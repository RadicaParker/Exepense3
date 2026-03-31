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
       Yes — the best next step is to add a simple admin control portal with three editable master lists: **Amoeba**, **Expense Category**, and **Payment Method**. Streamlit forms work well for this kind of admin setup, and SQLite is a practical way to store the master data so your select boxes can load options dynamically instead of being hardcoded [web:86][web:74][web:76].

## What changes

Right now your dropdowns are fixed in the code, so every time you want to change a department or category, you would need to edit Python manually. A better design is to store those values in database tables and let the admin add or delete them from a protected admin page, which is a common pattern for lightweight internal apps [web:77][web:78].

## Replace app.py

Please replace your current `app.py` with the version below. It keeps the login, expense form, and user management, and adds a new **Master Data** admin page where you can manage Amoeba, Expense Category, and Payment Method.

```python
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
            