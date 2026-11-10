-- ============================================================================
-- PROJETO INTEGRADOR FATEC - DESAFIO DE DADOS / BUSINESS INTELLIGENCE
-- VIEWS ANALÍTICAS DO DATA WAREHOUSE - POSTGRESQL (SCHEMA: dw)
-- ============================================================================

CREATE OR REPLACE VIEW dw.vw_star_schema_completo AS
SELECT 
    f.sk_fato,
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
    d.nome_doenca,
    d.codigo_cid10,
    d.vetor_transmissor,
    m.nome_municipio,
    m.uf,
    m.populacao,
    m.faixa_populacional,
    a.nivel_alerta,
    a.status_alerta_nome,
    a.cor_indicativa,
    a.descricao_risco,
    a.acao_preventiva_recomendada,
    c.faixa_temperatura,
    c.faixa_umidade,
    c.condicao_receptividade,
    c.risco_clima_proliferacao,
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
FROM dw.fato_casos_dengue f
JOIN dw.dim_tempo t ON f.sk_tempo = t.sk_tempo
JOIN dw.dim_doenca d ON f.sk_doenca = d.sk_doenca
JOIN dw.dim_municipio m ON f.sk_municipio = m.sk_municipio
JOIN dw.dim_alerta a ON f.sk_alerta = a.sk_alerta
JOIN dw.dim_clima c ON f.sk_clima = c.sk_clima;

CREATE OR REPLACE VIEW dw.vw_sazonalidade_mensal AS
SELECT 
    t.ano,
    t.estacao_ano,
    t.nome_mes,
    t.mes,
    d.nome_doenca,
    COUNT(f.sk_fato) AS total_semanas,
    SUM(f.casos_notificados) AS total_casos_reais,
    ROUND(CAST(SUM(f.casos_estimados) AS NUMERIC), 0) AS total_casos_estimados,
    ROUND(CAST(AVG(f.incidencia_por_100k) AS NUMERIC), 1) AS incidencia_media_100k,
    ROUND(CAST(AVG(f.temp_media_semana) AS NUMERIC), 1) AS temp_media_celsius,
    ROUND(CAST(AVG(f.umid_media_semana) AS NUMERIC), 1) AS umidade_media_pct
FROM dw.fato_casos_dengue f
JOIN dw.dim_tempo t ON f.sk_tempo = t.sk_tempo
JOIN dw.dim_doenca d ON f.sk_doenca = d.sk_doenca
GROUP BY t.ano, t.estacao_ano, t.nome_mes, t.mes, d.nome_doenca;

CREATE OR REPLACE VIEW dw.vw_correlacao_clima_casos AS
SELECT 
    d.nome_doenca,
    c.faixa_temperatura,
    c.faixa_umidade,
    c.risco_clima_proliferacao,
    COUNT(f.sk_fato) AS semanas_registradas,
    SUM(f.casos_notificados) AS volume_casos,
    ROUND(CAST(AVG(f.casos_notificados) AS NUMERIC), 1) AS media_casos_semana,
    ROUND(CAST(AVG(f.taxa_rt) AS NUMERIC), 2) AS rt_medio_observado
FROM dw.fato_casos_dengue f
JOIN dw.dim_clima c ON f.sk_clima = c.sk_clima
JOIN dw.dim_doenca d ON f.sk_doenca = d.sk_doenca
GROUP BY d.nome_doenca, c.faixa_temperatura, c.faixa_umidade, c.risco_clima_proliferacao;

CREATE OR REPLACE VIEW dw.vw_alertas_criticos AS
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
FROM dw.fato_casos_dengue f
JOIN dw.dim_tempo t ON f.sk_tempo = t.sk_tempo
JOIN dw.dim_doenca d ON f.sk_doenca = d.sk_doenca
JOIN dw.dim_alerta a ON f.sk_alerta = a.sk_alerta
JOIN dw.dim_clima c ON f.sk_clima = c.sk_clima
WHERE a.nivel_alerta >= 3
ORDER BY f.incidencia_por_100k DESC;
