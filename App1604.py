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

    exec_sql(
        "INSERT OR IGNORE INTO users (email, name, password, role) VALUES (?, ?, ?, ?)",
        ("radicafinace", "Radica Finance", hash_pw("radica!23"), "admin")
    )

    try:
        exec_sql(
            "UPDATE users SET approver_email = ?, user_amoeba = ? WHERE email = ?",
            ("", "", "radicafinace")
        )
    except:
        pass

    try:
        exec_sql(
            "UPDATE users SET name = ?, password = ? WHERE email = ?",
            ("Radica Finance", hash_pw("radica!23"), "radicafinace")
        )
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
    row = fetch_one(
        "SELECT approver_email, user_amoeba FROM users WHERE email = ?",
        (user_email,)
    )
    if row:
        approver_email = row[0] if row[0] else ""
        user_amoeba = row[1] if row[1] else ""
        return approver_email, user_amoeba
    return "", ""


def show_receipt(receipt_name, receipt_data, receipt_type, key_name):
    if receipt_data is None:
        st.info("No attachment uploaded.")
        return

    if str(receipt_type).startswith("image/"):
        st.image(receipt_data, caption=receipt_name, use_container_width=True)

    st.download_button(
        "Download Receipt",
        data=receipt_data,
        file_name=receipt_name if receipt_name else "receipt",
        mime=receipt_type if receipt_type else "application/octet-stream",
        key=key_name
    )


def logout():
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.user_role = ""


init_db()

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
        menu = st.sidebar.radio(
            "Navigation",
            ["Expense Form", "My Expenses", "All Expenses", "Approval Queue", "User Management", "Master Data"]
        )
    else:
        menu = st.sidebar.radio(
            "Navigation",
            ["Expense Form", "My Expenses", "Approval Queue"]
        )

    if st.sidebar.button("Logout"):
        logout()
        st.rerun()

    if menu == "Expense Form":
        st.subheader("Submit Expense")

        categories = get_names("categories")
        payment_methods = get_names("payment_methods")
        currencies = ["HKD", "CNY", "USD"]

        approver_email, user_amoeba = get_user_profile(st.session_state.user_email)

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
                    receipt_name = ""
                    receipt_data = None
                    receipt_type = ""

                    if receipt is not None:
                        receipt_name = receipt.name
                        receipt_data = receipt.getvalue()
                        receipt_type = receipt.type

                    exec_sql(
                        "INSERT INTO expenses (expense_date, user_email, amoeba, category, description, amount, currency, payment_method, receipt_name, receipt_data, receipt_type, status, assigned_approver, approver_comment, approved_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(expense_date),
                            st.session_state.user_email,
                            user_amoeba,
                            category,
                            description,
                            amount,
                            currency,
                            payment_method,
                            receipt_name,
                            receipt_data,
                            receipt_type,
                            "Submitted",
                            approver_email,
                            "",
                            ""
                        )
                    )
                    st.success("Expense submitted for approval.")
                    st.rerun()

    elif menu == "My Expenses":
        st.subheader("My Expenses")

        df = fetch_df(
            "SELECT id, expense_date, amoeba, category, description, amount, currency, payment_method, receipt_name, receipt_data, receipt_type, status, assigned_approver, approver_comment, approved_by FROM expenses WHERE user_email = ? ORDER BY id DESC",
            (st.session_state.user_email,)
        )

        if df.empty:
            st.info("No expenses submitted yet.")
        else:
            st.dataframe(df.drop(columns=["receipt_data"], errors="ignore"), use_container_width=True)

            st.markdown("### View Attachment")
            expense_ids = df["id"].tolist()
            selected_expense_id = st.selectbox("Select expense ID", expense_ids, key="my_expense_attachment")
            selected_row = df[df["id"] == selected_expense_id].iloc[0]

            st.write("Receipt: " + str(selected_row["receipt_name"]))
            show_receipt(
                selected_row["receipt_name"],
                selected_row["receipt_data"],
                selected_row["receipt_type"],
                "my_receipt_" + str(selected_expense_id)
            )

            csv_df = df.drop(columns=["receipt_data"], errors="ignore")
            st.download_button(
                "Download My Expenses CSV",
                csv_df.to_csv(index=False).encode("utf-8"),
                "my_expenses.csv",
                "text/csv"
            )

    elif menu == "All Expenses" and st.session_state.user_role == "admin":
        st.subheader("All Expenses")

        df = fetch_df(
            "SELECT id, expense_date, user_email, amoeba, category, description, amount, currency, payment_method, receipt_name, receipt_data, receipt_type, status, assigned_approver, approver_comment, approved_by FROM expenses ORDER BY id DESC"
        )

        if df.empty:
            st.info("No expense records found.")
        else:
            st.dataframe(df.drop(columns=["receipt_data"], errors="ignore"), use_container_width=True)

            st.markdown("### View Attachment")
            expense_ids = df["id"].tolist()
            selected_expense_id = st.selectbox("Select expense ID", expense_ids, key="all_expense_attachment")
            selected_row = df[df["id"] == selected_expense_id].iloc[0]

            st.write("Employee: " + str(selected_row["user_email"]))
            st.write("Receipt: " + str(selected_row["receipt_name"]))
            show_receipt(
                selected_row["receipt_name"],
                selected_row["receipt_data"],
                selected_row["receipt_type"],
                "all_receipt_" + str(selected_expense_id)
            )

            csv_df = df.drop(columns=["receipt_data"], errors="ignore")
            st.download_button(
                "Download All Expenses CSV",
                csv_df.to_csv(index=False).encode("utf-8"),
                "all_expenses.csv",
                "text/csv"
            )

    elif menu == "Approval Queue":
        st.subheader("Approval Queue")

        df = fetch_df(
            "SELECT id, expense_date, user_email, amoeba, category, description, amount, currency, payment_method, receipt_name, receipt_data, receipt_type, status FROM expenses WHERE status = ? AND assigned_approver = ? ORDER BY id DESC",
            ("Submitted", st.session_state.user_email)
        )

        if df.empty:
            st.info("No expenses waiting for your approval.")
        else:
            st.dataframe(df.drop(columns=["receipt_data"], errors="ignore"), use_container_width=True)

            option_map = {}
            for _, row in df.iterrows():
                label = "ID " + str(row["id"]) + " | " + str(row["user_email"]) + " | " + str(row["currency"]) + " " + f'{row["amount"]:.2f}' + " | " + str(row["category"])
                option_map[label] = row["id"]

            selected_label = st.selectbox("Select expense to review", list(option_map.keys()))
            selected_id = option_map[selected_label]
            selected = df[df["id"] == selected_id].iloc[0]

            st.markdown("### Selected Expense")
            st.write("Employee: " + str(selected["user_email"]))
            st.write("Date: " + str(selected["expense_date"]))
            st.write("Amoeba: " + str(selected["amoeba"]))
            st.write("Category: " + str(selected["category"]))
            st.write("Amount: " + str(selected["currency"]) + " " + f'{selected["amount"]:.2f}')
            st.write("Payment Method: " + str(selected["payment_method"]))
            st.write("Description: " + str(selected["description"]))
            st.write("Receipt: " + str(selected["receipt_name"]))

            show_receipt(
                selected["receipt_name"],
                selected["receipt_data"],
                selected["receipt_type"],
                "approval_receipt_" + str(selected_id)
            )

            comment = st.text_area("Approval Comment")
            col_a, col_b = st.columns(2)

            with col_a:
                if st.button("Approve Expense"):
                    exec_sql(
                        "UPDATE expenses SET status = ?, approver_comment = ?, approved_by = ? WHERE id = ?",
                        ("Approved", comment, st.session_state.user_email, selected_id)
                    )
                    st.success("Expense approved.")
                    st.rerun()

            with col_b:
                if st.button("Reject Expense"):
                    exec_sql(
                        "UPDATE expenses SET status = ?, approver_comment = ?, approved_by = ? WHERE id = ?",
                        ("Rejected", comment, st.session_state.user_email, selected_id)
                    )
                    st.warning("Expense rejected.")
                    st.rerun()

    elif menu == "User Management" and st.session_state.user_role == "admin":
        st.subheader("User Management")

        users_df = fetch_df(
            "SELECT id, email, name, role, approver_email, user_amoeba FROM users ORDER BY id"
        )
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
                    ok, msg = create_user(
                        new_email,
                        new_name,
                        new_password,
                        new_role,
                        new_approver,
                        new_amoeba
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown("### Update User Profile")
        non_admin_df = users_df[users_df["role"] != "admin"]

        if not non_admin_df.empty:
            user_options = {}
            for _, row in non_admin_df.iterrows():
                label = str(row["name"]) + " (" + str(row["email"]) + ")"
                user_options[label] = row["email"]

            selected_user_label = st.selectbox("Select user", list(user_options.keys()))
            selected_user_email = user_options[selected_user_label]

            current_row = non_admin_df[non_admin_df["email"] == selected_user_email].iloc[0]
            current_approver = current_row["approver_email"] if pd.notna(current_row["approver_email"]) else ""
            current_amoeba = current_row["user_amoeba"] if pd.notna(current_row["user_amoeba"]) else ""

            approver_index = all_user_emails.index(current_approver) if current_approver in all_user_emails else 0
            amoeba_index = amoeba_choices.index(current_amoeba) if current_amoeba in amoeba_choices else 0

            selected_approver = st.selectbox(
                "Select approver",
                all_user_emails,
                index=approver_index,
                key="approver_update"
            )

            selected_amoeba = st.selectbox(
                "Select Amoeba / Department",
                amoeba_choices,
                index=amoeba_index,
                key="amoeba_update"
            )

            if st.button("Update User Profile"):
                exec_sql(
                    "UPDATE users SET approver_email = ?, user_amoeba = ? WHERE email = ?",
                    (selected_approver, selected_amoeba, selected_user_email)
                )
                st.success("User profile updated.")
                st.rerun()

            st.markdown("### Delete User")
            if st.button("Delete Selected User"):
                exec_sql("DELETE FROM users WHERE email = ?", (selected_user_email,))
                st.success("User deleted.")
                st.rerun()

    elif menu == "Master Data" and st.session_state.user_role == "admin":
        st.subheader("Master Data Control Portal")

        tab1, tab2, tab3 = st.tabs(["Amoeba", "Expense Category", "Payment Method"])

        with tab1:
            amoeba_df = fetch_df("SELECT id, name FROM amoebas ORDER BY name")
            st.dataframe(amoeba_df, use_container_width=True)

            with st.form("add_amoeba_form"):
                new_amoeba = st.text_input("New Amoeba / Department")
                add_amoeba_btn = st.form_submit_button("Add Amoeba")

                if add_amoeba_btn:
                    if not new_amoeba.strip():
                        st.error("Please enter a value.")
                    else:
                        ok, msg = add_item("amoebas", new_amoeba.strip())
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            if not amoeba_df.empty:
                amoeba_map = {}
                for _, row in amoeba_df.iterrows():
                    amoeba_map[row["name"]] = row["id"]

                selected_amoeba = st.selectbox("Select Amoeba to delete", list(amoeba_map.keys()))
                if st.button("Delete Amoeba"):
                    exec_sql("DELETE FROM amoebas WHERE id = ?", (amoeba_map[selected_amoeba],))
                    st.success("Amoeba deleted.")
                    st.rerun()

        with tab2:
            category_df = fetch_df("SELECT id, name FROM categories ORDER BY name")
            st.dataframe(category_df, use_container_width=True)

            with st.form("add_category_form"):
                new_category = st.text_input("New Expense Category")
                add_category_btn = st.form_submit_button("Add Category")

                if add_category_btn:
                    if not new_category.strip():
                        st.error("Please enter a value.")
                    else:
                        ok, msg = add_item("categories", new_category.strip())
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            if not category_df.empty:
                category_map = {}
                for _, row in category_df.iterrows():
                    category_map[row["name"]] = row["id"]

                selected_category = st.selectbox("Select Category to delete", list(category_map.keys()))
                if st.button("Delete Category"):
                    exec_sql("DELETE FROM categories WHERE id = ?", (category_map[selected_category],))
                    st.success("Category deleted.")
                    st.rerun()

        with tab3:
            payment_df = fetch_df("SELECT id, name FROM payment_methods ORDER BY name")
            st.dataframe(payment_df, use_container_width=True)

            with st.form("add_payment_form"):
                new_payment = st.text_input("New Payment Method")
                add_payment_btn = st.form_submit_button("Add Payment Method")

                if add_payment_btn:
                    if not new_payment.strip():
                        st.error("Please enter a value.")
                    else:
                        ok, msg = add_item("payment_methods", new_payment.strip())
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            if not payment_df.empty:
                payment_map = {}
                for _, row in payment_df.iterrows():
                    payment_map[row["name"]] = row["id"]

                selected_payment = st.selectbox("Select Payment Method to delete", list(payment_map.keys()))
                if st.button("Delete Payment Method"):
                    exec_sql("DELETE FROM payment_methods WHERE id = ?", (payment_map[selected_payment],))
                    st.success("Payment method deleted.")
                    st.rerun()
