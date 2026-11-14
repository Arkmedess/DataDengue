# DataDengue

Pipeline de engenharia de dados e inteligência epidemiológica para monitoramento de arboviroses (**Dengue, Chikungunya e Zika**) a partir da **API InfoDengue (Fiocruz/EMAp)**, desenvolvido para o **Projeto Integrador FATEC — Desafio de Dados (2026)**. Estrutura o ciclo analítico completo: ingestão relacional em 3FN (**PostgreSQL**), modelagem dimensional (**Star Schema**), geração de **SQL Views**, exportação de datasets, inspeção via **JetBrains DataGrip**, dashboard web com **DataGrid** e painel executivo no **Power BI (.pbix / .pbip)**.

**Integrantes do Grupo:** Aline, Arthur, Matheus, Rayllis e Rebeca.

---

## Árvore de Diretórios do Projeto

```text
DataDengue/
├── docker-compose.yml              # Serviço PostgreSQL 16 (Alpine) na porta 5432
├── main.py                         # Ponto de entrada CLI e orquestrador do pipeline
├── pyproject.toml                  # Configuração do projeto e dependências (uv/pip)
├── uv.lock                         # Lockfile determinístico de pacotes
├── README.md                       # Documentação principal
│
├── sql/                            # Scripts DDL e Consultas SQL
│   ├── 01_create_transacional_oltp.sql  # Schema 'oltp': tabelas relacionais em 3FN
│   ├── 02_create_dw_star_schema.sql    # Schema 'dw': modelo dimensional Star Schema
│   ├── 03_queries_analiticas.sql        # Consultas de agregação e métricas avançadas
│   └── 04_create_views.sql             # SQL Views analíticas (vw_*)
│
├── src/                            # Código-fonte da aplicação
│   ├── api_service.py              # Cliente HTTP resiliente para a API InfoDengue
│   ├── database.py                 # Gerenciamento de Engine SQLAlchemy e conexões PostgreSQL
│   ├── models.py                   # Modelos de validação Pydantic para parâmetros
│   ├── oltp_loader.py              # Ingestão idempotente normalizada em 3FN (schema oltp)
│   ├── etl_pipeline.py             # Pipeline ETL para o Star Schema e exportação de CSVs
│   ├── dashboard.py                # Dashboard analítico em Streamlit com DataGrid Inspector
│   └── cli/                        # Camada de interface de linha de comando
│       ├── __init__.py             # Exportação das rotinas da CLI
│       └── service.py              # Subcomandos (status, summary, clean, tui)
│
├── data/                           # Armazenamento de dados
│   ├── oltp/                       # Diretório auxiliar operacional
│   └── dw/                         # Datasets dimensionais exportados para Power BI (CSV)
│       ├── dim_alerta.csv
│       ├── dim_clima.csv
│       ├── dim_doenca.csv
│       ├── dim_municipio.csv
│       ├── dim_tempo.csv
│       └── fato_casos_dengue.csv
│
├── dax/                            # Fórmulas e Medidas DAX
│   └── medidas_power_bi.dax        # 16 medidas calculadas prontas para Power BI
│
├── docs/                           # Documentação e apresentação do projeto
│   └── Apresentacao_DataDengue.pdf # Apresentação final em PDF (Visão de Negócio)
│
├── powerbi/                        # Projeto Power BI (.pbix e .pbip)
│   ├── Atividade_Sabado.pbix       # Dashboard completo com medidas DAX
│   └── Atividade_Sabado.pbip       # Projeto PBIP (Report + SemanticModel)
│
└── tests/                          # Suíte de testes automatizados (pytest)
    ├── test_cli_service.py
    ├── test_etl_pipeline.py
    ├── test_multi_disease_and_resilience.py
    └── test_oltp_loader.py
```

---

## A API InfoDengue & Parâmetros

Os dados são consumidos diretamente da API pública do **InfoDengue** (Fiocruz e FGV/EMAp), cruzando dados laboratoriais do SINAN com dados meteorológicos (satélite e estações aeroportuárias).

### Parâmetros Suportados (`src/models.py`)
* `geocode`: Código IBGE do município (padrão: `3525904` — Jundiaí/SP).
* `disease`: Arbovirose (`dengue`, `chikungunya`, `zika`). Suporta ingestão multi-doenças em lote.
* `ew_start` / `ew_end`: Semanas epidemiológicas (1 a 53).
* `ey_start` / `ey_end`: Anos da série histórica (2010 a 2026, com autocorreção caso invertidos).

---

## Arquitetura de Dados: PostgreSQL (`oltp` e `dw`)

O banco utiliza dois esquemas lógicos desacoplados no PostgreSQL:

1. **Schema `oltp` (Transacional em 3FN):**
   * `tb_municipio`: Cadastro municipal e demográfico.
   * `tb_notificacao_dengue`: Notificações semanais por doença com Nowcasting.
   * `tb_monitoramento_climatico`: Dados de temperatura e umidade.
   * `tb_alerta_epidemiologico`: Níveis de alerta e transmissão.

2. **Schema `dw` (Star Schema Dimensional):**
   * `dim_tempo`, `dim_municipio`, `dim_alerta`, `dim_clima`, `dim_doenca`.
   * `fato_casos_dengue`: Métricas de casos, estimativas, incidência e gap de subnotificação.

3. **SQL Views Analíticas Prontas (`dw.vw_*`):**
   * **`vw_star_schema_completo`**: Visão desnormalizada (todas as dimensões conectadas aos fatos). Ideal para conexão direta no Power BI.
   * **`vw_sazonalidade_mensal`**: Total de casos e média móvel por mês e ano.
   * **`vw_correlacao_clima_casos`**: Casos agregados por faixa de temperatura e umidade.
   * **`vw_alertas_criticos`**: Notificações em nível Laranja e Vermelho com $R_t > 1$.

---

## Instalação e Execução Rápida

### Pré-requisitos
* **Docker** e **Docker Compose**
* **Python >= 3.13** e [uv](https://docs.astral.sh/uv/)

```bash
# 1. Clonar o repositório
git clone https://github.com/Arkmedess/DataDengue.git
cd DataDengue

# 2. Instalar dependências no ambiente virtual
uv sync

# 3. Subir o PostgreSQL no Docker
docker compose up -d

# 4. Executar carga completa de dados (Dengue, Chikungunya e Zika)
uv run python main.py --all-diseases
```

---

## Comandos da CLI & Utilitários (Tabela Completa)

A aplicação pode ser operada via linha de comando (`main.py`) com flags ou subcomandos:

| Comando / Flag | Argumentos | Valor Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `python main.py` | N/A | Ano 2025, Dengue | Executa o pipeline padrão (coleta $\rightarrow$ OLTP $\rightarrow$ DW $\rightarrow$ CSVs). |
| `--all-diseases` | N/A | `False` | Coleta e consolida as 3 arboviroses (Dengue, Chikungunya e Zika) em lote. |
| `--diseases` | `<d1> <d2>...` | `None` | Seleciona arboviroses específicas (ex.: `--diseases dengue chikungunya`). |
| `--disease` | `dengue\|chikungunya\|zika` | `dengue` | Consulta uma única doença específica. |
| `--start-year` | `YYYY` (2010–2026) | `2025` | Ano inicial da série histórica (com autocorreção). |
| `--end-year` | `YYYY` (2010–2026) | `2025` | Ano final da série histórica. |
| `--geocode` | Código IBGE (7 dígitos) | `3525904` | Município a monitorar (padrão: Jundiaí/SP). |
| `--ui` | N/A | `False` | Executa o pipeline e inicia o Streamlit automaticamente no navegador. |
| `--tui` ou `-i` | N/A | `False` | Inicia o menu interativo amigável no terminal (TUI). |
| **`status`** | Subcomando | N/A | Exibe status da conexão PostgreSQL, contagem de registros em `oltp`/`dw`, períodos e CSVs gerados. |
| **`summary`** | `--year`, `--limit`, `--json` | Ano atual | Exibe resumo epidemiológico anual/semanal formatado no terminal (ou em JSON para scripts). |
| **`clean`** | `--all`, `-y` | Limpa DW | Trunca as tabelas dimensionais no PostgreSQL e apaga os CSVs. Com `--all`, reseta também o `oltp`. |
| **`tui`** | Subcomando | N/A | Abre a interface de menu navegável por teclado no terminal. |

### Exemplos Práticos:
```bash
# Ingestão de 2 anos para todas as arboviroses
uv run python main.py --all-diseases --start-year 2024 --end-year 2025

# Resumo epidemiológico em formato JSON
uv run python main.py summary --year 2025 --json

# Verificar a saúde do banco e tabelas geradas
uv run python main.py status

# Limpeza e reset do Data Warehouse
uv run python main.py clean -y
```

---

## Inspeção no JetBrains DataGrip

Para visualizar esquemas, tabelas e diagramas no **DataGrip**:
1. Crie um novo Data Source: **PostgreSQL**.
2. Configure:
   * **Host:** `localhost` | **Port:** `5432`
   * **Database:** `datadengue` | **User:** `postgres` | **Password:** `postgres`
3. Na aba **Schemas**, marque as opções **`oltp`** e **`dw`**.
4. Clique com o botão direito no schema `dw` $\rightarrow$ **Diagrams $\rightarrow$ Show Diagram...** para visualizar o modelo estrela completo.

---

## Visualização no DataGrid (Streamlit)

O projeto inclui um dashboard com visualização interativa de dados em grade:
```bash
uv run streamlit run src/dashboard.py
```
- Acesse a aba **`DataGrid Inspector`** para navegar por qualquer tabela do `dw` ou `oltp`, ordenar colunas, aplicar filtros e exportar recortes.

---

## Power BI (.pbix / .pbip) & Apresentação

O painel no Power BI Desktop segue a identidade visual em azul e branco do **SUS** (Relatório de Alastramento — Jundiaí/SP, série histórica **2016–2026** com **1.556 registros semanais**), trazendo filtros de **Ano**, **Mês**, **Doença** e **Estação do Ano**, além de comparativo de *Nowcasting*, dispersão climática, níveis de alerta e distribuição sazonal.

1. **Conexão Direta ao PostgreSQL:** Obter Dados $\rightarrow$ Banco de Dados PostgreSQL (`localhost:5432`, banco `datadengue`) $\rightarrow$ selecione as tabelas do schema `dw` ou a view **`dw.vw_star_schema_completo`**.
2. **Conexão via CSVs:** Obter Dados $\rightarrow$ Pasta `data/dw/` com os 6 datasets prontos.
3. **Medidas DAX:** Copie as 16 fórmulas prontas disponíveis em [dax/medidas_power_bi.dax](dax/medidas_power_bi.dax).

> **Documentação e Apresentação:**
> * Apresentação em PDF (Visão de Negócio): [docs/Apresentacao_DataDengue.pdf](docs/Apresentacao_DataDengue.pdf)
> * Projeto Power BI: [powerbi/Atividade_Sabado.pbix](powerbi/Atividade_Sabado.pbix) e [powerbi/Atividade_Sabado.pbip](powerbi/Atividade_Sabado.pbip)

---

## Testes Automatizados

A suíte de testes valida a integridade do banco de dados, idempotência, resiliência a dados corrompidos e consistência do ETL diretamente contra o PostgreSQL:
```bash
uv run pytest
```

---

## Demonstração da Interface

<img width="1836" height="698" alt="Visão Geral do Painel" src="https://github.com/user-attachments/assets/0194105f-4906-4e3a-a095-9825f9151dd7" />

<img width="1562" height="976" alt="Gráficos de Correlação Climática" src="https://github.com/user-attachments/assets/5d3dcf58-542b-4af8-8d37-448a1ccb99c7" />

<img width="1561" height="941" alt="Tabela de Dados e Alertas" src="https://github.com/user-attachments/assets/e3567ab5-fac0-4a25-ba38-2d269f902030" />
