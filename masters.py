import streamlit as st
import pandas as pd
from db import table
from ui_components import header

MASTER_TABLES = [
    {"name": "countries", "cols": ["name", "code"]},
    {"name": "regions", "cols": ["name"]},
    {"name": "exchange_houses", "cols": ["name", "country", "region"]},
]



def render_master(name: str, cols):
    header(f" Master: {name}")
    # List
    res = table(name).select("*").execute()
    df = pd.DataFrame(res.data or [])
    st.dataframe(df, use_container_width=True)
    
    with st.expander("Add / Update"):
        inputs = {}
        cols_cont = st.columns(len(cols))
        for i, c in enumerate(cols):
            with cols_cont[i]:
                inputs[c] = st.text_input(c.capitalize())
        rid = st.text_input("id (for update only)")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Add", type="primary"):
                try:
                    table(name).insert(inputs).execute()
                    st.success("Added")
                    st.rerun()
                except Exception as e:
                    st.error(f"Add failed: {e}")
        with c2:
            if st.button("Update by id"):
                try:
                    if not rid:
                        st.warning("Provide id for update")
                    else:
                        table(name).update(inputs).eq("id", rid).execute()
                        st.success("Updated")
                        st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")



def masters_page(user_role: str):
    if user_role != "admin":
        st.warning(" Only admins can access Masters page.")
        return
    tabs = st.tabs([m["name"].capitalize() for m in MASTER_TABLES])
    for t, m in zip(tabs, MASTER_TABLES):
        with t:
            render_master(m["name"], m["cols"])