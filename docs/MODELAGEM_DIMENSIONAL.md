# Documentação Técnica: Modelagem de Dados & Arquitetura Analítica (DataDengue)

Este documento descreve a arquitetura de dados concebida para atender aos requisitos do **Desafio Business Intelligence (Data-to-Insight Journey) — FATEC 2026**.

---

## 1. Topologia da Solução

O projeto implementa a jornada completa desde a ingestão da fonte primária (API InfoDengue/Fiocruz), passando pela normalização transacional (OLTP em 3FN) e pela carga dimensional (Star Schema/OLAP) no Data Warehouse:

```mermaid
flowchart TD
    API["InfoDengue API (Fiocruz)"] --> Ingest["Ingestão / Extrator Python"]
    
    subgraph OLTP["1. Banco de Dados Transacional (3FN)"]
        Ingest --> M["tb_municipio"]
        Ingest --> U["tb_unidade_notificadora"]
        Ingest --> N["tb_notificacao_dengue"]
        Ingest --> C["tb_monitoramento_climatico"]
        Ingest --> A["tb_alerta_epidemiologico"]
    end

    subgraph ETL["2. Pipeline ETL Dimensional"]
        M & N & C & A --> Transform["src/etl_pipeline.py<br/>(Limpeza, Surrogate Keys, Enriquecimento Temporal)"]
    end

    subgraph DW["3. Data Warehouse (Star Schema)"]
        Transform --> DT["dim_tempo"]
        Transform --> DM["dim_municipio"]
        Transform --> DA["dim_alerta"]
        Transform --> DC["dim_clima"]
        Transform --> FATO["fato_casos_dengue"]
    end

    subgraph Consumo["4. Camada de Apresentação e Decisão"]
        DW --> PBI["Power BI Desktop (.pbix)<br/>(Relacionamentos 1:N + Medidas DAX)"]
        DW --> SQL["Queries Analíticas SQL"]
        DW --> STR["Streamlit Web App"]
    end
```

---

## 2. Diagrama Entidade-Relacionamento (Star Schema)

```mermaid
erDiagram
    dim_tempo ||--o{ fato_casos_dengue : "sk_tempo"
    dim_municipio ||--o{ fato_casos_dengue : "sk_municipio"
    dim_alerta ||--o{ fato_casos_dengue : "sk_alerta"
    dim_clima ||--o{ fato_casos_dengue : "sk_clima"

    dim_tempo {
        int sk_tempo PK "YYYYMMDD"
        date data_inicio_semana
        int semana_epidem "1 a 53"
        int ano_epidem
        int semana_ano "YYYYWW"
        int mes
        string nome_mes
        int ano
        int trimestre "1 a 4"
        string ano_mes
        string estacao_ano "Verão, Outono..."
    }

    dim_municipio {
        int sk_municipio PK
        int geocode "Código IBGE"
        string nome_municipio
        string uf
        int populacao
        string faixa_populacional
    }

    dim_alerta {
        int sk_alerta PK "1 a 4"
        int nivel_alerta
        string status_alerta_nome "Verde, Amarelo, Laranja, Vermelho"
        string cor_indicativa "Hexadecimal"
        string descricao_risco
        string acao_preventiva_recomendada
    }

    dim_clima {
        int sk_clima PK
        string faixa_temperatura "Fria, Agradável, Favorável, Alta"
        string faixa_umidade "Baixa, Ideal Vetorial, Alta"
        string condicao_receptividade
        string risco_clima_proliferacao "Baixo, Moderado, Crítico"
    }

    fato_casos_dengue {
        int sk_fato PK
        int sk_tempo FK
        int sk_municipio FK
        int sk_alerta FK
        int sk_clima FK
        int casos_notificados "Fato Aditivo"
        real casos_estimados "Nowcasting"
        real diferenca_nowcasting "Subnotificação estimada"
        int casos_confirmados
        int casos_provaveis
        real incidencia_por_100k "Taxa por 100k hab"
        real taxa_rt "Ritmo Reprodutivo Efetivo"
        real probabilidade_rt_maior_1
        real temp_media_semana
        real umid_media_semana
        int notif_acumuladas_ano
    }
```

---

## 3. Dicionário de Tabelas e Campos

### 3.1. Dimensão Tempo (`dim_tempo`)
Armazena a granularidade cronológica e epidemiológica semanal:
* **`sk_tempo`**: Chave substituta numérica no formato `YYYYMMDD` correspondente ao domingo inicial da semana epidemiológica.
* **`semana_epidem`**: Número da semana de acordo com o calendário epidemiológico do Ministério da Saúde (1 a 53).
* **`estacao_ano`**: Classificação sazonal (Verão, Outono, Inverno, Primavera), fundamental para análises de ciclo vetorial.

### 3.2. Dimensão Município (`dim_municipio`)
Identificação territorial e demográfica:
* **`sk_municipio`**: Chave substituta do município (baseada no código IBGE 3525904 - Jundiaí/SP).
* **`populacao`**: Censo/estimativa IBGE utilizada para o cálculo de incidência por 100 mil habitantes.

### 3.3. Dimensão Alerta (`dim_alerta`)
Tabela dimensional dos níveis de atenção sanitária da metodologia InfoDengue:
* **1 - Verde:** Baixo risco. Monitoramento de rotina.
* **2 - Amarelo:** Atenção epidemiológica. Intensificação de vistorias residenciais.
* **3 - Laranja:** Alerta de transmissão acelerada ($R_t > 1$ sustentado). Mobilização comunitária.
* **4 - Vermelho:** Emergência epidêmica. Abertura de polos de hidratação e nebulização veicular.

### 3.4. Dimensão Condicionantes Climáticos (`dim_clima`)
Categorização dos fatores ambientais que governam a velocidade reprodutiva do mosquito *Aedes aegypti*:
* **`faixa_temperatura`**: Fria ($<18^\circ\text{C}$), Agradável ($18-24^\circ\text{C}$), Favorável ao Vetor ($24-28^\circ\text{C}$), Alta ($>28^\circ\text{C}$).
* **`faixa_umidade`**: Baixa ($<60\%$), Ideal ao Vetor ($60-80\%$), Alta ($>80\%$).
* **`risco_clima_proliferacao`**: Cruzamento ambiental (Baixo, Moderado, Crítico).

### 3.5. Tabela Fato (`fato_casos_dengue`)
Fatos métricos quantitativos semanais:
* **`casos_notificados`**: Casos brutos registrados na semana.
* **`casos_estimados`**: Projeção estatística ajustada por atraso de notificação (*nowcasting* da Fiocruz).
* **`diferenca_nowcasting`**: Diferença entre casos estimados e notificados, evidenciando represamento/atraso laboratorial.
* **`incidencia_por_100k`**: $\frac{\text{casos}}{\text{população}} \times 100.000$, padrão epidemiológico internacional.
* **`taxa_rt`**: Número reprodutivo básico efetivo ($R_t > 1$ indica epidemia em expansão).

---

## 4. Como Executar o Pipeline

```bash
# Sincroniza ambiente e dependências
uv sync

# Executa testes unitários e de integração
uv run pytest

# Executa o pipeline de dados completo (API -> OLTP -> DW -> CSVs)
uv run python main.py

# Para executar o pipeline e abrir o Streamlit:
uv run python main.py --ui
```
