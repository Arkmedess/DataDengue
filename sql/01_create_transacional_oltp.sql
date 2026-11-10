-- ============================================================================
-- PROJETO INTEGRADOR FATEC - DESAFIO DE DADOS / BUSINESS INTELLIGENCE
-- MODELO RELACIONAL TRANSACIONAL (OLTP) - POSTGRESQL (SCHEMA: oltp)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS oltp;

-- 1. TABELA DE MUNICÍPIOS
CREATE TABLE IF NOT EXISTS oltp.tb_municipio (
    id_municipio INTEGER PRIMARY KEY,           -- Código IBGE / Geocode
    nome_municipio VARCHAR(100) NOT NULL,
    uf VARCHAR(2) NOT NULL DEFAULT 'SP',
    populacao INTEGER NOT NULL
);

-- 2. TABELA DE UNIDADES NOTIFICADORAS / PONTOS DE VIGILÂNCIA
CREATE TABLE IF NOT EXISTS oltp.tb_unidade_notificadora (
    id_unidade SERIAL PRIMARY KEY,
    id_municipio INTEGER NOT NULL,
    nome_unidade VARCHAR(120) NOT NULL,
    tipo_unidade VARCHAR(50) NOT NULL,          -- UBS, UPA, Hospital Municipal, Vigilância Zoonoses
    bairro VARCHAR(100) NOT NULL,
    FOREIGN KEY (id_municipio) REFERENCES oltp.tb_municipio(id_municipio)
);

-- 3. TABELA TRANSACIONAL DE NOTIFICAÇÕES SEMANAIS DE CASOS
CREATE TABLE IF NOT EXISTS oltp.tb_notificacao_dengue (
    id_notificacao SERIAL PRIMARY KEY,
    id_municipio INTEGER NOT NULL,
    doenca VARCHAR(30) NOT NULL DEFAULT 'dengue', -- dengue, chikungunya, zika
    data_inicio_semana DATE NOT NULL,
    semana_ano INTEGER NOT NULL,                -- Formato YYYYWW (ex.: 202501)
    semana_epidem INTEGER NOT NULL,             -- 1 a 53
    ano_epidem INTEGER NOT NULL,                -- Ano epidemiológico
    casos_notificados INTEGER NOT NULL DEFAULT 0,
    casos_estimados DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- Nowcasting Fiocruz
    casos_confirmados INTEGER NOT NULL DEFAULT 0,
    casos_provaveis INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (id_municipio) REFERENCES oltp.tb_municipio(id_municipio),
    CONSTRAINT uq_notificacao_municipio_semana_doenca UNIQUE (id_municipio, semana_ano, doenca)
);

-- 4. TABELA TRANSACIONAL DE MONITORAMENTO CLIMÁTICO
CREATE TABLE IF NOT EXISTS oltp.tb_monitoramento_climatico (
    id_clima SERIAL PRIMARY KEY,
    id_municipio INTEGER NOT NULL,
    data_inicio_semana DATE NOT NULL,
    semana_ano INTEGER NOT NULL,
    temp_min DOUBLE PRECISION,
    temp_med DOUBLE PRECISION,
    temp_max DOUBLE PRECISION,
    umid_min DOUBLE PRECISION,
    umid_med DOUBLE PRECISION,
    umid_max DOUBLE PRECISION,
    receptivo_ambiental INTEGER DEFAULT 0,      -- 0: desfavorável, 1..3: favorável à proliferação
    FOREIGN KEY (id_municipio) REFERENCES oltp.tb_municipio(id_municipio),
    CONSTRAINT uq_clima_municipio_semana UNIQUE (id_municipio, semana_ano)
);

-- 5. TABELA DE AVALIAÇÃO DE RISCO E ALERTA EPIDEMIOLÓGICO
CREATE TABLE IF NOT EXISTS oltp.tb_alerta_epidemiologico (
    id_alerta SERIAL PRIMARY KEY,
    id_municipio INTEGER NOT NULL,
    doenca VARCHAR(30) NOT NULL DEFAULT 'dengue',
    data_inicio_semana DATE NOT NULL,
    semana_ano INTEGER NOT NULL,
    nivel_alerta INTEGER NOT NULL,              -- 1: Verde, 2: Amarelo, 3: Laranja, 4: Vermelho
    rt DOUBLE PRECISION,                        -- Número reprodutivo efetivo
    p_rt1 DOUBLE PRECISION,                     -- Probabilidade de Rt > 1
    incidencia_100k DOUBLE PRECISION,           -- Casos por 100k habitantes
    transmissao_sustentada INTEGER DEFAULT 0,   -- 0: não, 1: possível, 2: provável, 3: altamente provável
    notif_acumuladas_ano INTEGER DEFAULT 0,
    FOREIGN KEY (id_municipio) REFERENCES oltp.tb_municipio(id_municipio),
    CONSTRAINT uq_alerta_municipio_semana_doenca UNIQUE (id_municipio, semana_ano, doenca)
);

-- ============================================================================
-- ÍNDICES DE PERFORMANCE
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_notif_semana_doenca ON oltp.tb_notificacao_dengue(semana_ano, doenca);
CREATE INDEX IF NOT EXISTS idx_clima_semana ON oltp.tb_monitoramento_climatico(semana_ano);
CREATE INDEX IF NOT EXISTS idx_alerta_semana_doenca ON oltp.tb_alerta_epidemiologico(semana_ano, doenca);
