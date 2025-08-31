import streamlit as st
from datetime import date
from auth import login_form, logout_button
from masters import masters_page
from purchase import create_form, edit_grid
from reports import summary_page, detail_page
from ui_components import filters_section

st.set_page_config(page_title="Purchase Entry Web App", layout="wide")


def sidebar_menu():
    st.sidebar.title(" Menu")
    pages = ["Dashboard", "Purchase Entry", "Summary Report", "Detail Report", "Masters"]
    if "user" in st.session_state and st.session_state["user"].get("role") != "admin":
    
    # hide Masters for non-admins
        pages = [p for p in pages if p != "Masters"]
    choice = st.sidebar.radio("Go to:", pages)
    logout_button()
    return choice
    
def dashboard():
    st.markdown("# Dashboard")
    st.info("Welcome to the purchase entry web app!")


def main():
    # Auth gate
    user = st.session_state.get("user")
    if not user:
        login_form()
        return
    choice = sidebar_menu()
    
    # Shared filters for reports and list
    filters = filters_section(
        countries=[], # You can prefetch from masters tables if needed
        regions=[],
        houses=[],
    )
    
    if choice == "Dashboard":
        dashboard()
    elif choice == "Purchase Entry":
        create_form()
        st.divider()
        edit_grid(filters)
    elif choice == "Summary Report":
        summary_page(filters)
    elif choice == "Detail Report":
        detail_page(filters)
    elif choice == "Masters":
        role = user.get("role", "")
        masters_page(role)
    
if __name__ == "__main__":
    main()
