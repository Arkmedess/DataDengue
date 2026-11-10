-- ============================================================================
-- PROJETO INTEGRADOR FATEC - DESAFIO DE DADOS / BUSINESS INTELLIGENCE
-- QUERIES ANALÍTICAS DE NEGÓCIO E VALIDAÇÃO DO DATA WAREHOUSE (STAR SCHEMA)
-- ============================================================================

-- 1. VISÃO EXECUTIVA GERAL POR MUNICÍPIO: CASOS, ESTIMATIVAS E TAXA DE SUBNOTIFICAÇÃO
SELECT 
    m.nome_municipio,
    m.uf,
    m.populacao,
    SUM(f.casos_notificados) AS total_casos_reais,
    ROUND(SUM(f.casos_estimados), 0) AS total_casos_estimados_nowcasting,
    ROUND(SUM(f.diferenca_nowcasting), 0) AS diferenca_atraso_notificacao,
    ROUND(AVG(f.incidencia_por_100k), 2) AS media_incidencia_100k,
    ROUND(AVG(f.taxa_rt), 2) AS rt_medio_periodo
FROM fato_casos_dengue f
JOIN dim_municipio m ON f.sk_municipio = m.sk_municipio
GROUP BY m.nome_municipio, m.uf, m.populacao;

-- 2. SAZONALIDADE: IMPACTO DAS ESTAÇÕES DO ANO E MESES NO NÚMERO DE CASOS
SELECT 
    t.estacao_ano,
    t.nome_mes,
    COUNT(f.sk_fato) AS semanas_monitoradas,
    SUM(f.casos_notificados) AS total_casos,
    ROUND(AVG(f.temp_media_semana), 1) AS temp_media_celsius,
    ROUND(AVG(f.umid_media_semana), 1) AS umidade_media_pct
FROM fato_casos_dengue f
JOIN dim_tempo t ON f.sk_tempo = t.sk_tempo
GROUP BY t.estacao_ano, t.nome_mes, t.mes
ORDER BY t.mes;

-- 3. DISTRIBUIÇÃO E IMPACTO POR NÍVEL DE ALERTA EPIDEMIOLÓGICO
SELECT 
    a.nivel_alerta,
    a.status_alerta_nome,
    a.descricao_risco,
    COUNT(f.sk_fato) AS quantidade_semanas,
    SUM(f.casos_notificados) AS volume_casos_notificados,
    ROUND(AVG(f.incidencia_por_100k), 2) AS incidencia_media_100k,
    ROUND(AVG(f.taxa_rt), 2) AS rt_medio
FROM fato_casos_dengue f
JOIN dim_alerta a ON f.sk_alerta = a.sk_alerta
GROUP BY a.nivel_alerta, a.status_alerta_nome, a.descricao_risco
ORDER BY a.nivel_alerta;

-- 4. CORRELAÇÃO CLIMÁTICA: COMPORTAMENTO DE CASOS POR FAIXA DE TEMPERATURA E UMIDADE
SELECT 
    c.faixa_temperatura,
    c.faixa_umidade,
    c.risco_clima_proliferacao,
    COUNT(f.sk_fato) AS semanas_registradas,
    SUM(f.casos_notificados) AS total_casos,
    ROUND(AVG(f.casos_notificados), 1) AS media_casos_por_semana
FROM fato_casos_dengue f
JOIN dim_clima c ON f.sk_clima = c.sk_clima
GROUP BY c.faixa_temperatura, c.faixa_umidade, c.risco_clima_proliferacao
ORDER BY total_casos DESC;

-- 5. SEMANAS COM MAIOR RITMO DE TRANSMISSÃO SUSTENTADA (Rt > 1 E PICO DE INCIDÊNCIA)
SELECT 
    t.data_inicio_semana,
    t.semana_ano,
    f.casos_notificados,
    f.casos_estimados,
    f.incidencia_por_100k,
    f.taxa_rt,
    a.status_alerta_nome,
    c.faixa_temperatura
FROM fato_casos_dengue f
JOIN dim_tempo t ON f.sk_tempo = t.sk_tempo
JOIN dim_alerta a ON f.sk_alerta = a.sk_alerta
JOIN dim_clima c ON f.sk_clima = c.sk_clima
WHERE f.taxa_rt > 1.2
ORDER BY f.incidencia_por_100k DESC
LIMIT 10;
