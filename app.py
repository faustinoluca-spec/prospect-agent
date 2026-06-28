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
.stTabs [data-baseweb="tab-panel"] { padding-top: 0.75rem !important; background: transparent !important; }

/* ── Metrics ── */
[data-testid="metric-container"] {
    background: rgba(10,10,25,0.7) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 14px !important; padding: 1.1rem 1.25rem !important;
    backdrop-filter: blur(10px);
}
[data-testid="metric-container"] label { color: #334155 !important; font-size: 0.72rem !important; text-transform: uppercase; letter-spacing: 0.08em; }
[data-testid="stMetricValue"] { color: #e2e8f0 !important; font-weight: 700 !important; }

/* ── Alerts ── */
.stSuccess > div {
    background: rgba(16,185,129,0.07) !important; border: 1px solid rgba(16,185,129,0.2) !important;
    border-radius: 12px !important; color: #34d399 !important;
}
.stWarning > div {
    background: rgba(245,158,11,0.07) !important; border: 1px solid rgba(245,158,11,0.2) !important;
    border-radius: 12px !important; color: #fbbf24 !important;
}
.stError > div {
    background: rgba(239,68,68,0.07) !important; border: 1px solid rgba(239,68,68,0.2) !important;
    border-radius: 12px !important;
}
.stInfo > div {
    background: rgba(99,102,241,0.07) !important; border: 1px solid rgba(99,102,241,0.2) !important;
    border-radius: 12px !important; color: #818cf8 !important;
}

/* ── Status ── */
[data-testid="stStatus"] {
    background: rgba(10,10,25,0.8) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 14px !important; color: #64748b !important;
    backdrop-filter: blur(10px);
}

/* ── Misc ── */
hr { border-color: rgba(255,255,255,0.05) !important; margin: 1.25rem 0 !important; }
.stMarkdown p { color: #64748b; line-height: 1.7; }
.stCheckbox label { color: #475569 !important; font-size: 0.85rem !important; }
.stDownloadButton button {
    background: rgba(10,10,25,0.8) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    color: #64748b !important; border-radius: 10px !important; box-shadow: none !important;
}
.stCaption, [data-testid="stCaptionContainer"] p { color: #334155 !important; }

/* ── Login card ── */
.login-card {
    background: rgba(12,12,28,0.85);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 24px;
    padding: 2.5rem 2.75rem;
    backdrop-filter: blur(20px);
    box-shadow: 0 32px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(99,102,241,0.05);
    max-width: 440px;
    margin: 0 auto;
}

/* ── Gradient text util ── */
.grad {
    background: linear-gradient(135deg, #f1f5f9 0%, #818cf8 50%, #06b6d4 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.grad-subtle {
    background: linear-gradient(135deg, #94a3b8, #6366f1);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
</style>
""", unsafe_allow_html=True)


# ── Session init ──────────────────────────────────────────────────────────────

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_id"]   = None
    st.session_state["user_email"] = None
    st.session_state["display_name"] = None


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def show_login():
    st.markdown("""
    <div style="padding:4rem 0 2rem 0; text-align:center;">
        <div style="font-size:2.8rem; margin-bottom:0.5rem;">🎯</div>
        <h1 style="font-size:2.4rem; font-weight:900; margin:0 0 0.4rem 0;
                   background:linear-gradient(135deg,#f1f5f9,#818cf8,#06b6d4);
                   -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;">
            AI Prospector
        </h1>
        <p style="color:#334155; font-size:0.95rem; margin:0 0 2.5rem 0;">
            Prospecção B2B com inteligência artificial
        </p>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.8, 1])
    with col:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["  Entrar  ", "  Criar conta  "])

        with tab_login:
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            email    = st.text_input("Email", key="li_email", placeholder="seu@email.com")
            password = st.text_input("Senha", key="li_pass",  placeholder="••••••••", type="password")
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

            if st.button("Entrar →", type="primary", use_container_width=True, key="btn_login"):
                if not email or not password:
                    st.error("Preencha email e senha.")
                else:
                    ok, session, user = login(email, password)
                    if ok:
                        config = load_user_config(user.id)
                        st.session_state["logged_in"]    = True
                        st.session_state["user_id"]      = user.id
                        st.session_state["user_email"]   = user.email
                        st.session_state["display_name"] = config.get("display_name") or user.email.split("@")[0]
                        st.rerun()
                    else:
                        st.error("Email ou senha incorretos.")

        with tab_register:
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            new_email = st.text_input("Email",  key="reg_email", placeholder="seu@email.com")
            new_name  = st.text_input("Nome",   key="reg_name",  placeholder="Como quer ser chamado")
            new_pass  = st.text_input("Senha",  key="reg_pass",  placeholder="Mínimo 6 caracteres", type="password")
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

            if st.button("Criar conta →", type="primary", use_container_width=True, key="btn_register"):
                if not new_email or not new_pass:
                    st.error("Preencha email e senha.")
                else:
                    ok, msg = register(new_email, new_pass, new_name)
                    if ok:
                        ok2, session, user = login(new_email, new_pass)
                        if ok2:
                            st.session_state["logged_in"]    = True
                            st.session_state["user_id"]      = user.id
                            st.session_state["user_email"]   = user.email
                            st.session_state["display_name"] = new_name or new_email.split("@")[0]
                            st.rerun()
                        else:
                            st.success(msg + " Faça login.")
                    else:
                        st.error(msg)

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("""
    <p style="text-align:center; color:#1e2235; font-size:0.75rem; margin-top:2rem;">
        Autenticação segura via Supabase. Seus dados ficam protegidos na nuvem.
    </p>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

def show_app():
    user_id      = st.session_state["user_id"]
    display_name = st.session_state["display_name"]
    config       = load_user_config(user_id)
    can_send     = config_is_complete(config)

    # ── Sidebar ───────────────────────────────────────────────────────────────

    with st.sidebar:
        st.markdown(f"""
        <div style="padding:0.75rem 0 0.5rem 0;">
            <div style="font-size:1.2rem; font-weight:800; color:#e2e8f0; letter-spacing:-0.02em;">🎯 AI Prospector</div>
            <div style="font-size:0.75rem; color:#334155; margin-top:0.15rem;">Olá, <b style="color:#6366f1;">{display_name}</b></div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Sair", type="secondary", key="logout"):
            st.session_state.clear()
            st.rerun()

        st.divider()

        # Configurações opcionais
        st.markdown("""
        <div style="font-size:0.68rem;font-weight:700;letter-spacing:0.12em;color:#334155;text-transform:uppercase;margin-bottom:0.75rem;">
            ⚙️ Configurações
        </div>
        <div style="font-size:0.78rem;color:#334155;margin-bottom:1rem;line-height:1.6;">
            Tudo abaixo é <b style="color:#475569;">opcional</b>.<br>
            O app funciona sem configurar nada.<br>
            Gmail e Hunter.io desbloqueiam o envio de emails.
        </div>
        """, unsafe_allow_html=True)

        gmail      = st.text_input("Gmail de envio", value=config.get("gmail",""), placeholder="seuemail@gmail.com")
        gmail_pass = st.text_input("Senha de app Gmail", value=config.get("gmail_app_password",""), type="password",
                                   placeholder="xxxx xxxx xxxx xxxx",
                                   help="Google → Gerenciar conta → Segurança → Senhas de app")
        hunter_key = st.text_input("Hunter.io API Key", value=config.get("hunter_api_key",""), type="password",
                                   placeholder="Encontra emails verificados",
                                   help="Crie conta gratuita em hunter.io — 25 buscas/mês")

        if st.button("💾 Salvar configurações", type="secondary", use_container_width=True):
            save_user_config(user_id, {"display_name": display_name, "gmail": gmail, "gmail_app_password": gmail_pass, "hunter_api_key": hunter_key})
            config = load_user_config(user_id)
            st.success("Salvo!")
            st.rerun()

        st.divider()

        visited = count_visited(user_id)
        c1, c2 = st.columns(2)
        c1.metric("Mapeados", visited)
        c2.metric("Nesta sessão", len(st.session_state.get("prospects", [])))

        if visited > 0:
            if st.button("🗑️ Resetar histórico", type="secondary", use_container_width=True):
                reset_visited(user_id)
                st.session_state.pop("prospects", None)
                st.rerun()

    # ── Hero ──────────────────────────────────────────────────────────────────

    st.markdown("""
    <div style="text-align:center; padding:3.5rem 0 2.75rem 0;">
        <div style="display:inline-flex; align-items:center; gap:0.5rem;
                    background:rgba(99,102,241,0.08); border:1px solid rgba(99,102,241,0.2);
                    border-radius:50px; padding:0.3rem 1rem 0.3rem 0.75rem;
                    color:#6366f1; font-size:0.7rem; font-weight:700;
                    letter-spacing:0.1em; text-transform:uppercase; margin-bottom:2rem;">
            <span style="width:6px;height:6px;border-radius:50%;background:#6366f1;
                         box-shadow:0 0 8px #6366f1; display:inline-block;"></span>
            Groq &nbsp;·&nbsp; LangGraph &nbsp;·&nbsp; Serper &nbsp;·&nbsp; Hunter.io
        </div>
        <h1 style="font-size:3.2rem; font-weight:900; line-height:1.08; margin:0 0 1.1rem 0;
                   background:linear-gradient(135deg,#f8fafc 0%,#a5b4fc 45%,#22d3ee 100%);
                   -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
                   letter-spacing:-0.03em;">
            Encontre clientes.<br>Não apenas contatos.
        </h1>
        <p style="color:#475569; font-size:1rem; max-width:520px; margin:0 auto 2.75rem auto; line-height:1.75; font-weight:400;">
            Descreva quem você quer atingir. O agente pesquisa na web, analisa os sites,
            identifica o decisor e escreve mensagens personalizadas — em minutos.
        </p>
        <div style="display:flex; justify-content:center; align-items:center; gap:3.5rem; flex-wrap:wrap;">
            <div style="text-align:center;">
                <div style="font-size:2.1rem; font-weight:800;
                            background:linear-gradient(135deg,#6366f1,#818cf8);
                            -webkit-background-clip:text; -webkit-text-fill-color:transparent;">~2 min</div>
                <div style="font-size:0.7rem; color:#334155; text-transform:uppercase; letter-spacing:0.1em; margin-top:0.3rem; font-weight:600;">por campanha</div>
            </div>
            <div style="width:1px; height:36px; background:linear-gradient(to bottom,transparent,rgba(255,255,255,0.07),transparent);"></div>
            <div style="text-align:center;">
                <div style="font-size:2.1rem; font-weight:800;
                            background:linear-gradient(135deg,#06b6d4,#38bdf8);
                            -webkit-background-clip:text; -webkit-text-fill-color:transparent;">5–10+</div>
                <div style="font-size:0.7rem; color:#334155; text-transform:uppercase; letter-spacing:0.1em; margin-top:0.3rem; font-weight:600;">prospects qualificados</div>
            </div>
            <div style="width:1px; height:36px; background:linear-gradient(to bottom,transparent,rgba(255,255,255,0.07),transparent);"></div>
            <div style="text-align:center;">
                <div style="font-size:2.1rem; font-weight:800;
                            background:linear-gradient(135deg,#8b5cf6,#a78bfa);
                            -webkit-background-clip:text; -webkit-text-fill-color:transparent;">3×</div>
                <div style="font-size:0.7rem; color:#334155; text-transform:uppercase; letter-spacing:0.1em; margin-top:0.3rem; font-weight:600;">variações de mensagem</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Input card ────────────────────────────────────────────────────────────

    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(99,102,241,0.07) 0%,rgba(139,92,246,0.04) 100%);
                border:1px solid rgba(99,102,241,0.13); border-radius:22px;
                padding:1.75rem 2rem 1.25rem 2rem; margin-bottom:1.5rem;
                box-shadow:0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.04);">
        <div style="font-size:0.65rem; font-weight:800; letter-spacing:0.14em;
                    color:#6366f1; text-transform:uppercase; margin-bottom:0.65rem;">
            ✦ &nbsp; Defina seu cliente ideal (ICP)
        </div>
    """, unsafe_allow_html=True)

    icp = st.text_area("icp", placeholder="Ex: Startups de tecnologia B2B em São Paulo com 20 a 100 funcionários, time de vendas estruturado e produto SaaS.",
                        height=95, label_visibility="collapsed")

    st.markdown("</div>", unsafe_allow_html=True)

    c_btn, c_hint = st.columns([1, 3])
    with c_btn:
        run = st.button("🔍  Prospectar", type="primary", disabled=not icp.strip(), use_container_width=True)
    with c_hint:
        if config.get("hunter_api_key"):
            st.markdown("<p style='color:#475569;font-size:0.8rem;padding-top:0.7rem;'>✦ Hunter.io ativo — emails serão buscados automaticamente</p>", unsafe_allow_html=True)
        else:
            st.markdown("<p style='color:#1e2235;font-size:0.8rem;padding-top:0.7rem;'>Configure Hunter.io na sidebar para encontrar emails verificados (opcional)</p>", unsafe_allow_html=True)

    # ── Pipeline visual ───────────────────────────────────────────────────────

    st.markdown("""
    <div style="display:flex; align-items:center; gap:0; margin:1.75rem 0 2rem 0;
                background:rgba(8,8,20,0.6); border:1px solid rgba(255,255,255,0.05);
                border-radius:14px; padding:0.85rem 1.5rem; overflow-x:auto; flex-wrap:nowrap;">
        <div style="display:flex; align-items:center; gap:0.5rem; white-space:nowrap;">
            <span style="font-size:0.7rem;color:#334155;">🧠 Queries IA</span>
        </div>
        <div style="flex:1; height:1px; background:linear-gradient(to right,rgba(99,102,241,0.3),transparent); min-width:16px; margin:0 0.5rem;"></div>
        <div style="display:flex; align-items:center; gap:0.5rem; white-space:nowrap;">
            <span style="font-size:0.7rem;color:#334155;">🌐 Busca web</span>
        </div>
        <div style="flex:1; height:1px; background:linear-gradient(to right,rgba(99,102,241,0.3),transparent); min-width:16px; margin:0 0.5rem;"></div>
        <div style="display:flex; align-items:center; gap:0.5rem; white-space:nowrap;">
            <span style="font-size:0.7rem;color:#334155;">✅ Qualificação</span>
        </div>
        <div style="flex:1; height:1px; background:linear-gradient(to right,rgba(99,102,241,0.3),transparent); min-width:16px; margin:0 0.5rem;"></div>
        <div style="display:flex; align-items:center; gap:0.5rem; white-space:nowrap;">
            <span style="font-size:0.7rem;color:#334155;">🔍 Scraping</span>
        </div>
        <div style="flex:1; height:1px; background:linear-gradient(to right,rgba(99,102,241,0.3),transparent); min-width:16px; margin:0 0.5rem;"></div>
        <div style="display:flex; align-items:center; gap:0.5rem; white-space:nowrap;">
            <span style="font-size:0.7rem;color:#334155;">👤 Decisor</span>
        </div>
        <div style="flex:1; height:1px; background:linear-gradient(to right,rgba(99,102,241,0.3),transparent); min-width:16px; margin:0 0.5rem;"></div>
        <div style="display:flex; align-items:center; gap:0.5rem; white-space:nowrap;">
            <span style="font-size:0.7rem;color:#334155;">✉️ Mensagem</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Execução ──────────────────────────────────────────────────────────────

    if run and icp.strip():
        for key in ["prospects", "approved", "debug_info"]:
            st.session_state.pop(key, None)

        with st.status("Agente trabalhando...", expanded=True) as status:
            st.write("🧠 Gerando queries de busca inteligentes...")
            st.write("🌐 Varrendo a web em busca de empresas...")
            st.write("✅ Qualificando e filtrando com IA (retry automático se < 5)...")
            st.write("🔍 Analisando o site de cada empresa...")
            st.write("👤 Identificando CEO ou fundador...")
            if config.get("hunter_api_key"):
                st.write("📧 Buscando emails verificados via Hunter.io...")
            st.write("✉️ Gerando 3 variações de mensagem por empresa...")

            try:
                prospects, debug_info = run_prospector(
                    icp.strip(),
                    hunter_api_key=config.get("hunter_api_key") or None
                )
                status.update(label=f"✅ {len(prospects)} prospect(s) encontrado(s)", state="complete", expanded=False)
                st.session_state["prospects"]  = prospects
                st.session_state["debug_info"] = debug_info
                st.session_state["approved"]   = {i: True for i in range(len(prospects))}
                # Salvar no Supabase
                for p in prospects:
                    save_visited_url(user_id, p["website"])
            except Exception as e:
                status.update(label="Erro durante a prospecção.", state="error", expanded=True)
                st.error(f"Detalhes: {e}")

    # ── Debug ─────────────────────────────────────────────────────────────────

    if st.session_state.get("debug_info"):
        d = st.session_state["debug_info"]
        with st.expander("🔬 Raio-X da prospecção", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tentativas", d["attempts"])
            c2.metric("Resultados brutos", d["raw_results_count"])
            c3.metric("Qualificados", d["qualified_count"])
            c4.metric("Bloqueados", len(d["blocked_urls"]))

            if d.get("queries"):
                st.markdown("<div style='margin-top:0.75rem;font-size:0.7rem;font-weight:700;color:#334155;text-transform:uppercase;letter-spacing:0.1em;'>Queries geradas</div>", unsafe_allow_html=True)
                for q in d["queries"]:
                    st.markdown(f"<div style='font-size:0.8rem;color:#334155;padding:0.18rem 0;'>→ {q}</div>", unsafe_allow_html=True)

            if d.get("blocked_urls"):
                st.markdown("<div style='margin-top:0.75rem;font-size:0.7rem;font-weight:700;color:#334155;text-transform:uppercase;letter-spacing:0.1em;'>URLs bloqueadas</div>", unsafe_allow_html=True)
                for url in d["blocked_urls"]:
                    st.markdown(f"<div style='font-size:0.8rem;color:#1e2235;text-decoration:line-through;padding:0.18rem 0;'>{url}</div>", unsafe_allow_html=True)

            st.caption("Rastreamento completo no LangSmith → ProspectorAgent")

    # ── Resultados ────────────────────────────────────────────────────────────

    if st.session_state.get("prospects"):
        prospects = st.session_state["prospects"]

        if not prospects:
            st.warning("Nenhum prospect encontrado. Tente refinar o ICP.")
            return

        approved_count = sum(1 for v in st.session_state.get("approved", {}).values() if v)

        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:0.9rem; margin:2.25rem 0 1.25rem 0;">
            <div style="font-size:1.25rem; font-weight:700; color:#e2e8f0; letter-spacing:-0.01em;">Resultados</div>
            <div style="background:rgba(99,102,241,0.1); border:1px solid rgba(99,102,241,0.25);
                        border-radius:50px; padding:0.2rem 0.85rem; font-size:0.75rem;
                        font-weight:600; color:#818cf8; letter-spacing:0.02em;">
                {len(prospects)} encontrados
            </div>
            <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.2);
                        border-radius:50px; padding:0.2rem 0.85rem; font-size:0.75rem;
                        font-weight:600; color:#34d399; letter-spacing:0.02em;">
                {approved_count} aprovados
            </div>
        </div>
        """, unsafe_allow_html=True)

        def sc_color(s): return "#10b981" if s>=8 else "#f59e0b" if s>=6 else "#ef4444"
        def sc_icon(s):  return "🟢" if s>=8 else "🟡" if s>=6 else "🔴"

        for i, p in enumerate(prospects):
            sc = p["fit_score"]
            color = sc_color(sc)
            already_sent = is_sent(user_id, p["website"])

            dm_badge  = f" · 👤 {p['decisor']}" if p.get("decisor") else ""
            em_badge  = f" · 📧 {p['email']}"   if p.get("email")   else ""
            sent_badge = " · ✅ Enviado"          if already_sent     else ""

            with st.expander(
                f"{sc_icon(sc)} **{p['empresa']}** — Fit {sc}/10{dm_badge}{em_badge}{sent_badge}",
                expanded=(i == 0)
            ):
                approved = st.checkbox("Aprovar", value=st.session_state["approved"].get(i, True), key=f"approve_{i}")
                st.session_state["approved"][i] = approved

                st.divider()
                left, right = st.columns([1, 1], gap="large")

                with left:
                    st.markdown(f"""
                    <div style="display:flex; align-items:flex-start; gap:0.85rem; margin-bottom:1.1rem;">
                        <div style="width:46px; height:46px; border-radius:50%; flex-shrink:0;
                                    background:linear-gradient(135deg,{color}15,{color}30);
                                    border:2px solid {color}50;
                                    display:flex; align-items:center; justify-content:center;
                                    font-size:1.05rem; font-weight:800; color:{color};">{sc}</div>
                        <div>
                            <div style="font-size:0.65rem;color:#334155;text-transform:uppercase;
                                        letter-spacing:0.1em;font-weight:700; margin-bottom:0.2rem;">Fit Score</div>
                            <div style="font-size:0.82rem;color:#64748b;line-height:1.5;">{p['motivo_fit']}</div>
                        </div>
                    </div>
                    <div style="font-size:0.85rem;color:#64748b;margin-bottom:0.5rem;">
                        🌐 <a href="{p['website']}" target="_blank" style="color:#818cf8;text-decoration:none;">{p['website']}</a>
                    </div>
                    <div style="font-size:0.85rem;color:#64748b;margin-bottom:0.9rem;line-height:1.6;">
                        {p['descricao']}
                    </div>
                    """, unsafe_allow_html=True)

                    if p.get("decisor"):
                        cargo = p.get("cargo_decisor","")
                        st.markdown(f"""<div style="display:inline-block; margin-bottom:0.5rem;
                                    background:rgba(139,92,246,0.08); border:1px solid rgba(139,92,246,0.2);
                                    border-radius:8px; padding:0.35rem 0.75rem;
                                    font-size:0.82rem; color:#a78bfa; font-weight:500;">
                                    👤 {p['decisor']}{" — " + cargo if cargo else ""}
                                </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='font-size:0.78rem;color:#1e2235;'>👤 Decisor não identificado</div>", unsafe_allow_html=True)

                    if p.get("email"):
                        conf = f" · {p['email_score']}% conf." if p.get("email_score") else ""
                        st.markdown(f"""<div style="display:inline-block; margin-top:0.4rem;
                                    background:rgba(6,182,212,0.08); border:1px solid rgba(6,182,212,0.2);
                                    border-radius:8px; padding:0.35rem 0.75rem;
                                    font-size:0.82rem; color:#22d3ee; font-weight:500;">
                                    📧 {p['email']}{conf}
                                </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='font-size:0.78rem;color:#1e2235;margin-top:0.35rem;'>📧 Email não encontrado</div>", unsafe_allow_html=True)

                with right:
                    st.markdown("<div style='font-size:0.65rem;font-weight:800;letter-spacing:0.12em;color:#334155;text-transform:uppercase;margin-bottom:0.6rem;'>Mensagens</div>", unsafe_allow_html=True)

                    mensagens = p.get("mensagens", [p.get("mensagem","")])
                    labels = ["🎯 Problema", "✨ Benefício", "⚡ Direto"][:len(mensagens)]
                    tabs = st.tabs(labels)

                    for j, (tab, msg) in enumerate(zip(tabs, mensagens)):
                        with tab:
                            msg_edit = st.text_area("msg", value=msg, height=115,
                                                     key=f"msg_{i}_{j}", label_visibility="collapsed")

                            # Email sending — opcional
                            if p.get("email") and can_send and not already_sent:
                                assunto = st.text_input("Assunto", value=f"Uma ideia para {p['empresa']}",
                                                         key=f"subj_{i}_{j}", label_visibility="collapsed")
                                if st.button(f"📤 Enviar para {p['email']}", key=f"send_{i}_{j}", type="primary"):
                                    try:
                                        send_email(p["email"], assunto, msg_edit, config)
                                        mark_sent(user_id, p["website"], p["email"])
                                        st.success("Enviado!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(str(e))
                            elif already_sent:
                                st.success("✅ Email já enviado")
                            else:
                                # Dica discreta, não bloqueia
                                with st.expander("📧 Enviar por email (opcional)", expanded=False):
                                    if not p.get("email"):
                                        st.caption("Configure Hunter.io na sidebar para encontrar o email do decisor.")
                                    if not can_send:
                                        st.caption("Configure Gmail na sidebar para enviar direto pelo app.")

        # ── Export ────────────────────────────────────────────────────────────

        st.divider()
        approved_list = [p for i, p in enumerate(prospects) if st.session_state["approved"].get(i, True)]

        if approved_list:
            df = pd.DataFrame(approved_list)
            buf = io.StringIO()
            df.to_csv(buf, index=False, encoding="utf-8-sig")

            c_dl, c_info = st.columns([1, 3])
            with c_dl:
                st.download_button(
                    f"⬇️ Exportar CSV ({len(approved_list)})",
                    data=buf.getvalue(), file_name="prospects.csv",
                    mime="text/csv", use_container_width=True,
                )
            with c_info:
                st.markdown(f"<p style='color:#1e2235;font-size:0.8rem;padding-top:0.7rem;'>{len(approved_list)} prospect(s) aprovado(s) · pronto para importar no seu CRM</p>", unsafe_allow_html=True)
        else:
            st.warning("Marque ao menos um prospect para exportar.")


# ── Router ────────────────────────────────────────────────────────────────────

if st.session_state.get("logged_in"):
    show_app()
else:
    show_login()
