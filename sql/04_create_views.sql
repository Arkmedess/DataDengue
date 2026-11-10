-- ============================================================================
-- PROJETO INTEGRADOR FATEC - DESAFIO DE DADOS / BUSINESS INTELLIGENCE
-- VIEWS ANALÍTICAS DO DATA WAREHOUSE (STAR SCHEMA)
-- ============================================================================
-- Views prontas para inspeção no JetBrains DataGrip, consultas rápidas
-- e conexão direta no Power BI Desktop.
-- ============================================================================

-- 1. VIEW CONSOLIDADA: STAR SCHEMA COMPLETO (DENORMALIZED ANALYTICAL VIEW)
-- Permite visualizar todas as métricas da Fato enriquecidas com os atributos
-- das 5 dimensões em uma única tabela virtual no DataGrip.
CREATE VIEW IF NOT EXISTS vw_star_schema_completo AS
SELECT 
    f.sk_fato,
    -- Dimensão Tempo
    t.sk_tempo,
    t.data_inicio_semana,
    t.semana_ano,
    t.semana_epidem,
    t.ano_epidem,
    t.ano,
    t.mes,
    t.nome_mes,
    t.trimestre,
    t.estacao_ano,
    -- Dimensão Doença
    d.nome_doenca,
    d.codigo_cid10,
    d.vetor_transmissor,
    -- Dimensão Município
    m.nome_municipio,
    m.uf,
    m.populacao,
    m.faixa_populacional,
    -- Dimensão Alerta
    a.nivel_alerta,
    a.status_alerta_nome,
    a.cor_indicativa,
    a.descricao_risco,
    a.acao_preventiva_recomendada,
    -- Dimensão Clima
    c.faixa_temperatura,
    c.faixa_umidade,
    c.condicao_receptividade,
    c.risco_clima_proliferacao,
    -- Fatos e Métricas
    f.casos_notificados,
    f.casos_estimados,
    f.diferenca_nowcasting,
    f.casos_confirmados,
    f.casos_provaveis,
    f.incidencia_por_100k,
    f.taxa_rt,
    f.probabilidade_rt_maior_1,
    f.temp_media_semana,
    f.umid_media_semana,
    f.notif_acumuladas_ano
FROM fato_casos_dengue f
JOIN dim_tempo t ON f.sk_tempo = t.sk_tempo
JOIN dim_doenca d ON f.sk_doenca = d.sk_doenca
JOIN dim_municipio m ON f.sk_municipio = m.sk_municipio
JOIN dim_alerta a ON f.sk_alerta = a.sk_alerta
JOIN dim_clima c ON f.sk_clima = c.sk_clima;

-- 2. VIEW DE SAZONALIDADE: IMPACTO MENSAL E POR ESTAÇÃO DO ANO
CREATE VIEW IF NOT EXISTS vw_sazonalidade_mensal AS
SELECT 
    t.ano,
    t.estacao_ano,
    t.nome_mes,
    t.mes,
    d.nome_doenca,
    COUNT(f.sk_fato) AS total_semanas,
    SUM(f.casos_notificados) AS total_casos_reais,
    ROUND(SUM(f.casos_estimados), 0) AS total_casos_estimados,
    ROUND(AVG(f.incidencia_por_100k), 1) AS incidencia_media_100k,
    ROUND(AVG(f.temp_media_semana), 1) AS temp_media_celsius,
    ROUND(AVG(f.umid_media_semana), 1) AS umidade_media_pct
FROM fato_casos_dengue f
JOIN dim_tempo t ON f.sk_tempo = t.sk_tempo
JOIN dim_doenca d ON f.sk_doenca = d.sk_doenca
GROUP BY t.ano, t.estacao_ano, t.nome_mes, t.mes, d.nome_doenca;

-- 3. VIEW DE CORRELAÇÃO CLIMÁTICA: TEMPERATURA E UMIDADE VS. TRANSMISSÃO
CREATE VIEW IF NOT EXISTS vw_correlacao_clima_casos AS
SELECT 
    d.nome_doenca,
    c.faixa_temperatura,
    c.faixa_umidade,
    c.risco_clima_proliferacao,
    COUNT(f.sk_fato) AS semanas_registradas,
    SUM(f.casos_notificados) AS volume_casos,
    ROUND(AVG(f.casos_notificados), 1) AS media_casos_semana,
    ROUND(AVG(f.taxa_rt), 2) AS rt_medio_observado
FROM fato_casos_dengue f
JOIN dim_clima c ON f.sk_clima = c.sk_clima
JOIN dim_doenca d ON f.sk_doenca = d.sk_doenca
GROUP BY d.nome_doenca, c.faixa_temperatura, c.faixa_umidade, c.risco_clima_proliferacao;

-- 4. VIEW DE ALERTAS EPIDEMIOLÓGICOS CRÍTICOS (NÍVEIS LARANJA E VERMELHO)
CREATE VIEW IF NOT EXISTS vw_alertas_criticos AS
SELECT 
    t.data_inicio_semana,
    t.semana_ano,
    d.nome_doenca,
    a.status_alerta_nome AS alerta,
    f.casos_notificados,
    f.casos_estimados,
    f.incidencia_por_100k,
    f.taxa_rt,
    c.faixa_temperatura,
    a.acao_preventiva_recomendada
FROM fato_casos_dengue f
JOIN dim_tempo t ON f.sk_tempo = t.sk_tempo
JOIN dim_doenca d ON f.sk_doenca = d.sk_doenca
JOIN dim_alerta a ON f.sk_alerta = a.sk_alerta
JOIN dim_clima c ON f.sk_clima = c.sk_clima
WHERE a.nivel_alerta >= 3
ORDER BY f.incidencia_por_100k DESC;
