from pathlib import Path
from typing import cast

import pandas as pd
import streamlit as st

# 1. Configuração da Página (Sempre a primeira linha do Streamlit)
st.set_page_config(
    page_title="Painel InfoDengue - Jundiaí", page_icon="🦟", layout="wide"
)


# 2. Carregamento de Dados (Com cache para não travar o app)
@st.cache_data
def carregar_dados():
    # Busca o arquivo limpo na pasta data
    caminho_arquivo = (
        Path(__file__).resolve().parent.parent / "data" / "Dengue_Jundiai.csv"
    )

    if not caminho_arquivo.exists():
        st.error("Arquivo de dados não encontrado! Rode o main.py primeiro.")
        st.stop()

    df = pd.read_csv(caminho_arquivo)
    # Garante que a data seja interpretada como tempo para os gráficos
    df["data_ini_SE"] = pd.to_datetime(df["data_ini_SE"])
    return df


df = carregar_dados()

# ==========================================
# BARRA LATERAL (Filtros Interativos)
# ==========================================
st.sidebar.title("🔍 Filtros Dinâmicos")
st.sidebar.write("Use os controles abaixo para explorar os dados.")

# Interação 1: Slider de Semanas Epidemiológicas
semana_min: int = int(min(df["SE"]))
semana_max = int(max(df["SE"]))
semanas_selecionadas = st.sidebar.slider(
    "1. Selecione o período (Semanas):",
    min_value=semana_min,
    max_value=semana_max,
    value=(semana_min, semana_max),  # Seleciona tudo por padrão
)

# Interação 2: Dropdown de Múltipla Escolha para Status de Alerta
alertas_disponiveis = df["alerta_status"].unique().tolist()
alertas_selecionados = st.sidebar.multiselect(
    "2. Filtrar por Nível de Alerta:",
    options=alertas_disponiveis,
    default=alertas_disponiveis,
)

# Aplicando os filtros no DataFrame
df_filtrado = df[
    (df["SE"] >= semanas_selecionadas[0])
    & (df["SE"] <= semanas_selecionadas[1])
    & (df["alerta_status"].isin(alertas_selecionados))
]

# LAYOUT PRINCIPAL (Dashboard)
st.title("📊 Monitoramento de Dengue - Jundiaí (2026)")
st.markdown(
    "Acompanhamento de casos, estimativas e fatores climáticos com base nos dados do **InfoDengue**."
)
st.divider()

if df_filtrado.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

df_ordenado = df_filtrado.sort_values("data_ini_SE")
data_inicio = df_ordenado["data_ini_SE"].min().date()
data_fim = df_ordenado["data_ini_SE"].max().date()
total_linhas = int(df_ordenado.shape[0])

st.caption(
    f"Periodo selecionado: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')} "
    f"(SE {semanas_selecionadas[0]} - {semanas_selecionadas[1]}) | "
    f"{total_linhas} semanas exibidas"
)

# --- KPIs (Métricas de Destaque) ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_casos = df_filtrado["casos"].sum()
    st.metric("Total de Casos (Real)", f"{total_casos:,}")

with col2:
    total_estimado = df_filtrado["casos_est"].sum()
    st.metric("Total Estimado", f"{total_estimado:,.0f}")

with col3:
    if not df_filtrado.empty:
        pico_casos = int(max(df_filtrado["casos"]))

        # 1. Tipagem explícita: Avisamos ao editor que isto é uma Series do Pandas
        serie_casos: pd.Series = cast(pd.Series, df_filtrado["casos"])

        # 2. Agora o idxmax() funciona nativamente e sem alertas!
        semana_pico = df_filtrado.loc[serie_casos.idxmax(), "SE"]
    else:
        pico_casos = 0
        semana_pico = "-"

    st.metric("Pico de Casos (Semana)", f"{pico_casos} (SE: {semana_pico})")

with col4:
    if not df_filtrado.empty:
        # 1. Forçamos o editor a reconhecer a coluna como uma Series do Pandas
        serie_alerta = cast(pd.Series, df_filtrado["alerta_status"])

        # 2. Buscamos a moda. Como o .mode() retorna uma Series, extraímos o primeiro valor (.iloc[0])
        # e forçamos para string nativa usando str()
        alerta_predominante = str(serie_alerta.mode().iloc[0])
    else:
        alerta_predominante = "-"

    # Agora o st.metric recebe uma string pura (coberta pelo tipo "Value") e o erro some!
    st.metric("Alerta Predominante", alerta_predominante)

st.divider()

st.subheader("Indicadores da Ultima Semana")
col_semana_1, col_semana_2, col_semana_3 = st.columns(3)
ultima_linha = df_ordenado.iloc[-1]
penultima_linha = df_ordenado.iloc[-2] if total_linhas > 1 else None

casos_ultima = int(ultima_linha["casos"])
casos_delta = (
    casos_ultima - int(penultima_linha["casos"]) if penultima_linha is not None else None
)

estimado_ultima = float(ultima_linha["casos_est"])
estimado_delta = (
    estimado_ultima - float(penultima_linha["casos_est"]) if penultima_linha is not None else None
)

rt_disponivel = "Rt" in df_ordenado.columns
if rt_disponivel:
    rt_ultima = float(ultima_linha["Rt"])
    rt_delta = (
        rt_ultima - float(penultima_linha["Rt"]) if penultima_linha is not None else None
    )
else:
    rt_ultima = None
    rt_delta = None

with col_semana_1:
    st.metric("Casos na Ultima SE", f"{casos_ultima:,}", delta=casos_delta)

with col_semana_2:
    st.metric(
        "Estimativa na Ultima SE", f"{estimado_ultima:,.1f}", delta=estimado_delta
    )

with col_semana_3:
    if rt_disponivel:
        st.metric("Rt na Ultima SE", f"{rt_ultima:.2f}", delta=rt_delta)
    else:
        st.metric("Rt na Ultima SE", "N/A")

st.divider()

# --- GRÁFICOS ---
tab_casos, tab_clima, tab_alertas = st.tabs(
    ["Evolucao de Casos", "Clima e Casos", "Alertas"]
)

with tab_casos:
    st.markdown(
        "Comparativo entre os **Casos Notificados (Reais)** e os **Casos Estimados** ao longo do tempo."
    )
    grafico_linha = df_ordenado.set_index("data_ini_SE")[["casos", "casos_est"]]
    st.line_chart(grafico_linha, color=["#FF4B4B", "#FFA500"])

    st.markdown("Distribuicao de casos por semana epidemiologica.")
    grafico_barras = df_ordenado.set_index("data_ini_SE")[["casos"]]
    st.bar_chart(grafico_barras, color="#FF4B4B")

with tab_clima:
    st.markdown(
        "Explore a relacao entre temperatura e numero de casos registrados."
    )
    st.scatter_chart(
        df_ordenado, x="tempmed", y="casos", color="alerta_status", size="casos"
    )

    st.markdown("Evolucao da temperatura media ao longo do tempo.")
    grafico_temp = df_ordenado.set_index("data_ini_SE")[["tempmed"]]
    st.line_chart(grafico_temp, color="#1F77B4")

with tab_alertas:
    st.markdown(
        "Quantidade de semanas epidemiologicas que registraram cada tipo de alerta."
    )

    serie_grafico_alerta = cast(pd.Series, df_ordenado["alerta_status"])
    contagem_alertas = serie_grafico_alerta.value_counts()
    st.bar_chart(contagem_alertas)

    st.markdown("Distribuicao de niveis de alerta ao longo do tempo.")
    if "nivel" in df_ordenado.columns:
        grafico_alerta = df_ordenado.set_index("data_ini_SE")[["nivel"]]
        st.line_chart(grafico_alerta, color="#2CA02C")
    else:
        st.info("Coluna 'nivel' nao encontrada na base para gerar a serie temporal.")

# --- VISUALIZAÇÃO DOS DADOS BRUTOS ---
with st.expander("📂 Ver Tabela de Dados (Filtrada)"):
    st.dataframe(df_ordenado, use_container_width=True, hide_index=True)

st.subheader("Dicionario de Dados")
st.markdown("Descricao dos campos presentes na base de dados.")

dicionario_dados = pd.DataFrame(
    [
        {
            "Campo": "data_ini_SE",
            "Descricao": "Primeiro dia da semana epidemiologica (Domingo)",
        },
        {"Campo": "SE", "Descricao": "Semana epidemiologica"},
        {
            "Campo": "casos_est",
            "Descricao": (
                "Numero estimado de casos por semana usando o modelo de nowcasting "
                "(nota: Os valores sao atualizados retrospectivamente a cada semana)"
            ),
        },
        {
            "Campo": "cases_est_min",
            "Descricao": "Intervalo de credibilidade de 95% do numero estimado de casos",
        },
        {
            "Campo": "cases_est_max",
            "Descricao": "Intervalo de credibilidade de 95% do numero estimado de casos",
        },
        {
            "Campo": "casos",
            "Descricao": (
                "Numero de casos notificados por semana "
                "(Os valores sao atualizados retrospectivamente todas as semanas)"
            ),
        },
        {
            "Campo": "p_rt1",
            "Descricao": (
                "Probabilidade de (Rt> 1). Para emitir o alerta laranja, usamos "
                "o criterio p_rt1> 0,95 por 3 semanas ou mais."
            ),
        },
        {
            "Campo": "p_inc100k",
            "Descricao": "Taxa de incidencia estimada por 100.000",
        },
        {
            "Campo": "Localidade_id",
            "Descricao": "Divisao submunicipal (atualmente implementada apenas no Rio de Janeiro)",
        },
        {
            "Campo": "nivel",
            "Descricao": (
                "Nivel de alerta (1 = verde, 2 = amarelo, 3 = laranja, 4 = vermelho)"
            ),
        },
        {"Campo": "id", "Descricao": "Indice numerico"},
        {"Campo": "versao_modelo", "Descricao": "Versao do modelo (uso interno)"},
        {
            "Campo": "Rt",
            "Descricao": "Estimativa pontual do numero reprodutivo de casos, ver Saiba Mais",
        },
        {"Campo": "pop", "Descricao": "Populacao estimada (IBGE)"},
        {
            "Campo": "tempmin",
            "Descricao": "Media das temperaturas minimas diarias ao longo da semana",
        },
        {
            "Campo": "tempmed",
            "Descricao": "Media das temperaturas diarias ao longo da semana",
        },
        {
            "Campo": "tempmax",
            "Descricao": "Media das temperaturas maximas diarias ao longo da semana",
        },
        {
            "Campo": "umidmin",
            "Descricao": "Media da umidade relativa minima diaria do ar ao longo da semana",
        },
        {
            "Campo": "umidmed",
            "Descricao": "Media da umidade relativa diaria do ar ao longo da semana",
        },
        {
            "Campo": "umidmax",
            "Descricao": "Media da umidade relativa maxima diaria do ar ao longo da semana",
        },
        {
            "Campo": "receptivo",
            "Descricao": (
                "Indica receptividade climatica, ou seja, condicoes para alta capacidade vetorial. "
                "0 = desfavoravel, 1 = favoravel, 2 = favoravel nesta semana e na semana passada, "
                "3 = favoravel por pelo menos tres semanas (suficiente para completar um ciclo de transmissao)"
            ),
        },
        {
            "Campo": "transmissao",
            "Descricao": (
                "Evidencia de transmissao sustentada: 0 = nenhuma evidencia, 1 = possivel, "
                "2 = provavel, 3 = altamente provavel"
            ),
        },
        {
            "Campo": "nivel_inc",
            "Descricao": (
                "Incidencia estimada abaixo do limiar pre-epidemia, 1 = acima do limiar "
                "pre-epidemia, mas abaixo do limiar epidemico, 2 = acima do limiar epidemico"
            ),
        },
        {
            "Campo": "notif_accum_year",
            "Descricao": "Numero acumulado de casos no ano",
        },
    ]
)

st.dataframe(dicionario_dados, use_container_width=True, hide_index=True)