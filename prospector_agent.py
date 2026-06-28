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
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    try:
        companies = parse_json(resp.choices[0].message.content)
        new_qualified = []
        newly_blocked = []
        for c in companies:
            if not isinstance(c, dict):
                continue
            if c.get("fit_score", 0) < 6:
                continue
            if not is_company_website(c.get("website", "")):
                newly_blocked.append(c.get("website", ""))
            else:
                new_qualified.append(c)
    except Exception:
        new_qualified = []
        newly_blocked = []

    existing_qualified = state.get("qualified_companies", [])
    existing_blocked = state.get("debug_blocked_urls", [])
    merged = existing_qualified + new_qualified
    blocked = existing_blocked + newly_blocked
    return {"qualified_companies": merged, "debug_blocked_urls": blocked}


def enrich_companies(state: ProspectorState) -> dict:
    """Para cada empresa: scraping real do site + busca do CEO/fundador."""
    companies = state["qualified_companies"]
    enriched = []

    for company in companies:
        # 1. Scraping real do site
        website_text = scrape_website(company["website"])

        # 2. Tentar extrair decisor do conteúdo do site (grátis, já temos o texto)
        decision_maker = None
        if website_text:
            dm_site_prompt = f"""Analise o texto abaixo da homepage da empresa "{company['name']}" e extraia o nome do CEO, fundador ou principal liderança mencionado.
Se não encontrar nenhum nome com certeza, retorne null.

Texto do site:
{website_text[:1500]}

Responda APENAS com JSON: {{"name": "Nome Completo", "role": "CEO"}} ou null"""

            dm_site_resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": dm_site_prompt}],
                temperature=0.0,
            )
            try:
                dm_raw = dm_site_resp.choices[0].message.content.strip()
                decision_maker = None if dm_raw.lower() == "null" else parse_json(dm_raw)
            except Exception:
                decision_maker = None

        # 3. Fallback: buscar decisor via Serper se não achou no site
        if not decision_maker:
            dm_results = serper_search(
                f'"{company["name"]}" CEO fundador founder diretor',
                num=5
            )
            dm_snippets = " | ".join([
                r.get("title", "") + " " + r.get("snippet", "")
                for r in dm_results
            ])
            if dm_snippets:
                dm_serper_prompt = f"""Dado os resultados abaixo, extraia o nome do CEO ou fundador da empresa "{company['name']}".
Só retorne se tiver certeza razoável. Se não encontrar, retorne null.

Resultados:
{dm_snippets}

Responda APENAS com JSON: {{"name": "Nome Completo", "role": "CEO"}} ou null"""

                dm_serper_resp = client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "user", "content": dm_serper_prompt}],
                    temperature=0.0,
                )
                try:
                    dm_raw = dm_serper_resp.choices[0].message.content.strip()
                    decision_maker = None if dm_raw.lower() == "null" else parse_json(dm_raw)
                except Exception:
                    decision_maker = None

        # 4. Buscar email via Hunter.io
        hunter_key = state.get("hunter_api_key")
        email_result = None
        if hunter_key:
            if decision_maker and decision_maker.get("name"):
                # Email finder por nome + domínio
                parts = decision_maker["name"].split(" ", 1)
                email_result = find_email(parts[0], parts[1] if len(parts) > 1 else "", company["website"], hunter_key)

            if not email_result:
                # Domain search como fallback — retorna qualquer email do domínio
                from email_sender import domain_search_email
                email_result = domain_search_email(company["website"], hunter_key)

        enriched.append({
            **company,
            "website_content": website_text,
            "decision_maker": decision_maker,
            "email_result": email_result,
        })

    return {"enriched_companies": enriched}


def write_messages(state: ProspectorState) -> dict:
    icp = state["icp"]
    companies = state["enriched_companies"]
    visited = load_visited()
    final_prospects = []

    for company in companies:
        dm = company.get("decision_maker")
        dm_info = f"Contato: {dm['name']} ({dm['role']})" if dm else "Contato: não identificado"
        website_ctx = company.get("website_content", "")
        website_block = f"\nConteúdo real do site:\n{website_ctx[:800]}" if website_ctx else ""

        prompt = f"""Você é especialista em cold outreach B2B.

Empresa: {company['name']}
Site: {company['website']}
Descrição: {company['description']}
{dm_info}{website_block}

Contexto: buscamos clientes com perfil — {icp}

Gere 3 variações de mensagem de prospecção, cada uma com um ângulo diferente:
- Variação 1: foco no problema que a empresa provavelmente enfrenta
- Variação 2: foco no resultado/benefício que você entrega
- Variação 3: tom mais direto e curto (2 linhas máximo)

Regras para todas:
- Se tiver nome do contato, dirija-se pelo primeiro nome
- Use algo específico da empresa (nunca genérico)
- CTA direto e sem pressão
- Tom humano, português brasileiro
- Proibido: "Espero que esteja bem", frases genéricas, superlativos

Responda APENAS com JSON array de 3 strings:
["mensagem 1", "mensagem 2", "mensagem 3"]"""

        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        try:
            mensagens = parse_json(resp.choices[0].message.content)
            if not isinstance(mensagens, list) or len(mensagens) < 1:
                raise ValueError
        except Exception:
            mensagens = [resp.choices[0].message.content.strip()]

        email_data = company.get("email_result")
        final_prospects.append({
            "empresa": company["name"],
            "website": company["website"],
            "descricao": company["description"],
            "fit_score": company["fit_score"],
            "motivo_fit": company["fit_reason"],
            "decisor": dm["name"] if dm else None,
            "cargo_decisor": dm["role"] if dm else None,
            "email": email_data["email"] if email_data else None,
            "email_score": email_data["score"] if email_data else None,
            "mensagens": mensagens,
        })

        visited.add(company["website"])

    save_visited(visited)
    return {"final_prospects": final_prospects}


# ── Roteamento ────────────────────────────────────────────────────────────────

def route_after_qualify(state: ProspectorState) -> str:
    qualified_count = len(state.get("qualified_companies", []))
    attempts = state.get("attempts", 0)
    if qualified_count < MIN_PROSPECTS and attempts < MAX_ATTEMPTS:
        return "generate_queries"
    return "enrich_companies"


# ── Grafo ─────────────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(ProspectorState)

    graph.add_node("generate_queries", generate_queries)
    graph.add_node("search_web", search_web)
    graph.add_node("qualify_results", qualify_results)
    graph.add_node("enrich_companies", enrich_companies)
    graph.add_node("write_messages", write_messages)

    graph.set_entry_point("generate_queries")
    graph.add_edge("generate_queries", "search_web")
    graph.add_edge("search_web", "qualify_results")
    graph.add_conditional_edges("qualify_results", route_after_qualify, {
        "generate_queries": "generate_queries",
        "enrich_companies": "enrich_companies",
    })
    graph.add_edge("enrich_companies", "write_messages")
    graph.add_edge("write_messages", END)

    return graph.compile()


prospector = build_graph()


def run_prospector(icp: str, hunter_api_key: str = None):
    """Retorna (prospects, debug_info)."""
    result = prospector.invoke({
        "icp": icp,
        "attempts": 0,
        "previous_queries": [],
        "queries": [],
        "raw_results": [],
        "qualified_companies": [],
        "enriched_companies": [],
        "final_prospects": [],
        "hunter_api_key": hunter_api_key,
        "debug_blocked_urls": [],
        "debug_all_queries": [],
    })

    debug_info = {
        "attempts": result.get("attempts", 1),
        "queries": result.get("debug_all_queries", []),
        "raw_results_count": len(result.get("raw_results", [])),
        "qualified_count": len(result.get("qualified_companies", [])),
        "blocked_urls": result.get("debug_blocked_urls", []),
        "enriched_count": len(result.get("enriched_companies", [])),
    }

    return result["final_prospects"], debug_info
