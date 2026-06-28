import json
import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse

CONFIG_FILE = "config.json"
SENT_FILE = "sent_emails.json"


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"gmail": "", "gmail_app_password": "", "hunter_api_key": ""}


def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f)


def config_is_complete(config: dict) -> bool:
    return bool(config.get("gmail") and config.get("gmail_app_password"))


# ── Hunter.io ─────────────────────────────────────────────────────────────────

def find_email(first_name: str, last_name: str, website: str, hunter_api_key: str) -> dict | None:
    """Busca email verificado via Hunter.io. Retorna dict com email e score, ou None."""
    if not hunter_api_key or not first_name:
        return None

    try:
        domain = urlparse(website).netloc.replace("www.", "")
        resp = requests.get(
            "https://api.hunter.io/v2/email-finder",
            params={
                "domain": domain,
                "first_name": first_name,
                "last_name": last_name or "",
                "api_key": hunter_api_key,
            },
            timeout=8,
        )
        data = resp.json().get("data", {})
        email = data.get("email")
        score = data.get("score", 0)
        if email and score >= 50:
            return {"email": email, "score": score}
    except Exception:
        pass
    return None


def domain_search_email(website: str, hunter_api_key: str) -> dict | None:
    """Busca qualquer email verificado do domínio via Hunter.io domain search."""
    try:
        domain = urlparse(website).netloc.replace("www.", "")
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": hunter_api_key, "limit": 3},
            timeout=8,
        )
        emails = resp.json().get("data", {}).get("emails", [])
        # Pega o de maior confidence score
        emails = sorted(emails, key=lambda e: e.get("confidence", 0), reverse=True)
        if emails:
            best = emails[0]
            email = best.get("value")
            score = best.get("confidence", 0)
            if email and score >= 50:
                return {"email": email, "score": score}
    except Exception:
        pass
    return None


# ── Email sending ─────────────────────────────────────────────────────────────

def send_email(to_email: str, subject: str, body: str, config: dict) -> bool:
    """Envia email via Gmail SMTP. Retorna True se enviou com sucesso."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config["gmail"]
        msg["To"] = to_email

        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config["gmail"], config["gmail_app_password"])
            server.sendmail(config["gmail"], to_email, msg.as_string())

        return True
    except Exception as e:
        raise RuntimeError(f"Erro ao enviar email: {e}")


# ── Sent tracking ─────────────────────────────────────────────────────────────

def load_sent() -> dict:
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def mark_sent(website: str, email: str):
    sent = load_sent()
    sent[website] = {"email": email, "status": "sent"}
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sent, f)


def is_sent(website: str) -> bool:
    return website in load_sent()
