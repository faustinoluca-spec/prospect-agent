import os
import streamlit as st
from supabase import create_client, Client


# ── Client ────────────────────────────────────────────────────────────────────

def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")
    return create_client(url, key)


# ── Auth ──────────────────────────────────────────────────────────────────────

def register(email: str, password: str, display_name: str = "") -> tuple:
    try:
        sb = get_supabase()
        res = sb.auth.sign_up({"email": email, "password": password})
        if res.user:
            sb.table("user_configs").insert({
                "user_id": res.user.id,
                "display_name": display_name or email.split("@")[0],
                "gmail": "",
                "gmail_app_password": "",
                "hunter_api_key": "",
            }).execute()
            return True, "Conta criada com sucesso!"
        return False, "Erro ao criar conta."
    except Exception as e:
        msg = str(e)
        if "already registered" in msg:
            return False, "Este email já está cadastrado."
        return False, msg


def login(email: str, password: str) -> tuple:
    try:
        sb = get_supabase()
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            return True, res.session, res.user
        return False, None, None
    except Exception as e:
        msg = str(e)
        if "Invalid" in msg or "invalid" in msg:
            return False, None, None
        return False, None, None


# ── User config ───────────────────────────────────────────────────────────────

def load_user_config(user_id: str) -> dict:
    try:
        sb = get_supabase()
        res = sb.table("user_configs").select("*").eq("user_id", user_id).execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return {"gmail": "", "gmail_app_password": "", "hunter_api_key": "", "display_name": ""}


def save_user_config(user_id: str, config: dict):
    sb = get_supabase()
    existing = sb.table("user_configs").select("user_id").eq("user_id", user_id).execute()
    if existing.data:
        sb.table("user_configs").update(config).eq("user_id", user_id).execute()
    else:
        sb.table("user_configs").insert({"user_id": user_id, **config}).execute()


# ── Visited prospects ─────────────────────────────────────────────────────────

def load_visited(user_id: str) -> set:
    try:
        sb = get_supabase()
        res = sb.table("visited_prospects").select("website").eq("user_id", user_id).execute()
        return {r["website"] for r in res.data}
    except Exception:
        return set()


def save_visited_url(user_id: str, website: str, email: str = None):
    try:
        sb = get_supabase()
        sb.table("visited_prospects").insert({
            "user_id": user_id,
            "website": website,
            "email": email,
        }).execute()
    except Exception:
        pass


def count_visited(user_id: str) -> int:
    try:
        sb = get_supabase()
        res = sb.table("visited_prospects").select("website", count="exact").eq("user_id", user_id).execute()
        return res.count or 0
    except Exception:
        return 0


def is_sent(user_id: str, website: str) -> bool:
    try:
        sb = get_supabase()
        res = (sb.table("visited_prospects")
               .select("email")
               .eq("user_id", user_id)
               .eq("website", website)
               .execute())
        if res.data:
            return bool(res.data[0].get("email"))
    except Exception:
        pass
    return False


def mark_sent(user_id: str, website: str, email: str):
    try:
        sb = get_supabase()
        sb.table("visited_prospects").update({"email": email}).eq("user_id", user_id).eq("website", website).execute()
    except Exception:
        pass


def reset_visited(user_id: str):
    try:
        sb = get_supabase()
        sb.table("visited_prospects").delete().eq("user_id", user_id).execute()
    except Exception:
        pass
