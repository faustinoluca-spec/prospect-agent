-- ============================================================
-- AI Prospector — Supabase Schema
-- Cole este SQL no Supabase: SQL Editor → New query → Run
-- ============================================================

-- Tabela de configurações por usuário
CREATE TABLE IF NOT EXISTS user_configs (
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    display_name TEXT DEFAULT '',
    gmail       TEXT DEFAULT '',
    gmail_app_password TEXT DEFAULT '',
    hunter_api_key     TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela de prospects já visitados (histórico por usuário)
CREATE TABLE IF NOT EXISTS visited_prospects (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    website     TEXT NOT NULL,
    email       TEXT,
    visited_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para busca rápida por usuário
CREATE INDEX IF NOT EXISTS idx_visited_user_id ON visited_prospects(user_id);
CREATE INDEX IF NOT EXISTS idx_visited_website  ON visited_prospects(user_id, website);

-- ── Row Level Security (cada usuário vê só seus dados) ──────────────────────

ALTER TABLE user_configs       ENABLE ROW LEVEL SECURITY;
ALTER TABLE visited_prospects  ENABLE ROW LEVEL SECURITY;

-- user_configs: cada usuário acessa apenas o próprio registro
CREATE POLICY "user_configs: own row only" ON user_configs
    FOR ALL USING (auth.uid() = user_id);

-- visited_prospects: cada usuário acessa apenas seus próprios prospects
CREATE POLICY "visited_prospects: own rows only" ON visited_prospects
    FOR ALL USING (auth.uid() = user_id);
