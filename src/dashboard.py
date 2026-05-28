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

# --- KPIs (Métricas de Destaque) ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_casos = df_filtrado["casos"].sum()
    st.metric("Total de Casos (Real)", f"{total_casos:,}")

with col2:
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

with col3:
    media_temp = df_filtrado["tempmed"].mean()
    st.metric("Temperatura Média", f"{media_temp:.1f} °C")

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

# --- GRÁFICOS ---

st.subheader("1. Evolução Temporal de Casos")
st.markdown(
    "Comparativo entre os **Casos Notificados (Reais)** e os **Casos Estimados** ao longo do tempo."
)
# Prepara dados para o gráfico de linha nativo
grafico_linha = df_filtrado.set_index("data_ini_SE")[["casos", "casos_est"]]
st.line_chart(grafico_linha, color=["#FF4B4B", "#FFA500"])

col_esq, col_dir = st.columns(2)

with col_esq:
    st.subheader("2. Temperatura vs Casos")
    st.markdown(
        "Verifique se o aumento da temperatura influencia no número de casos registrados."
    )
    # Gráfico de dispersão nativo
    st.scatter_chart(
        df_filtrado, x="tempmed", y="casos", color="alerta_status", size="casos"
    )

with col_dir:
    st.subheader("3. Frequência de Alertas")
    st.markdown(
        "Quantidade de semanas epidemiológicas que registraram cada tipo de alerta."
    )

    # 1. Forçamos o editor a entender que a coluna é uma Series do Pandas
    serie_grafico_alerta = cast(pd.Series, df_filtrado["alerta_status"])

    # 2. Agora o .value_counts() é reconhecido perfeitamente
    contagem_alertas = serie_grafico_alerta.value_counts()

    # 3. Plota o gráfico de barras sem nenhuma linha vermelha no Zed
    st.bar_chart(contagem_alertas)

# --- VISUALIZAÇÃO DOS DADOS BRUTOS ---
with st.expander("📂 Ver Tabela de Dados (Filtrada)"):
    st.dataframe(df_filtrado, width="stretch", hide_index=True)
