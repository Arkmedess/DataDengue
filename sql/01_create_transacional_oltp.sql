-- ============================================================================
-- PROJETO INTEGRADOR FATEC - DESAFIO DE DADOS / BUSINESS INTELLIGENCE
-- MODELO RELACIONAL TRANSACIONAL (OLTP) - VIGILÂNCIA EPIDEMIOLÓGICA (DENGUE)
-- ============================================================================
-- Este script define a estrutura relacional normalizada em Terceira Forma Normal (3FN),
-- registrando as operações de monitoramento municipal, unidades de notificação,
-- dados climáticos observados e alertas sanitários semanais.
-- Compatível com: SQLite, PostgreSQL, MySQL e SQL Server.
-- ============================================================================

-- 1. TABELA DE MUNICÍPIOS
CREATE TABLE IF NOT EXISTS tb_municipio (
    id_municipio INTEGER PRIMARY KEY,           -- Código IBGE / Geocode
    nome_municipio VARCHAR(100) NOT NULL,
    uf VARCHAR(2) NOT NULL DEFAULT 'SP',
    populacao INTEGER NOT NULL
);

-- 2. TABELA DE UNIDADES NOTIFICADORAS / PONTOS DE VIGILÂNCIA
CREATE TABLE IF NOT EXISTS tb_unidade_notificadora (
    id_unidade INTEGER PRIMARY KEY AUTOINCREMENT,
    id_municipio INTEGER NOT NULL,
    nome_unidade VARCHAR(120) NOT NULL,
    tipo_unidade VARCHAR(50) NOT NULL,          -- UBS, UPA, Hospital Municipal, Vigilância Zoonoses
    bairro VARCHAR(100) NOT NULL,
    FOREIGN KEY (id_municipio) REFERENCES tb_municipio(id_municipio)
);

-- 3. TABELA TRANSACIONAL DE NOTIFICAÇÕES SEMANAIS DE CASOS
CREATE TABLE IF NOT EXISTS tb_notificacao_dengue (
    id_notificacao INTEGER PRIMARY KEY AUTOINCREMENT,
    id_municipio INTEGER NOT NULL,
    data_inicio_semana DATE NOT NULL,
    semana_ano INTEGER NOT NULL,                -- Formato YYYYWW (ex.: 202501)
    semana_epidem INTEGER NOT NULL,             -- 1 a 53
    ano_epidem INTEGER NOT NULL,                -- Ano epidemiológico
    casos_notificados INTEGER NOT NULL DEFAULT 0,
    casos_estimados REAL NOT NULL DEFAULT 0.0,  -- Nowcasting Fiocruz
    casos_confirmados INTEGER NOT NULL DEFAULT 0,
    casos_provaveis INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (id_municipio) REFERENCES tb_municipio(id_municipio),
    CONSTRAINT uq_notificacao_municipio_semana UNIQUE (id_municipio, semana_ano)
);

-- 4. TABELA TRANSACIONAL DE MONITORAMENTO CLIMÁTICO
CREATE TABLE IF NOT EXISTS tb_monitoramento_climatico (
    id_clima INTEGER PRIMARY KEY AUTOINCREMENT,
    id_municipio INTEGER NOT NULL,
    data_inicio_semana DATE NOT NULL,
    semana_ano INTEGER NOT NULL,
    temp_min REAL,
    temp_med REAL,
    temp_max REAL,
    umid_min REAL,
    umid_med REAL,
    umid_max REAL,
    receptivo_ambiental INTEGER DEFAULT 0,      -- 0: desfavorável, 1..3: favorável à proliferação
    FOREIGN KEY (id_municipio) REFERENCES tb_municipio(id_municipio),
    CONSTRAINT uq_clima_municipio_semana UNIQUE (id_municipio, semana_ano)
);

-- 5. TABELA DE AVALIAÇÃO DE RISCO E ALERTA EPIDEMIOLÓGICO
CREATE TABLE IF NOT EXISTS tb_alerta_epidemiologico (
    id_alerta INTEGER PRIMARY KEY AUTOINCREMENT,
    id_municipio INTEGER NOT NULL,
    data_inicio_semana DATE NOT NULL,
    semana_ano INTEGER NOT NULL,
    nivel_alerta INTEGER NOT NULL,              -- 1: Verde, 2: Amarelo, 3: Laranja, 4: Vermelho
    rt REAL,                                    -- Número reprodutivo efetivo
    p_rt1 REAL,                                 -- Probabilidade de Rt > 1
    incidencia_100k REAL,                       -- Casos por 100k habitantes
    transmissao_sustentada INTEGER DEFAULT 0,   -- 0: não, 1: possível, 2: provável, 3: altamente provável
    notif_acumuladas_ano INTEGER DEFAULT 0,
    FOREIGN KEY (id_municipio) REFERENCES tb_municipio(id_municipio),
    CONSTRAINT uq_alerta_municipio_semana UNIQUE (id_municipio, semana_ano)
);

-- ============================================================================
-- ÍNDICES DE PERFORMANCE PARA AS CHAVES ESTRANGEIRAS E BUSCAS CRONOLÓGICAS
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_notif_semana ON tb_notificacao_dengue(semana_ano);
CREATE INDEX IF NOT EXISTS idx_clima_semana ON tb_monitoramento_climatico(semana_ano);
CREATE INDEX IF NOT EXISTS idx_alerta_semana ON tb_alerta_epidemiologico(semana_ano);
