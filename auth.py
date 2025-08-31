from typing import Optional
import streamlit as st
from db import auth_client, get_profile, ensure_profile_fields



def login_form() -> Optional[dict]:
    st.title("🔑 Login")
    email = st.text_input("Email")
    pwd = st.text_input("Password", type="password")


    if st.button("Login", type="primary"):
        try:
            res = auth_client().sign_in_with_password({"email": email.strip(), "password": pwd.strip()})
            if not res.user:
                st.error("Invalid email/password")
                return None
            prof = get_profile(res.user.id)
            if not prof:
                st.error("No profile row found for this account. Ask admin to create 'profiles' record.")
                return None
            prof = ensure_profile_fields(prof)
            prof["auth_user_id"] = res.user.id
            st.session_state["user"] = prof
            st.success(f"Welcome {prof.get('name','')} ({prof.get('role','')})")
            st.rerun()
        
        except Exception as e:
            st.error(f"Login failed: {e}")
            return None




def logout_button():
    if st.sidebar.button("Logout"):
        try:
            auth_client().sign_out()
        finally:
            st.session_state.pop("user", None)
            st.rerun()