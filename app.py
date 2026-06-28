import io
import json
import os

import pandas as pd
import streamlit as st

from prospector_agent import run_prospector
from email_sender import config_is_complete, send_email
from auth import (
    login, register,
    load_user_config, save_user_config,
    count_visited, load_visited, save_visited_url,
    is_sent, mark_sent, reset_visited,
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="AI Prospector", page_icon="🎯", layout="wide")

# ── Global CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', sans-serif !important; box-sizing: border-box; }

/* ── Base ── */
.stApp {
    background: #060610;
    background-image:
        radial-gradient(ellipse 80% 50% at 50% -10%, rgba(99,102,241,0.12), transparent),
        linear-gradient(rgba(99,102,241,0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(99,102,241,0.025) 1px, transparent 1px);
    background-size: 100% 100%, 48px 48px, 48px 48px;
    min-height: 100vh;
}
#MainMenu, footer, header { visibility: hidden; }
.main .block-container { padding-top: 0; padding-bottom: 3rem; max-width: 1080px; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: rgba(8,8,20,0.95) !important;
    border-right: 1px solid rgba(255,255,255,0.05) !important;
    backdrop-filter: blur(20px);
}
section[data-testid="stSidebar"] * { color: #64748b !important; }
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] strong { color: #cbd5e1 !important; }

/* ── Inputs ── */
.stTextArea textarea, .stTextInput input {
    background: rgba(15,15,35,0.8) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 14px !important;
    color: #e2e8f0 !important;
    font-size: 0.95rem !important;
    transition: all 0.25s ease !important;
    backdrop-filter: blur(10px);
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: rgba(99,102,241,0.6) !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.12), 0 0 20px rgba(99,102,241,0.08) !important;
    background: rgba(15,15,40,0.95) !important;
}
.stTextArea label, .stTextInput label { color: #475569 !important; font-size: 0.75rem !important; letter-spacing: 0.05em; }

/* ── Buttons ── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%) !important;
    color: white !important; border: none !important;
    border-radius: 12px !important; font-weight: 700 !important;
    font-size: 0.9rem !important; letter-spacing: 0.02em !important;
    padding: 0.65rem 1.75rem !important;
    box-shadow: 0 4px 24px rgba(99,102,241,0.4), inset 0 1px 0 rgba(255,255,255,0.15) !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 32px rgba(99,102,241,0.55), inset 0 1px 0 rgba(255,255,255,0.2) !important;
}
.stButton > button[kind="primary"]:active { transform: translateY(0px) !important; }
.stButton > button[kind="secondary"] {
    background: rgba(15,15,30,0.8) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #64748b !important; border-radius: 10px !important;
    font-weight: 500 !important; transition: all 0.2s !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: rgba(99,102,241,0.4) !important; color: #94a3b8 !important;
}

/* ── Cards / Expander ── */
.stExpander {
    background: rgba(10,10,25,0.7) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 18px !important;
    overflow: hidden !important;
    margin-bottom: 0.85rem !important;
    backdrop-filter: blur(10px);
    transition: border-color 0.2s !important;
}
.stExpander:hover { border-color: rgba(99,102,241,0.2) !important; }
.stExpander > details > summary {
    background: transparent !important;
    color: #cbd5e1 !important; font-weight: 600 !important;
    padding: 1.1rem 1.4rem !important; font-size: 0.95rem !important;
}
.stExpander > details > summary:hover { color: #e2e8f0 !important; }
.stExpander > details[open] > summary {
    border-bottom: 1px solid rgba(255,255,255,0.05) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(10,10,25,0.8) !important;
    border-radius: 12px !important; padding: 4px !important;
    gap: 3px !important; border: 1px solid rgba(255,255,255,0.06) !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important; color: #475569 !important;
    border-radius: 9px !important; font-weight: 500 !important;
    font-size: 0.82rem !important; padding: 0.4rem 0.9rem !important;
    transition: all 0.2s !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #94a3b8 !important; }
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: white !important; font-weight: 600 !important;
    box-shadow: 0 2px 12px rgba(99,102,241,0.35) !important;
}
.stTabs [data-baseweb="tab-panel"] { padd