-- ============================================================================
-- PROJETO INTEGRADOR FATEC - DESAFIO DE DADOS / BUSINESS INTELLIGENCE
-- QUERIES ANALÍTICAS DE NEGÓCIO - POSTGRESQL (SCHEMA: dw)
-- ============================================================================

-- 1. VISÃO EXECUTIVA GERAL POR MUNICÍPIO E DOENÇA
SELECT 
    m.nome_municipio,
    d.nome_doenca,
    m.populacao,
    SUM(f.casos_notificados) AS total_casos_reais,
    ROUND(CAST(SUM(f.casos_estimados) AS NUMERIC), 0) AS total_casos_estimados_nowcasting,
    ROUND(CAST(SUM(f.diferenca_nowcasting) AS NUMERIC), 0) AS diferenca_atraso_notificacao,
    ROUND(CAST(AVG(f.incidencia_por_100k) AS NUMERIC), 2) AS media_incidencia_100k,
    ROUND(CAST(AVG(f.taxa_rt) AS NUMERIC), 2) AS rt_medio_periodo
FROM dw.fato_casos_dengue f
JOIN dw.dim_municipio m ON f.sk_municipio = m.sk_municipio
JOIN dw.dim_doenca d ON f.sk_doenca = d.sk_doenca
GROUP BY m.nome_municipio, d.nome_doenca, m.populacao;

-- 2. SAZONALIDADE: IMPACTO DAS ESTAÇÕES DO ANO E MESES NO NÚMERO DE CASOS
SELECT 
    t.estacao_ano,
    t.nome_mes,
    d.nome_doenca,
    COUNT(f.sk_fato) AS semanas_monitoradas,
    SUM(f.casos_notificados) AS total_casos,
    ROUND(CAST(AVG(f.temp_media_semana) AS NUMERIC), 1) AS temp_media_celsius,
    ROUND(CAST(AVG(f.umid_media_semana) AS NUMERIC), 1) AS umidade_media_pct
FROM dw.fato_casos_dengue f
JOIN dw.dim_tempo t ON f.sk_tempo = t.sk_tempo
JOIN dw.dim_doenca d ON f.sk_doenca = d.sk_doenca
GROUP BY t.estacao_ano, t.nome_mes, t.mes, d.nome_doenca
ORDER BY t.mes;

-- 3. DISTRIBUIÇÃO E IMPACTO POR NÍVEL DE ALERTA EPIDEMIOLÓGICO
SELECT 
    a.nivel_alerta,
    a.status_alerta_nome,
    COUNT(f.sk_fato) AS quantidade_semanas,
    SUM(f.casos_notificados) AS volume_casos_notificados,
    ROUND(CAST(AVG(f.incidencia_por_100k) AS NUMERIC), 2) AS incidencia_media_100k,
    ROUND(CAST(AVG(f.taxa_rt) AS NUMERIC), 2) AS rt_medio
FROM dw.fato_casos_dengue f
JOIN dw.dim_alerta a ON f.sk_alerta = a.sk_alerta
GROUP BY a.nivel_alerta, a.status_alerta_nome
ORDER BY a.nivel_alerta;
