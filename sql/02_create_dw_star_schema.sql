-- ============================================================================
-- PROJETO INTEGRADOR FATEC - DESAFIO DE DADOS / BUSINESS INTELLIGENCE
-- MODELO DIMENSIONAL (STAR SCHEMA / OLAP) - DATA WAREHOUSE ARBOVIROSES
-- ============================================================================
-- Estrutura em esquema estrela contendo uma Tabela Fato central cercada por
-- Dimensões ricas e desnormalizadas com Surrogate Keys (SK).
-- Suporta monitoramento integrado de Dengue, Chikungunya e Zika.
-- ============================================================================

-- 1. DIMENSÃO TEMPO EPIDEMIOLÓGICO
CREATE TABLE IF NOT EXISTS dim_tempo (
    sk_tempo INTEGER PRIMARY KEY,               -- Formato numérico YYYYMMDD (ex: 20250112)
    data_inicio_semana DATE NOT NULL,
    semana_epidem INTEGER NOT NULL,             -- 1 a 53
    ano_epidem INTEGER NOT NULL,                -- 2024, 2025, etc.
    semana_ano INTEGER NOT NULL,                -- 202501, 202502
    mes INTEGER NOT NULL,                       -- 1 a 12
    nome_mes VARCHAR(20) NOT NULL,              -- Janeiro, Fevereiro...
    ano INTEGER NOT NULL,
    trimestre INTEGER NOT NULL,                 -- 1 a 4
    ano_mes VARCHAR(7) NOT NULL,                -- 2025-01
    quinzena INTEGER NOT NULL,                  -- 1 ou 2
    estacao_ano VARCHAR(20) NOT NULL            -- Verão, Outono, Inverno, Primavera
);

-- 2. DIMENSÃO MUNICÍPIO
CREATE TABLE IF NOT EXISTS dim_municipio (
    sk_municipio INTEGER PRIMARY KEY,           -- Surrogate Key
    geocode INTEGER NOT NULL,                   -- Código IBGE
    nome_municipio VARCHAR(100) NOT NULL,
    uf VARCHAR(2) NOT NULL,
    populacao INTEGER NOT NULL,
    faixa_populacional VARCHAR(50) NOT NULL     -- Ex: 'Médio-Grande Porte (100k a 500k)'
);

-- 3. DIMENSÃO NÍVEL DE ALERTA EPIDEMIOLÓGICO
CREATE TABLE IF NOT EXISTS dim_alerta (
    sk_alerta INTEGER PRIMARY KEY,              -- Surrogate Key (1 a 4)
    nivel_alerta INTEGER NOT NULL,              -- 1, 2, 3, 4
    status_alerta_nome VARCHAR(30) NOT NULL,    -- Verde, Amarelo, Laranja, Vermelho
    cor_indicativa VARCHAR(20) NOT NULL,        -- Hex / Emoji (#2CA02C, #FFD700, #FFA500, #FF4B4B)
    descricao_risco VARCHAR(150) NOT NULL,      -- Descrição clínica/epidemiológica
    acao_preventiva_recomendada VARCHAR(250) NOT NULL -- Recomendação de saúde pública
);

-- 4. DIMENSÃO CONDICIONANTES CLIMÁTICOS
CREATE TABLE IF NOT EXISTS dim_clima (
    sk_clima INTEGER PRIMARY KEY,               -- Surrogate Key
    faixa_temperatura VARCHAR(50) NOT NULL,     -- Fria (<18°C), Agradável (18-24°C), Favorável (24-28°C), Alta (>28°C)
    faixa_umidade VARCHAR(50) NOT NULL,         -- Baixa (<60%), Ideal Vetorial (60-80%), Alta (>80%)
    condicao_receptividade VARCHAR(80) NOT NULL,-- Desfavorável, Transmissão Inicial, Surto Sustentado
    risco_clima_proliferacao VARCHAR(50) NOT NULL -- Baixo, Moderado, Crítico
);

-- 5. DIMENSÃO DOENÇA / AGRAVO
CREATE TABLE IF NOT EXISTS dim_doenca (
    sk_doenca INTEGER PRIMARY KEY,              -- 1: Dengue, 2: Chikungunya, 3: Zika
    nome_doenca VARCHAR(50) NOT NULL,
    codigo_cid10 VARCHAR(10) NOT NULL,
    vetor_transmissor VARCHAR(80) NOT NULL,
    descricao_clinica VARCHAR(200) NOT NULL
);

-- 6. TABELA FATO: MONITORAMENTO E INCIDÊNCIA DE ARBOVIROSES
CREATE TABLE IF NOT EXISTS fato_casos_dengue (
    sk_fato INTEGER PRIMARY KEY AUTOINCREMENT,
    sk_tempo INTEGER NOT NULL,
    sk_municipio INTEGER NOT NULL,
    sk_alerta INTEGER NOT NULL,
    sk_clima INTEGER NOT NULL,
    sk_doenca INTEGER NOT NULL DEFAULT 1,

    -- Métricas e Fatos Aditivos / Semi-aditivos
    casos_notificados INTEGER NOT NULL DEFAULT 0,
    casos_estimados REAL NOT NULL DEFAULT 0.0,
    diferenca_nowcasting REAL NOT NULL DEFAULT 0.0, -- (casos_est - casos) = atraso/subnotificação estimada
    casos_confirmados INTEGER NOT NULL DEFAULT 0,
    casos_provaveis INTEGER NOT NULL DEFAULT 0,
    incidencia_por_100k REAL NOT NULL DEFAULT 0.0,
    taxa_rt REAL,                                   -- Ritmo de contágio (Rt)
    probabilidade_rt_maior_1 REAL,
    temp_media_semana REAL,
    umid_media_semana REAL,
    notif_acumuladas_ano INTEGER NOT NULL DEFAULT 0,

    FOREIGN KEY (sk_tempo) REFERENCES dim_tempo(sk_tempo),
    FOREIGN KEY (sk_municipio) REFERENCES dim_municipio(sk_municipio),
    FOREIGN KEY (sk_alerta) REFERENCES dim_alerta(sk_alerta),
    FOREIGN KEY (sk_clima) REFERENCES dim_clima(sk_clima),
    FOREIGN KEY (sk_doenca) REFERENCES dim_doenca(sk_doenca),
    CONSTRAINT uq_fato_registro UNIQUE (sk_tempo, sk_municipio, sk_doenca)
);

-- ============================================================================
-- ÍNDICES PARA RELACIONAMENTOS DIMENSIONAIS NO POWER BI / SQL DW
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_fato_sk_tempo ON fato_casos_dengue(sk_tempo);
CREATE INDEX IF NOT EXISTS idx_fato_sk_municipio ON fato_casos_dengue(sk_municipio);
CREATE INDEX IF NOT EXISTS idx_fato_sk_alerta ON fato_casos_dengue(sk_alerta);
CREATE INDEX IF NOT EXISTS idx_fato_sk_clima ON fato_casos_dengue(sk_clima);
CREATE INDEX IF NOT EXISTS idx_fato_sk_doenca ON fato_casos_dengue(sk_doenca);
