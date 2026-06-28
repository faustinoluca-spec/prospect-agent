import os
import json
import re
import requests
from typing import TypedDict, List, Dict, Optional
from dotenv import load_dotenv
from groq import Groq
from langgraph.graph import StateGraph, END
from bs4 import BeautifulSoup
from email_sender import find_email

load_dotenv()

import streamlit as st

def _secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key)

GROQ_API_KEY   = _secret("GROQ_API_KEY")
SERPER_API_KEY = _secret("SERPER_API_KEY")
MODEL = "llama-3.3-70b-versatile"
MIN_PROSPECTS = 5
MAX_ATTEMPTS = 3

client = Groq(api_key=GROQ_API_KEY)

VISITED_FILE = "visited_prospects.json"

# Domínios que não são sites reais de empresas
BLOCKED_DOMAINS = {
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com",
    "crunchbase.com", "glassdoor.com", "indeed.com", "reclameaqui.com.br",
    "catho.com.br", "infojobs.com.br", "vagas.com.br", "gupy.io",
}

def is_company_website(url: str) -> bool:
    """Retorna False se a URL for de um diretório/rede social, não do site da empresa."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower().replace("www.", "")
    return not any(blocked in domain for blocked in BLOCKED_DOMAINS)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_visited() -> set:
    if os.path.exists(VISITED_FILE):
        with open(VISITED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_visited(visited: set):
    with open(VISITED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(visited), f)


def parse_json(text: str):
    text = text.strip()
    if "```" in text:
        for part in text.split("```"):
            part = part.strip().lstrip("json").strip()
            try:
                return json.loads(part)
            except Exception:
                continue
    return json.loads(text)


def scrape_website(url: str) -> str:
    """Retorna texto limpo da homepage (máx 2000 chars). Retorna '' em caso de erro."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return text[:2000]
    except Exception:
        return ""


def serper_search(query: str, num: int = 5) -> List[Dict]:
    payload = json.dumps({"q": query, "num": num, "gl": "br", "hl": "pt"})
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    resp = requests.post("https://google.serper.dev/search", headers=headers, data=payload)
    return resp.json().get("organic", [])


# ── Estado ────────────────────────────────────────────────────────────────────

class ProspectorState(TypedDict):
    icp: str
    attempts: int
    previous_queries: List[str]
    queries: List[str]
    raw_results: List[Dict]
    qualified_companies: List[Dict]
    enriched_companies: List[Dict]
    final_prospects: List[Dict]
    hunter_api_key: Optional[str]
    # Debug
    debug_blocked_urls: List[str]
    debug_all_queries: List[str]


# ── Nós ───────────────────────────────────────────────────────────────────────

def generate_queries(state: ProspectorState) -> dict:
    icp = state["icp"]
    previous = state.get("previous_queries", [])
    attempt = state.get("attempts", 0) + 1

    avoid_clause = ""
    if previous:
        avoid_clause = f"\n\nNão repita estas queries já usadas:\n" + "\n".join(f"- {q}" for q in previous)

    prompt = f"""Você é especialista em prospecção B2B. Esta é a tentativa {attempt} de {MAX_ATTEMPTS}.

Perfil de cliente ideal (ICP):
{icp}

Gere 5 queries de busca no Google para encontrar empresas reais que se encaixam nesse perfil.
Foque em queries que retornem sites de empresas específicas, não artigos ou diretórios.
Varie os ângulos: use diferentes combinações de setor, localização, tamanho, tecnologia.{avoid_clause}

Responda APENAS com JSON array de strings:
["query 1", "query 2", "query 3", "query 4", "query 5"]"""

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
    )
    queries = parse_json(resp.choices[0].message.content)
    all_previous = previous + queries
    all_queries = state.get("debug_all_queries", []) + queries
    return {"queries": queries, "previous_queries": all_previous, "attempts": attempt, "debug_all_queries": all_queries}


def search_web(state: ProspectorState) -> dict:
    visited = load_visited()
    seen_urls = set()
    all_results = []

    for query in state["queries"]:
        for result in serper_search(query, num=6):
            url = result.get("link", "")
            if url and url not in seen_urls and url not in visited:
                seen_urls.add(url)
                all_results.append({
                    "title": result.get("title", ""),
                    "link": url,
                    "snippet": result.get("snippet", ""),
                })

    # Merge com resultados de tentativas anteriores
    existing = state.get("raw_results", [])
    existing_urls = {r["link"] for r in existing}
    merged = existing + [r for r in all_results if r["link"] not in existing_urls]
    return {"raw_results": merged}


def qualify_results(state: ProspectorState) -> dict:
    icp = state["icp"]
    visited = load_visited()

    already_qualified_urls = {c["website"] for c in state.get("qualified_companies", [])}
    candidates = [
        r for r in state["raw_results"]
        if r["link"] not in visited and r["link"] not in already_qualified_urls
    ]

    if not candidates:
        return {}

    results_text = "\n".join([
        f"[{i+1}] Título: {r['title']}\n    URL: {r['link']}\n    Descrição: {r['snippet']}"
        for i, r in enumerate(candidates)
    ])

    prompt = f"""Você é analista de prospecção B2B experiente.

ICP:
{icp}

Resultados de busca:
{results_text}

Identifique APENAS empresas reais que se encaixam no ICP.
Exclua: artigos, blogs, diretórios, listas de comparação, notícias, SaaS genérico que não é o cliente-alvo.
IMPORTANTE: o campo "website" deve ser o site próprio da empresa (ex: empresa.com.br). Nunca use URLs de LinkedIn, Crunchbase, Facebook, redes sociais ou diretórios de emprego.

Para cada empresa qualificada:
- name: nome da empresa
- website: URL completa
- description: o que fazem (1-2 frases)
- fit_score: 1-10
- fit_reason: motivo objetivo

Responda APENAS com JSON array ([] se nenhum qualificar):
[{{"name":"...","website":"...","description":"...","fit_score":8,"fit_reason":"..."}}]"""

    resp = client.chat.completions.create(
        model=MODEL,
 