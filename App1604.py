import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from datetime import date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

def generate_approval_token(expense_id, expense_type, approver_email):
    """Generates a secure hash so approval links cannot be forged."""
    secret = st.secrets.get("APP_SECRET", "radica_super_secret_key_123")
    raw_string = f"{expense_id}_{expense_type}_{approver_email}_{secret}"
    return hashlib.sha256(raw_string.encode()).hexdigest()

def exec_sql(sql, params=()):
    """Executes SQL and returns the last inserted row ID (useful for new expenses)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id

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
    
    # Table for Vendor Expenses (3 vendors comparison)
    exec_sql("""CREATE TABLE IF NOT EXISTS vendor_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT, expense_date TEXT, user_email TEXT, amoeba TEXT, 
        category TEXT, description TEXT, currency TEXT, payment_method TEXT, 
        v1_name TEXT, v1_amount REAL, v1_file_name TEXT, v1_file_data BLOB, v1_file_type TEXT, 
        v2_name TEXT, v2_amount REAL, v2_file_name TEXT, v2_file_data BLOB, v2_file_type TEXT, 
        v3_name TEXT, v3_amount REAL, v3_file_name TEXT, v3_file_data BLOB, v3_file_type TEXT, 
        selected_vendor TEXT, gross_profit_pct REAL, status TEXT, assigned_approver TEXT, 
        approver_comment TEXT, approved_by TEXT)""")

    safe_add_column("users", "approver_email TEXT")
    safe_add_column("users", "user_amoeba TEXT")
    safe_add_column("expenses", "assigned_approver TEXT")
    safe_add_column("expenses", "approver_comment TEXT")
    safe_add_column("expenses", "approved_by TEXT")
    safe_add_column("expenses", "receipt_data BLOB")
    safe_add_column("expenses", "receipt_type TEXT")

    exec_sql(
        "INSERT OR IGNORE INTO users (email, name, password, role) VALUES (?, ?, ?, ?)",
        ("radicafinace", "Radica Finance", hash_pw("radica!23"), "admin")
    )

    try:
        exec_sql("UPDATE users SET approver_email = ?, user_amoeba = ? WHERE email = ?", ("", "", "radicafinace"))
        exec_sql("UPDATE users SET name = ?, password = ? WHERE email = ?", ("Radica Finance", hash_pw("radica!23"), "radicafinace"))
    except:
        pass

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
    row = fetch_one("SELECT approver_email, user_amoeba FROM users WHERE email = ?", (user_email,))
    if row:
        return row[0] if row[0] else "", row[1] if row[1] else ""
    return "", ""

def show_receipt(receipt_name, receipt_data, receipt_type, key_name):
    if receipt_data is None:
        st.info("No attachment available.")
        return
    if str(receipt_type).startswith("image/"):
        st.image(receipt_data, caption=receipt_name, use_container_width=True)
    st.download_button(
        "Download Document",
        data=receipt_data,
        file_name=receipt_name if receipt_name else "document",
        mime=receipt_type if receipt_type else "application/octet-stream",
        key=key_name
    )

def send_approval_email(to_email, submitter_name, amount, currency, expense_type, expense_id):
    """Sends an email notification to the approver with a 1-click approval link."""
    try:
        if not hasattr(st, "secrets") or "SENDER_EMAIL" not in st.secrets:
            st.warning("⚠️ Email skipped: 'SENDER_EMAIL' is missing from Streamlit secrets.")
            return

        smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = st.secrets.get("SMTP_PORT", 587)
        sender_email = st.secrets["SENDER_EMAIL"]
        sender_password = st.secrets["SENDER_PASSWORD"]
        
        app_url = st.secrets.get("APP_URL", "https://your-expense-app.streamlit.app").rstrip("/")
        ex_type_code = "std" if expense_type == "Standard" else "ven"
        token = generate_approval_token(expense_id, ex_type_code, to_email)
        
        approve_url = f"{app_url}/?action=approve&type={ex_type_code}&id={expense_id}&email={to_email}&token={token}"

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = f"Action Required: New {expense_type} Expense from {submitter_name}"

        body = f"""Hello,

A new {expense_type} expense has been submitted by {submitter_name} and is waiting for your approval.

Amount: {currency} {amount}

-------------------------------------------------
✅ ONE-CLICK APPROVE
Click the link below to instantly approve this expense (no login required):
{approve_url}
-------------------------------------------------

Or log in to the app to review attachments, vendor quotes, and details:
{app_url}

Thank you!
"""
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
    except smtplib.SMTPAuthenticationError:
        st.error("📧 Email failed: Authentication Error. Check your email and App Password in secrets.")
    except Exception as e:
        st.error(f"📧 Email failed to send: {e}")

def logout():
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.user_role = ""

# ==========================================
# Initialize DB
# ==========================================
init_db()

# ==========================================
# ONE-CLICK APPROVAL ROUTE CATCHER
# ==========================================
# If the URL contains ?action=approve, intercept it before rendering the app!
if "action" in st.query_params and st.query_params["action"] == "approve":
    ex_type = st.query_params.get("type", "")
    ex_id = st.query_params.get("id", "")
    appr_email = st.query_params.get("email", "")
    token = st.query_params.get("token", "")
    
    st.title("💸 Radica Amoeba Expense - One-Click Approval")
    
    expected_token = generate_approval_token(ex_id, ex_type, appr_email)
    
    if token == expected_token:
        table = "expenses" if ex_type == "std" else "vendor_expenses"
        row = fetch_one(f"SELECT status, assigned_approver FROM {table} WHERE id = ?", (ex_id,))
        
        if row:
            if row[0] == "Submitted" and row[1] == appr_email:
                exec_sql(f"UPDATE {table} SET status = 'Approved', approver_comment = 'Approved via Email 1-Click', approved_by = ? WHERE id = ?", (appr_email, ex_id))
                st.success(f"✅ Expense #{ex_id} has been successfully approved!")
                st.balloons()
            elif row[0] != "Submitted":
                st.info(f"This expense has already been processed (Current status: {row[0]}).")
            else:
                st.error("You are not the assigned approver for this expense.")
        else:
            st.error("Expense record not found in the database.")
    else:
        st.error("❌ Invalid or expired approval link. Please log in to the app to approve manually.")
        
    st.write("---")
    if st.button("Go to Login / Main App"):
        st.query_params.clear()
        st.rerun()
        
    st.stop() # Stops the rest of the script from loading so they don't see the login screen

# ==========================================
# MAIN APP RENDERING
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_role" not in st.session_state:
    st.session_state.user_role = ""

st.title("💸 Radica Amoeba Expense")

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login", "Create Account"])

    with tab1:
        st.subheader("Login")
        st.caption("Admin login: radicafinace / radica!23")

        with st.form("login_form"):
            email = st.text_input("Email / Login ID")
            password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Login")

            if login_btn:
                user = login_user(email, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_email = user[0]
                    st.session_state.user_name = user[1]
                    st.session_state.user_role = user[2]
                    st.success("Login successful.")
                    st.rerun()
                else:
                    st.error("Incorrect login ID or password.")

    with tab2:
        st.subheader("Create Account")

        with st.form("signup_form"):
            name = st.text_input("Full Name")
            email = st.text_input("Email / Login ID", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            confirm_password = st.text_input("Confirm Password", type="password")
            signup_btn = st.form_submit_button("Create Account")

            if signup_btn:
                if not name or not email or not password:
                    st.error("Please fill in all fields.")
                elif password != confirm_password:
                    st.error("Passwords do not match.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    ok, msg = create_user(email, name, password)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

else:
    st.sidebar.success("Logged in as " + st.session_state.user_name)
    st.sidebar.write("Role: " + st.session_state.user_role)

    if st.session_state.user_role == "admin":
        menu = st.sidebar.radio("Navigation", ["Expense Form", "My Expenses", "All Expenses", "Approval Queue", "User Management", "Master Data"])
    else:
        menu = st.sidebar.radio("Navigation", ["Expense Form", "My Expenses", "Approval Queue"])

    if st.sidebar.button("Logout"):
        logout()
        st.rerun()

    categories = get_names("categories")
    payment_methods = get_names("payment_methods")
    currencies = ["HKD", "CNY", "USD"]
    approver_email, user_amoeba = get_user_profile(st.session_state.user_email)

    if menu == "Expense Form":
        tab_reg, tab_ven = st.tabs(["Standard Expense", "Vendor Expense (3 Quotes)"])

        with tab_reg:
            st.subheader("Submit Standard Expense")
            with st.form("expense_form"):
                col1, col2 = st.columns(2)
                with col1:
                    expense_date = st.date_input("Expense Date", value=date.today())
                    category = st.selectbox("Expense Category", categories)
                    currency = st.selectbox("Currency", currencies)

                with col2:
                    amount = st.number_input("Amount", min_value=0.0, step=1.0, format="%.2f")
                    payment_method = st.selectbox("Payment Method", payment_methods)
                    receipt = st.file_uploader("Upload Receipt (optional)", type=["pdf", "png", "jpg", "jpeg"])

                st.text_input("Amoeba / Department", value=user_amoeba, disabled=True)
                description = st.text_area("Description")
                save_btn = st.form_submit_button("Save Expense")

                if save_btn:
                    if amount <= 0:
                        st.error("Amount must be greater than 0.")
                    elif approver_email == "":
                        st.error("No approver is assigned to your account. Please contact admin.")
                    elif user_amoeba == "":
                        st.error("No Amoeba / Department is assigned to your account. Please contact admin.")
                    else:
                        receipt_name, receipt_data, receipt_type = "", None, ""
                        if receipt is not None:
                            receipt_name = receipt.name
                            receipt_data = receipt.getvalue()
                            receipt_type = receipt.type

                        new_id = exec_sql(
                            "INSERT INTO expenses (expense_date, user_email, amoeba, category, description, amount, currency, payment_method, receipt_name, receipt_data, receipt_type, status, assigned_approver, approver_comment, approved_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (str(expense_date), st.session_state.user_email, user_amoeba, category, description, amount, currency, payment_method, receipt_name, receipt_data, receipt_type, "Submitted", approver_email, "", "")
                        )
                        
                        send_approval_email(approver_email, st.session_state.user_name, amount, currency, "Standard", new_id)
                        st.success("Expense submitted for approval.")
                        st.rerun()

        with tab_ven:
            st.subheader("Submit Vendor Expense")
            with st.form("vendor_expense_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    expense_date_v = st.date_input("Date", value=date.today(), key="v_date")
                    category_v = st.selectbox("Category", categories, key="v_cat")
                with col2:
                    currency_v = st.selectbox("Currency", currencies, key="v_curr")
                    payment_method_v = st.selectbox("Payment Method", payment_methods, key="v_pay")
                with col3:
                    gp_pct = st.number_input("Gross Profit %", min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
                    selected_vendor = st.selectbox("Select Winning Vendor", ["Vendor 1", "Vendor 2", "Vendor 3"])

                st.text_input("Amoeba / Department", value=user_amoeba, disabled=True, key="v_amoeba")
                description_v = st.text_area("Description / Business Justification", key="v_desc")

                st.markdown("### 3 Vendors Comparison")
                v1_col, v2_col, v3_col = st.columns(3)
                
                with v1_col:
                    st.markdown("**Vendor 1**")
                    v1_name = st.text_input("Vendor 1 Name", key="v1_name")
                    v1_amount = st.number_input("Vendor 1 Amount", min_value=0.0, step=1.0, format="%.2f", key="v1_amount")
                    v1_file = st.file_uploader("Quotation 1 (Required)", type=["pdf", "png", "jpg", "jpeg"], key="v1_file")

                with v2_col:
                    st.markdown("**Vendor 2**")
                    v2_name = st.text_input("Vendor 2 Name", key="v2_name")
                    v2_amount = st.number_input("Vendor 2 Amount", min_value=0.0, step=1.0, format="%.2f", key="v2_amount")
                    v2_file = st.file_uploader("Quotation 2 (Required)", type=["pdf", "png", "jpg", "jpeg"], key="v2_file")

                with v3_col:
                    st.markdown("**Vendor 3**")
                    v3_name = st.text_input("Vendor 3 Name", key="v3_name")
                    v3_amount = st.number_input("Vendor 3 Amount", min_value=0.0, step=1.0, format="%.2f", key="v3_amount")
                    v3_file = st.file_uploader("Quotation 3 (Required)", type=["pdf", "png", "jpg", "jpeg"], key="v3_file")

                save_ven_btn = st.form_submit_button("Save Vendor Expense")

                if save_ven_btn:
                    if approver_email == "" or user_amoeba == "":
                        st.error("No approver or Amoeba assigned. Please contact admin.")
                    elif v1_amount <= 0 or v2_amount <= 0 or v3_amount <= 0:
                        st.error("All 3 vendor amounts must be greater than 0.")
                    elif not v1_name.strip() or not v2_name.strip() or not v3_name.strip():
                        st.error("Please provide names for all 3 vendors.")
                    elif not v1_file or not v2_file or not v3_file:
                        st.error("Please upload supporting quotations for all 3 vendors.")
                    else:
                        new_v_id = exec_sql("""
                            INSERT INTO vendor_expenses (
                                expense_date, user_email, amoeba, category, description, currency, payment_method, 
                                v1_name, v1_amount, v1_file_name, v1_file_data, v1_file_type,
                                v2_name, v2_amount, v2_file_name, v2_file_data, v2_file_type,
                                v3_name, v3_amount, v3_file_name, v3_file_data, v3_file_type,
                                selected_vendor, gross_profit_pct, status, assigned_approver, approver_comment, approved_by
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            str(expense_date_v), st.session_state.user_email, user_amoeba, category_v, description_v, currency_v, payment_method_v,
                            v1_name, v1_amount, v1_file.name, v1_file.getvalue(), v1_file.type,
                            v2_name, v2_amount, v2_file.name, v2_file.getvalue(), v2_file.type,
                            v3_name, v3_amount, v3_file.name, v3_file.getvalue(), v3_file.type,
                            selected_vendor, gp_pct, "Submitted", approver_email, "", ""
                        ))
                        
                        display_amount = v1_amount if selected_vendor == "Vendor 1" else (v2_amount if selected_vendor == "Vendor 2" else v3_amount)
                        send_approval_email(approver_email, st.session_state.user_name, display_amount, currency_v, "Vendor", new_v_id)
                        
                        st.success("Vendor expense submitted for approval.")
                        st.rerun()

    elif menu == "My Expenses":
        st.subheader("My Expenses")
        tab_reg, tab_ven = st.tabs(["Standard Expenses", "Vendor Expenses"])

        with tab_reg:
            df = fetch_df("SELECT id, expense_date, amoeba, category, description, amount, currency, payment_method, receipt_name, receipt_data, receipt_type, status, assigned_approver, approver_comment, approved_by FROM expenses WHERE user_email = ? ORDER BY id DESC", (st.session_state.user_email,))
            if df.empty:
                st.info("No standard expenses submitted yet.")
            else:
                st.dataframe(df.drop(columns=["receipt_data"], errors="ignore"), use_container_width=True)
                st.markdown("### View Attachment")
                selected_expense_id = st.selectbox("Select standard expense ID", df["id"].tolist(), key="my_ex_id")
                selected_row = df[df["id"] == selected_expense_id].iloc[0]
                show_receipt(selected_row["receipt_name"], selected_row["receipt_data"], selected_row["receipt_type"], "my_rec_" + str(selected_expense_id))
                st.download_button("Download CSV", df.drop(columns=["receipt_data"]).to_csv(index=False).encode("utf-8"), "my_expenses.csv", "text/csv")

        with tab_ven:
            df_v = fetch_df("SELECT id, expense_date, category, description, currency, payment_method, v1_name, v1_amount, v2_name, v2_amount, v3_name, v3_amount, selected_vendor, gross_profit_pct, status, assigned_approver, approver_comment, v1_file_name, v1_file_data, v1_file_type, v2_file_name, v2_file_data, v2_file_type, v3_file_name, v3_file_data, v3_file_type FROM vendor_expenses WHERE user_email = ? ORDER BY id DESC", (st.session_state.user_email,))
            if df_v.empty:
                st.info("No vendor expenses submitted yet.")
            else:
                cols_to_drop = ["v1_file_data", "v2_file_data", "v3_file_data"]
                st.dataframe(df_v.drop(columns=cols_to_drop, errors="ignore"), use_container_width=True)
                st.markdown("### View Quotations")
                v_id = st.selectbox("Select vendor expense ID", df_v["id"].tolist(), key="my_ven_id")
                v_row = df_v[df_v["id"] == v_id].iloc[0]
                
                quote_sel = st.radio("Select Quotation to View", ["Vendor 1", "Vendor 2", "Vendor 3"], horizontal=True, key="my_ven_radio")
                if quote_sel == "Vendor 1":
                    show_receipt(v_row["v1_file_name"], v_row["v1_file_data"], v_row["v1_file_type"], f"v1_{v_id}")
                elif quote_sel == "Vendor 2":
                    show_receipt(v_row["v2_file_name"], v_row["v2_file_data"], v_row["v2_file_type"], f"v2_{v_id}")
                else:
                    show_receipt(v_row["v3_file_name"], v_row["v3_file_data"], v_row["v3_file_type"], f"v3_{v_id}")

    elif menu == "All Expenses" and st.session_state.user_role == "admin":
        st.subheader("All Expenses")
        tab_reg, tab_ven = st.tabs(["Standard Expenses", "Vendor Expenses"])

        with tab_reg:
            df = fetch_df("SELECT id, expense_date, user_email, amoeba, category, description, amount, currency, payment_method, receipt_name, receipt_data, receipt_type, status, assigned_approver, approver_comment, approved_by FROM expenses ORDER BY id DESC")
            if df.empty:
                st.info("No standard expenses found.")
            else:
                st.dataframe(df.drop(columns=["receipt_data"], errors="ignore"), use_container_width=True)
                st.markdown("### View Attachment")
                ex_id = st.selectbox("Select standard expense ID", df["id"].tolist(), key="all_ex_id")
                row = df[df["id"] == ex_id].iloc[0]
                show_receipt(row["receipt_name"], row["receipt_data"], row["receipt_type"], "all_rec_" + str(ex_id))
                st.download_button("Download CSV", df.drop(columns=["receipt_data"]).to_csv(index=False).encode("utf-8"), "all_expenses.csv", "text/csv")

        with tab_ven:
            df_v = fetch_df("SELECT id, expense_date, user_email, amoeba, category, description, currency, payment_method, v1_name, v1_amount, v2_name, v2_amount, v3_name, v3_amount, selected_vendor, gross_profit_pct, status, assigned_approver, approver_comment, v1_file_name, v1_file_data, v1_file_type, v2_file_name, v2_file_data, v2_file_type, v3_file_name, v3_file_data, v3_file_type FROM vendor_expenses ORDER BY id DESC")
            if df_v.empty:
                st.info("No vendor expenses found.")
            else:
                cols_to_drop = ["v1_file_data", "v2_file_data", "v3_file_data"]
                st.dataframe(df_v.drop(columns=cols_to_drop, errors="ignore"), use_container_width=True)
                st.markdown("### View Quotations")
                v_id = st.selectbox("Select vendor expense ID", df_v["id"].tolist(), key="all_ven_id")
                v_row = df_v[df_v["id"] == v_id].iloc[0]
                
                quote_sel = st.radio("Select Quotation to View", ["Vendor 1", "Vendor 2", "Vendor 3"], horizontal=True, key="all_ven_radio")
                if quote_sel == "Vendor 1":
                    show_receipt(v_row["v1_file_name"], v_row["v1_file_data"], v_row["v1_file_type"], f"v1_all_{v_id}")
                elif quote_sel == "Vendor 2":
                    show_receipt(v_row["v2_file_name"], v_row["v2_file_data"], v_row["v2_file_type"], f"v2_all_{v_id}")
                else:
                    show_receipt(v_row["v3_file_name"], v_row["v3_file_data"], v_row["v3_file_type"], f"v3_all_{v_id}")

    elif menu == "Approval Queue":
        st.subheader("Approval Queue")
        tab_reg, tab_ven = st.tabs(["Standard Expenses", "Vendor Expenses"])

        with tab_reg:
            df = fetch_df("SELECT id, expense_date, user_email, amoeba, category, description, amount, currency, payment_method, receipt_name, receipt_data, receipt_type, status FROM expenses WHERE status = ? AND assigned_approver = ? ORDER BY id DESC", ("Submitted", st.session_state.user_email))
            if df.empty:
                st.info("No standard expenses waiting for your approval.")
            else:
                st.dataframe(df.drop(columns=["receipt_data"], errors="ignore"), use_container_width=True)
                option_map = {f'ID {r["id"]} | {r["user_email"]} | {r["currency"]} {r["amount"]:.2f}': r["id"] for _, r in df.iterrows()}
                selected_label = st.selectbox("Select standard expense to review", list(option_map.keys()), key="app_ex_sel")
                selected_id = option_map[selected_label]
                selected = df[df["id"] == selected_id].iloc[0]

                show_receipt(selected["receipt_name"], selected["receipt_data"], selected["receipt_type"], f"app_rec_{selected_id}")
                comment = st.text_area("Approval Comment", key="app_ex_com")
                c1, c2 = st.columns(2)
                if c1.button("Approve Expense", key="app_ex_y"):
                    exec_sql("UPDATE expenses SET status=?, approver_comment=?, approved_by=? WHERE id=?", ("Approved", comment, st.session_state.user_email, selected_id))
                    st.success("Approved."); st.rerun()
                if c2.button("Reject Expense", key="app_ex_n"):
                    exec_sql("UPDATE expenses SET status=?, approver_comment=?, approved_by=? WHERE id=?", ("Rejected", comment, st.session_state.user_email, selected_id))
                    st.warning("Rejected."); st.rerun()

        with tab_ven:
            df_v = fetch_df("SELECT * FROM vendor_expenses WHERE status = ? AND assigned_approver = ? ORDER BY id DESC", ("Submitted", st.session_state.user_email))
            if df_v.empty:
                st.info("No vendor expenses waiting for your approval.")
            else:
                cols_to_drop = ["v1_file_data", "v2_file_data", "v3_file_data"]
                st.dataframe(df_v.drop(columns=cols_to_drop, errors="ignore"), use_container_width=True)
                
                v_opt_map = {f'ID {r["id"]} | {r["user_email"]} | {r["category"]} | GP: {r["gross_profit_pct"]}%': r["id"] for _, r in df_v.iterrows()}
                v_label = st.selectbox("Select vendor expense to review", list(v_opt_map.keys()), key="app_ven_sel")
                v_id = v_opt_map[v_label]
                v_row = df_v[df_v["id"] == v_id].iloc[0]

                st.write(f"**Selected Vendor:** {v_row['selected_vendor']}")
                st.write(f"**GP %:** {v_row['gross_profit_pct']}%")

                q_sel = st.radio("Review Quotations", ["Vendor 1", "Vendor 2", "Vendor 3"], horizontal=True, key="app_ven_radio")
                if q_sel == "Vendor 1":
                    st.write(f"Name: {v_row['v1_name']} | Amount: {v_row['v1_amount']}")
                    show_receipt(v_row["v1_file_name"], v_row["v1_file_data"], v_row["v1_file_type"], f"app_v1_{v_id}")
                elif q_sel == "Vendor 2":
                    st.write(f"Name: {v_row['v2_name']} | Amount: {v_row['v2_amount']}")
                    show_receipt(v_row["v2_file_name"], v_row["v2_file_data"], v_row["v2_file_type"], f"app_v2_{v_id}")
                else:
                    st.write(f"Name: {v_row['v3_name']} | Amount: {v_row['v3_amount']}")
                    show_receipt(v_row["v3_file_name"], v_row["v3_file_data"], v_row["v3_file_type"], f"app_v3_{v_id}")

                v_comment = st.text_area("Approval Comment", key="app_ven_com")
                c1, c2 = st.columns(2)
                if c1.button("Approve Vendor Expense", key="app_ven_y"):
                    exec_sql("UPDATE vendor_expenses SET status=?, approver_comment=?, approved_by=? WHERE id=?", ("Approved", v_comment, st.session_state.user_email, v_id))
                    st.success("Approved."); st.rerun()
                if c2.button("Reject Vendor Expense", key="app_ven_n"):
                    exec_sql("UPDATE vendor_expenses SET status=?, approver_comment=?, approved_by=? WHERE id=?", ("Rejected", v_comment, st.session_state.user_email, v_id))
                    st.warning("Rejected."); st.rerun()

    elif menu == "User Management" and st.session_state.user_role == "admin":
        st.subheader("User Management")

        users_df = fetch_df("SELECT id, email, name, role, approver_email, user_amoeba FROM users ORDER BY id")
        st.dataframe(users_df, use_container_width=True)

        all_user_emails = [""] + users_df["email"].tolist()
        amoeba_choices = [""] + get_names("amoebas")

        with st.form("add_user_form"):
            st.markdown("### Add New User")
            new_name = st.text_input("User Name")
            new_email = st.text_input("User Email")
            new_password = st.text_input("Temporary Password", type="password")
            new_role = st.selectbox("Role", ["user", "admin"])
            new_approver = st.selectbox("Assigned Approver", all_user_emails)
            new_amoeba = st.selectbox("Amoeba / Department", amoeba_choices)
            add_user_btn = st.form_submit_button("Add User")

            if add_user_btn:
                if not new_name or not new_email or not new_password:
                    st.error("Please fill in all fields.")
                else:
                    ok, msg = create_user(new_email, new_name, new_password, new_role, new_approver, new_amoeba)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown("### Update User Profile")
        non_admin_df = users_df[users_df["role"] != "admin"]

        if non_admin_df.empty:
            st.info("No non-admin users found. Please add a user above to update their profile.")
        else:
            user_options = {f'{r["name"]} ({r["email"]})': r["email"] for _, r in non_admin_df.iterrows()}
            selected_user_label = st.selectbox("Select user", list(user_options.keys()), key="selected_user_label")
            selected_user_email = user_options[selected_user_label]

            current_row = non_admin_df[non_admin_df["email"] == selected_user_email].iloc[0]
            current_approver = current_row["approver_email"] if pd.notna(current_row["approver_email"]) else ""
            current_amoeba = current_row["user_amoeba"] if pd.notna(current_row["user_amoeba"]) else ""

            app_idx = all_user_emails.index(current_approver) if current_approver in all_user_emails else 0
            am_idx = amoeba_choices.index(current_amoeba) if current_amoeba in amoeba_choices else 0

            selected_approver = st.selectbox("Select approver", all_user_emails, index=app_idx, key="app_upd")
            selected_amoeba = st.selectbox("Select Amoeba / Department", amoeba_choices, index=am_idx, key="am_upd")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Update User Profile"):
                    exec_sql("UPDATE users SET approver_email = ?, user_amoeba = ? WHERE email = ?", (selected_approver, selected_amoeba, selected_user_email))
                    st.success("User profile updated."); st.rerun()
            with col2:
                if st.button("Delete Selected User"):
                    exec_sql("DELETE FROM users WHERE email = ?", (selected_user_email,))
                    st.success("User deleted."); st.rerun()

    elif menu == "Master Data" and st.session_state.user_role == "admin":
        st.subheader("Master Data Control Portal")
        tab1, tab2, tab3 = st.tabs(["Amoeba", "Expense Category", "Payment Method"])

        with tab1:
            amoeba_df = fetch_df("SELECT id, name FROM amoebas ORDER BY name")
            st.dataframe(amoeba_df, use_container_width=True)
            with st.form("add_amoeba_form"):
                new_amoeba = st.text_input("New Amoeba / Department")
                if st.form_submit_button("Add Amoeba"):
                    if not new_amoeba.strip(): st.error("Please enter a value.")
                    else: 
                        ok, msg = add_item("amoebas", new_amoeba.strip())
                        st.success(msg) if ok else st.error(msg)
                        if ok: st.rerun()
            if not amoeba_df.empty:
                amoeba_map = {r["name"]: r["id"] for _, r in amoeba_df.iterrows()}
                sel_am = st.selectbox("Select Amoeba to delete", list(amoeba_map.keys()))
                if st.button("Delete Amoeba"):
                    exec_sql("DELETE FROM amoebas WHERE id = ?", (amoeba_map[sel_am],))
                    st.success("Amoeba deleted."); st.rerun()

        with tab2:
            category_df = fetch_df("SELECT id, name FROM categories ORDER BY name")
            st.dataframe(category_df, use_container_width=True)
            with st.form("add_category_form"):
                new_category = st.text_input("New Expense Category")
                if st.form_submit_button("Add Category"):
                    if not new_category.strip(): st.error("Please enter a value.")
                    else:
                        ok, msg = add_item("categories", new_category.strip())
                        st.success(msg) if ok else st.error(msg)
                        if ok: st.rerun()
            if not category_df.empty:
                category_map = {r["name"]: r["id"] for _, r in category_df.iterrows()}
                sel_cat = st.selectbox("Select Category to delete", list(category_map.keys()))
                if st.button("Delete Category"):
                    exec_sql("DELETE FROM categories WHERE id = ?", (category_map[sel_cat],))
                    st.success("Category deleted."); st.rerun()

        with tab3:
            payment_df = fetch_df("SELECT id, name FROM payment_methods ORDER BY name")
            st.dataframe(payment_df, use_container_width=True)
            with st.form("add_payment_form"):
                new_payment = st.text_input("New Payment Method")
                if st.form_submit_button("Add Payment Method"):
                    if not new_payment.strip(): st.error("Please enter a value.")
                    else:
                        ok, msg = add_item("payment_methods", new_payment.strip())
                        st.success(msg) if ok else st.error(msg)
                        if ok: st.rerun()
            if not payment_df.empty:
                payment_map = {r["name"]: r["id"] for _, r in payment_df.iterrows()}
                sel_pay = st.selectbox("Select Payment Method to delete", list(payment_map.keys()))
                if st.button("Delete Payment Method"):
                    exec_sql("DELETE FROM payment_methods WHERE id = ?", (payment_map[sel_pay],))
                    st.success("Payment method deleted."); st.rerun()
