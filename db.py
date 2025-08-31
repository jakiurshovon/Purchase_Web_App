import os
from typing import Optional, List
from supabase import create_client
from dotenv import load_dotenv
import streamlit as st


# Load .env for local dev
load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")


if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Supabase credentials not set. Add SUPABASE_URL & SUPABASE_KEY in .env or Streamlit Secrets.")
    st.stop()


# Single global client
sb = create_client(SUPABASE_URL, SUPABASE_KEY)


# Convenience wrappers


def table(name: str):
    return sb.table(name)


def auth_client():
    return sb.auth


def get_profile(user_id: str):
    return table("profiles").select("uid,name,email,roles,short_id").eq("uid", user_id).single().execute().data


def ensure_profile_fields(data: dict):
# Normalize role/roles differences if needed
    if "roles" in data and "role" not in data:
        data["role"] = data["roles"]
    return data

def fetch_all(table_name: str, column_name: str) -> List[str]:
    try:
        res = table(table_name).select(column_name).order(column_name).execute()
        return sorted([r.get(column_name) for r in res.data or [] if r.get(column_name) is not None])
    except Exception as e:
        st.error(f"Error fetching {table_name}: {e}")
        return []