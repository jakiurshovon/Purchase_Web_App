import streamlit as st
import os
import pandas as pd
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple
from io import BytesIO

# Data / exports
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Supabase
from supabase import create_client, Client

# Use Streamlit secrets for environment variables
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
SUPABASE_RESET_REDIRECT_URL = st.secrets.get("SUPABASE_RESET_REDIRECT_URL")

anon: Client = None
admin: Client = None

def init_supabase():
    global anon, admin
    if not (SUPABASE_URL and SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY):
        st.error("Missing SUPABASE_URL/SUPABASE_ANON_KEY/SUPABASE_SERVICE_ROLE_KEY in Streamlit secrets.")
        st.stop()
    try:
        anon = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    except Exception as e:
        st.error(f"Error initializing Supabase: {e}")
        st.stop()
    st.session_state.supabase_initialized = True

def client_sign_in(email: str, password: str) -> Tuple[str, str]:
    try:
        res = anon.auth.sign_in_with_password({"email": email, "password": password})
        token = getattr(res.session, "access_token", None) if getattr(res, "session", None) else None
        uid = getattr(res.user, "id", None) if getattr(res, "user", None) else None
        if token is None:
            token = (res.get("access_token") if isinstance(res, dict) else None) or (res["session"]["access_token"] if isinstance(res, dict) and res.get("session") else None)
        if uid is None:
            uid = (res.get("user", {}).get("id") if isinstance(res, dict) else None)
        if not token or not uid:
            raise Exception("Invalid login response from Supabase")
        return token, uid
    except Exception as e:
        msg = str(e)
        if "Invalid login credentials" in msg or "Invalid login" in msg or "INVALID_PASSWORD" in msg:
            raise ValueError("Invalid email or password.")
        if "Email not confirmed" in msg:
            raise ValueError("Email is not confirmed yet.")
        raise

def get_user_profile(uid: str) -> Optional[Dict[str, Any]]:
    res = anon.table("profiles").select("*").eq("uid", uid).limit(1).execute()
    data = res.data or []
    if not data:
        return None
    prof = data[0]
    prof["uid"] = prof.get("uid") or uid
    roles = prof.get("roles") or []
    if isinstance(roles, str):
        roles = [r.strip() for r in roles.split(",") if r.strip()]
    prof["roles"] = roles or ["user"]
    return prof

def get_user_by_short_id(short_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    res = anon.table("profiles").select("*").eq("short_id", str(short_id)).limit(1).execute()
    data = res.data or []
    if not data:
        return None, None
    prof = data[0]
    return prof.get("uid"), prof

def admin_create_user(email: str, password: str, display_name: str, roles=None, short_id: Optional[str]=None) -> str:
    roles = roles or ["user"]
    u = admin.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"name": display_name}
    })
    uid = getattr(u.user, "id", None) or (u.get("user", {}).get("id") if isinstance(u, dict) else None)
    if not uid:
        raise RuntimeError("Failed to create auth user")
    admin.table("profiles").upsert({
        "uid": uid,
        "email": email,
        "name": display_name,
        "roles": roles,
        "short_id": str(short_id) if short_id else None,
        "created_at": datetime.now().isoformat()
    }).execute()
    return uid

def admin_update_user_profile(uid: str, name: Optional[str]=None, roles: Optional[List[str]]=None, short_id: Optional[str]=None):
    updates = {}
    if name is not None:
        updates["name"] = name
        try:
            admin.auth.admin.update_user_by_id(uid, {"user_metadata": {"name": name}})
        except Exception:
            try:
                admin.auth.admin.update_user(uid, {"user_metadata": {"name": name}})
            except Exception:
                pass
    if roles is not None:
        updates["roles"] = roles
    if short_id is not None:
        updates["short_id"] = short_id
    if updates:
        admin.table("profiles").update(updates).eq("uid", uid).execute()

def list_profiles() -> List[Dict[str, Any]]:
    res = admin.table("profiles").select("*").order("created_at", desc=False).execute()
    return res.data or []

def fetch_countries() -> List[Dict[str, Any]]:
    res = anon.table("countries").select("*").order("name").execute()
    return res.data or []

def add_country(name: str) -> str:
    res = admin.table("countries").insert({"name": name}).execute()
    if not (res.data):
        raise RuntimeError("Failed to insert country")
    row = res.data[0]
    return row.get('id') or row.get('name')

def update_country(country_id: str, new_name: str) -> None:
    admin.table("countries").update({"name": new_name}).eq("id", country_id).execute()

def delete_country(country_id: str) -> None:
    admin.table("countries").delete().eq("id", country_id).execute()

def fetch_regions() -> List[Dict[str, Any]]:
    res = anon.table("regions").select("*").order("name").execute()
    return res.data or []

def add_region(name: str, link_country_id: Optional[str]=None) -> str:
    res = admin.table("regions").insert({"name": name}).execute()
    if not (res.data):
        raise RuntimeError("Failed to insert region")
    row = res.data[0]
    region_id = row.get('id') or row.get('name')
    if link_country_id:
        try:
            admin.table("country_regions").insert({"country_id": link_country_id, "region_id": region_id}).execute()
        except Exception:
            pass
    return region_id

def update_region(region_id: str, new_name: str) -> None:
    admin.table("regions").update({"name": new_name}).eq("id", region_id).execute()

def delete_region(region_id: str) -> None:
    admin.table("regions").delete().eq("id", region_id).execute()

def fetch_exchange_houses():
    res = anon.table("exchange_houses").select(
        "id,name,country_id,region_id,created_at,"
        "countries(name),regions(name)"
    ).order("name").execute()
    houses = []
    for h in res.data or []:
        houses.append({
            "id": h["id"],
            "name": h["name"],
            "country_id": h.get("country_id"),
            "region_id": h.get("region_id"),
            "country_name": h.get("countries", {}).get("name") if h.get("countries") else "",
            "region_name": h.get("regions", {}).get("name") if h.get("regions") else ""
        })
    return houses

def add_exchange_house(name: str, country_id: Optional[str], region_id: Optional[str]) -> str:
    payload = {"name": name, "created_at": datetime.now().isoformat()}
    if country_id:
        payload["country_id"] = country_id
    if region_id:
        payload["region_id"] = region_id
    r = admin.table("exchange_houses").insert(payload).execute()
    return (r.data or [{}])[0].get('id') or (r.data or [{}])[0].get('name')

def update_exchange_house(doc_id: str, updates: dict):
    admin.table("exchange_houses").update(updates).eq("id", doc_id).execute()

def delete_exchange_house(doc_id: str):
    admin.table("exchange_houses").delete().eq("id", doc_id).execute()

def create_purchase_record(user_id: str, user_name: str, exchange_house_id: Optional[str], exchange_house_name: str,
                           exchange_region: Optional[str], currency: str, amount: float, cross_rate: float,
                           purchase_rate: float, revaluation_rate: float, tx_date=None) -> str:
    data = {
        "user_id": user_id,
        "user_name": user_name,
        "exchange_house_id": exchange_house_id,
        "exchange_house_name": exchange_house_name,
        "exchange_region": exchange_region or None,
        "currency": currency,
        "amount": float(amount),
        "cross_rate": float(cross_rate),
        "purchase_rate": float(purchase_rate),
        "revaluation_rate": float(revaluation_rate),
        "created_at": datetime.now().isoformat(),
        "tx_date": (tx_date.isoformat() if isinstance(tx_date, date)
                    else (tx_date if isinstance(tx_date, str)
                          else datetime.now().date().isoformat()))
    }
    r = admin.table("purchases").insert(data).execute()
    return (r.data or [{}])[0].get('id') or (r.data or [{}])[0].get('tx_date')

def update_purchase_record(doc_id: str, updates: dict):
    admin.table("purchases").update(updates).eq("id", doc_id).execute()

def delete_purchase_record(doc_id: str):
    admin.table("purchases").delete().eq("id", doc_id).execute()

def fetch_purchases_between(start_date: date, end_date: date) -> List[Dict[str, Any]]:
    res = anon.table("purchases").select("*").gte("tx_date", start_date.isoformat()).lte("tx_date", end_date.isoformat()).order("tx_date").execute()
    return res.data or []

def compute_summary(purchases, mode):
    if not purchases:
        base_cols = [mode, "Encashed amount (EQ_USD)", "Eqv BDT", "Wt avrg rate"]
        if mode == "Currency":
            base_cols.insert(1, "Actual cumulative Amount")
        return pd.DataFrame(columns=base_cols)

    house_map = {h["id"]: h for h in fetch_exchange_houses()}
    
    rows = []
    for r in purchases:
        label = ""
        if mode == "House":
            label = r.get("exchange_house_name", "") or ""
        elif mode == "Currency":
            label = r.get("currency", "") or ""
        elif mode == "Country":
            hid = r.get("exchange_house_id", "")
            label = (house_map.get(hid, {}) or {}).get("country_name", "") or ""
        elif mode == "Region":
            label = r.get("exchange_region", "") or ""
        else:
            label = r.get("exchange_house_name", "") or ""

        amt = float(r.get("amount", 0) or 0)
        cross = float(r.get("cross_rate", 0) or 0)
        purch = float(r.get("purchase_rate", 0) or 0)

        eq_usd = amt * cross
        eq_bdt = amt * purch

        row = {
            "group": label,
            "eq_usd": eq_usd,
            "eq_bdt": eq_bdt
        }
        if mode == "Currency":
            row["raw_amt"] = amt
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        base_cols = [mode, "Encashed amount (EQ_USD)", "Eqv BDT", "Wt avrg rate"]
        if mode == "Currency":
            base_cols.insert(1, "Actual cumulative Amount")
        return pd.DataFrame(columns=base_cols)

    agg = {"eq_usd": "sum", "eq_bdt": "sum"}
    if mode == "Currency":
        agg["raw_amt"] = "sum"

    g = df.groupby("group", dropna=False).agg(agg).reset_index()
    g["Wt avrg rate"] = g.apply(lambda x: (x["eq_bdt"] / x["eq_usd"]) if x["eq_usd"] else 0.0, axis=1)

    g = g.rename(columns={
        "group": mode,
        "eq_usd": "Encashed amount (EQ_USD)",
        "eq_bdt": "Eqv BDT",
        "raw_amt": "Actual cumulative Amount"
    })
    
    if mode == "Currency":
        g = g[[mode, "Actual cumulative Amount", "Encashed amount (EQ_USD)", "Eqv BDT", "Wt avrg rate"]]
    else:
        g = g[[mode, "Encashed amount (EQ_USD)", "Eqv BDT", "Wt avrg rate"]]

    return g

def generate_pdf_from_dataframe(df, title="Report", subtitle=""):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=30,
        rightMargin=30,
        topMargin=20,
        bottomMargin=30
    )
    styles = getSampleStyleSheet()
    Story = []

    h1 = styles["Heading1"]
    h1.alignment = 1
    h1.fontSize = 20
    h1.fontName = 'Helvetica-Bold'
    h1.spaceAfter = -2

    h2 = styles["Heading3"]
    h2.alignment = 1
    h2.fontSize = 9
    h2.fontName = 'Helvetica-Bold'
    h2.spaceAfter = 0

    h3 = styles["Heading2"]
    h3.alignment = 1
    h3.fontSize = 14
    h3.fontName = 'Helvetica-Bold'
    h3.spaceAfter = 0

    normal = styles["Normal"]
    normal.alignment = 1
    normal.spaceAfter = 0

    Story.append(Paragraph("Dutch Bangla Bank", h1))
    Story.append(Paragraph("Foreign Remittance Division", h2))
    Story.append(Paragraph("Purchase Entry System", h3))
    Story.append(Spacer(1, 0.1 * 12))
    Story.append(Paragraph(title, h2))

    if subtitle:
        Story.append(Paragraph(subtitle, normal))
    Story.append(Spacer(1, 0.2 * 12))

    if df.empty:
        Story.append(Paragraph("No data available for the selected period.", styles['Normal']))
    else:
        df_display = df.copy()
        if "Actions" in df_display.columns:
            df_display = df_display.drop(columns=["Actions"])

        grand_total_row_index = -1
        if "Grand Total" in df_display.iloc[:, 0].values:
            grand_total_row_index = df_display.index[df_display.iloc[:, 0] == "Grand Total"][0]

        data = [list(df_display.columns)] + df_display.values.tolist()
        
        table_style_list = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ADD8E6')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ]

        if grand_total_row_index != -1:
            list_index = df.index.get_loc(grand_total_row_index) + 1
            table_style_list.append(('ALIGN', (0, list_index), (-1, list_index), 'CENTER'))
            table_style_list.append(('FONTNAME', (0, list_index), (-1, list_index), 'Helvetica-Bold'))
            table_style_list.append(('SPAN', (0, list_index), (1, list_index)))

        table = Table(data, repeatRows=1, colWidths=None)
        table.setStyle(TableStyle(table_style_list))
        Story.append(table)

    doc.build(Story)
    buffer.seek(0)
    return buffer

def generate_excel_from_dataframe(df, sheet_name='Sheet1'):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    buffer.seek(0)
    return buffer

def _get_profile_name(profile):
    return profile.get("name") or profile.get("email") or "Guest"

def _render_home_page():
    st.header(f"Welcome, {_get_profile_name(st.session_state.profile)} 👋")
    st.write("Use the sidebar to navigate the application.")

def _render_purchase_entry():
    st.header("Purchase Entry")
    st.write("Fill out the form to add a new purchase record.")
    # Form for new purchase
    with st.form("purchase_form", clear_on_submit=True):
        st.write("New Purchase Record")
        houses = fetch_exchange_houses()
        house_options = {h["name"]: h["id"] for h in houses}
        house_names = ["Select House"] + list(house_options.keys())
        selected_house_name = st.selectbox("Exchange House", house_names, key="house_name")
        selected_house_id = house_options.get(selected_house_name)
        
        currency = st.text_input("Currency (e.g., USD, EUR)")
        amount = st.text_input("Amount")
        cross_rate = st.text_input("Cross Rate")
        purchase_rate = st.text_input("Purchase Rate")
        revaluation_rate = st.text_input("Revaluation Rate")
        tx_date = st.date_input("Transaction Date", value="today")

        submitted = st.form_submit_button("Save Purchase")
        if submitted:
            try:
                # Get relevant exchange house info
                house_info = next((h for h in houses if h["name"] == selected_house_name), {})
                exchange_region = house_info.get("region_name")
                
                # Check for required fields
                if not all([selected_house_id, currency, amount, cross_rate, purchase_rate, revaluation_rate, tx_date]):
                    st.error("Please fill in all fields.")
                else:
                    create_purchase_record(
                        user_id=st.session_state.profile["uid"],
                        user_name=st.session_state.profile["name"],
                        exchange_house_id=selected_house_id,
                        exchange_house_name=selected_house_name,
                        exchange_region=exchange_region,
                        currency=currency,
                        amount=float(amount),
                        cross_rate=float(cross_rate),
                        purchase_rate=float(purchase_rate),
                        revaluation_rate=float(revaluation_rate),
                        tx_date=tx_date
                    )
                    st.success("Purchase record saved successfully!")
            except ValueError:
                st.error("Invalid number format. Please check the amount and rate fields.")
            except Exception as e:
                st.error(f"Failed to save record: {e}")

def _render_reports():
    st.header("Reports")
    st.write("Generate detailed or summarized reports for purchases.")

    # Date range selector
    with st.container():
        st.subheader("Select Date Range")
        col1, col2 = st.columns(2)
        start_date = col1.date_input("Start Date", value=date.today())
        end_date = col2.date_input("End Date", value=date.today())

    # Report views
    report_views = ["Details", "Summary"]
    selected_report_view = st.radio("Select Report View", report_views, horizontal=True)

    if selected_report_view == "Summary":
        group_by_options = ["House", "Currency", "Country", "Region"]
        group_by = st.selectbox("Group By", group_by_options)

    if st.button("Generate Report"):
        purchases = fetch_purchases_between(start_date, end_date)
        if not purchases:
            st.warning("No data found for the selected date range.")
            return

        df = pd.DataFrame(purchases)
        df["tx_date"] = pd.to_datetime(df["tx_date"]).dt.date
        df.sort_values(by="tx_date", inplace=True)
        
        report_title = f"{selected_report_view} Report from {start_date} to {end_date}"
        
        if selected_report_view == "Details":
            st.subheader("Detailed Report")
            df_display = df.copy()
            st.dataframe(df_display)

            # Export buttons
            col1, col2 = st.columns(2)
            excel_buffer = generate_excel_from_dataframe(df)
            col1.download_button(
                label="Export to Excel",
                data=excel_buffer,
                file_name="detailed_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            pdf_buffer = generate_pdf_from_dataframe(df_display, title="Detailed Report", subtitle=f"From {start_date} to {end_date}")
            col2.download_button(
                label="Export to PDF",
                data=pdf_buffer,
                file_name="detailed_report.pdf",
                mime="application/pdf"
            )

        elif selected_report_view == "Summary":
            st.subheader(f"Summary Report (Grouped by {group_by})")
            summary_df = compute_summary(purchases, group_by)
            st.dataframe(summary_df)

            col1, col2 = st.columns(2)
            excel_buffer = generate_excel_from_dataframe(summary_df)
            col1.download_button(
                label="Export to Excel",
                data=excel_buffer,
                file_name="summary_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            pdf_buffer = generate_pdf_from_dataframe(summary_df, title="Summary Report", subtitle=f"Grouped by {group_by} from {start_date} to {end_date}")
            col2.download_button(
                label="Export to PDF",
                data=pdf_buffer,
                file_name="summary_report.pdf",
                mime="application/pdf"
            )

def _render_admin_menu():
    st.header("Admin Dashboard")
    st.write("Manage users, exchange houses, countries, and regions.")

    if "admin" not in st.session_state.profile["roles"]:
        st.warning("You do not have administrative privileges.")
        return

    st.subheader("Manage Users")
    user_expander = st.expander("Create & Manage Users")
    with user_expander:
        with st.form("create_user_form", clear_on_submit=True):
            st.write("Create New User")
            name = st.text_input("Name")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            short_id = st.text_input("4-digit ID (optional)")
            st.write("Roles:")
            col1, col2, col3 = st.columns(3)
            user_role = col1.checkbox("user", value=True)
            report_role = col2.checkbox("report")
            admin_role = col3.checkbox("admin")
            
            if st.form_submit_button("Create User"):
                if not all([name, email, password]):
                    st.error("Name, email, and password are required.")
                elif short_id and (not short_id.isdigit() or len(short_id) != 4):
                    st.error("Short ID must be a 4-digit number.")
                else:
                    roles = []
                    if user_role: roles.append("user")
                    if report_role: roles.append("report")
                    if admin_role: roles.append("admin")
                    try:
                        uid = admin_create_user(email=email, password=password, display_name=name, roles=roles, short_id=short_id or None)
                        st.success(f"User created with UID: {uid}")
                        st.session_state.users_last_updated = datetime.now()
                    except Exception as e:
                        st.error(f"Error creating user: {e}")

        st.subheader("Existing Users")
        if 'users_last_updated' not in st.session_state:
            st.session_state.users_last_updated = datetime.now()
        
        profiles = list_profiles()
        df_profiles = pd.DataFrame(profiles)
        df_profiles = df_profiles[["name", "email", "roles", "short_id", "uid"]]
        st.dataframe(df_profiles)
    
    st.subheader("Manage Exchange Houses")
    exchange_expander = st.expander("Manage Exchange Houses")
    with exchange_expander:
        # Simplified management without complex dialogs, using forms
        with st.form("manage_exchange_form", clear_on_submit=True):
            st.write("Add New Exchange House")
            name = st.text_input("Exchange House Name")
            countries = fetch_countries()
            country_options = {c["name"]: c["id"] for c in countries}
            country_names = ["Select a Country"] + list(country_options.keys())
            selected_country_name = st.selectbox("Country", country_names)
            selected_country_id = country_options.get(selected_country_name)
            
            regions = fetch_regions()
            region_options = {r["name"]: r["id"] for r in regions}
            region_names = ["Select a Region"] + list(region_options.keys())
            selected_region_name = st.selectbox("Region", region_names)
            selected_region_id = region_options.get(selected_region_name)

            if st.form_submit_button("Add Exchange House"):
                if not name:
                    st.error("Exchange House Name is required.")
                else:
                    try:
                        add_exchange_house(name, selected_country_id, selected_region_id)
                        st.success("Exchange house added.")
                    except Exception as e:
                        st.error(f"Failed to add exchange house: {e}")

        st.subheader("Existing Exchange Houses")
        houses = fetch_exchange_houses()
        df_houses = pd.DataFrame(houses)
        st.dataframe(df_houses)

def _render_main_app():
    if "is_authenticated" not in st.session_state or not st.session_state["is_authenticated"]:
        _render_login()
    else:
        st.sidebar.title("Navigation")
        if "admin" in st.session_state.profile["roles"]:
            page = st.sidebar.radio("Go to", ["Home", "Purchase Entry", "Reports", "Admin"])
        else:
            page = st.sidebar.radio("Go to", ["Home", "Purchase Entry", "Reports"])
        
        st.sidebar.markdown("---")
        st.sidebar.write(f"Logged in as: **{st.session_state.profile['name']}**")
        if st.sidebar.button("Logout"):
            st.session_state["is_authenticated"] = False
            st.session_state["profile"] = None
            st.experimental_rerun()

        if page == "Home":
            _render_home_page()
        elif page == "Purchase Entry":
            _render_purchase_entry()
        elif page == "Reports":
            _render_reports()
        elif page == "Admin":
            _render_admin_menu()

def _render_login():
    st.title("Purchase Entry System")
    st.markdown("### Login")
    
    with st.form("login_form"):
        identity = st.text_input("Email or 4-digit ID", key="login_identity")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Login")

        if submitted:
            try:
                if not identity or not password:
                    st.error("Please provide login (email or 4-digit ID) and password.")
                    return

                if identity.isdigit() and len(identity) == 4:
                    uid, profile = get_user_by_short_id(identity)
                    if not uid:
                        st.error("No user found with that 4-digit ID.")
                        return
                    email = profile.get("email")
                    if not email:
                        st.error("User has no email; cannot sign in with 4-digit ID.")
                        return
                    
                    access_token, uid = client_sign_in(email, password)
                    profile = get_user_profile(uid)
                    if not profile:
                        st.error("Profile missing in Supabase. Ask admin.")
                        return

                else:
                    access_token, uid = client_sign_in(identity, password)
                    profile = get_user_profile(uid)
                    if not profile:
                        st.error("Profile not found. Ask admin.")
                        return

                st.session_state["is_authenticated"] = True
                st.session_state["profile"] = profile
                st.success("Login successful!")
                st.experimental_rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Unexpected error during login: {e}")

# Main application logic
if "supabase_initialized" not in st.session_state:
    init_supabase()

_render_main_app()