# DataDengue

Pipeline de dados e análise epidemiológica para monitoramento de arboviroses a partir da **API InfoDengue (Fiocruz/EMAp)**, estruturando desde a ingestão relacional até modelos dimensionais (Star Schema) e interfaces de visualização.

---

## A API InfoDengue

Os dados são consumidos diretamente da API pública mantida pelo sistema **InfoDengue** (Fiocruz e FGV/EMAp), que cruza notificações laboratoriais do SINAN com dados meteorológicos de satélite e estações aeroportuárias.

### Parâmetros Configuráveis (`src/models.py`)
No modelo `RequisitionBody`, você pode personalizar os parâmetros da requisição para qualquer município ou janela temporal:

* `geocode`: Código IBGE do município (padrão: `3525904` — Jundiaí/SP).
* `disease`: Arbovirose desejada (`dengue`, `chikungunya`, `zika`).
* `format`: Formato de resposta da API (`csv` ou `json`).
* `ew_start` / `ew_end`: Semanas epidemiológicas de início e fim (1 a 53).
* `ey_start` / `ey_end`: Anos do período de análise (ex.: 2024 a 2025).

A API retorna métricas brutas somadas a estimativas estatísticas de **Nowcasting** (correção do atraso natural de digitação e confirmação de exames) e cálculo de velocidade de contágio ($R_t$).

---

## O Que os Dados Permitem Enxergar (Views & Análises)

O ecossistema organiza os dados brutos em visões analíticas focadas em responder:

* **Real vs. Estimado (Nowcasting):** Acompanhamento simultâneo de casos notificados e projeções corrigidas no tempo, apontando represamento de resultados laboratoriais.
* **Sazonalidade e Identificação de Picos:** Rastreio exato da semana e do mês em que a transmissão explode (ex.: picos históricos concentrados entre as semanas 10 e 15).
* **Correlação Climática x Vetor:** Como oscilações na temperatura média e faixas de umidade do ar antecipam ou freiam o ciclo biológico do *Aedes aegypti*.
* **Semáforo Epidemiológico (Níveis de Alerta):** Monitoramento das transições de risco sanitário:
  * 🟢 **Verde:** Nível basal e monitoramento de rotina.
  * 🟡 **Amarelo:** Alerta precoce por condições climáticas favoráveis.
  * 🟠 **Laranja:** Transmissão sustentada em expansão ($R_t > 1$).
  * 🔴 **Vermelho:** Epidemia declarada com alta sobrecarga assistencial.
* **Indicadores Dinâmicos de Curto Prazo:** Comparativo semana-a-semana (*delta WoW*), incidência por 100 mil habitantes e ritmo de contágio da última semana monitorada.

---

## Instalação e Execução

### Requisitos
* Python >= 3.13
* [uv](https://docs.astral.sh/uv/) instalado

```bash
git clone https://github.com/Arkmedess/DataDengue.git
cd DataDengue
uv sync
```

### 1. Executar o Pipeline de Dados
Processa a coleta na API, popula o banco transacional relacional (OLTP em 3FN), gera o Data Warehouse (Star Schema) e exporta os datasets para `data/dw/`:
```bash
# Execução padrão (ano 2025, Dengue, Jundiaí)
uv run python main.py

# Executar com arboviroses combinadas (Dengue, Chikungunya e Zika)
uv run python main.py --all-diseases --start-year 2024 --end-year 2025

# Ou selecionar apenas duas (ex.: Dengue + Chikungunya)
uv run python main.py --diseases dengue chikungunya --start-year 2024 --end-year 2025

# Executar e abrir o Streamlit ao final
uv run python main.py --ui
```

### 2. Painel Interativo no Terminal (TUI)
Para abrir o menu interativo com opções de carga, visualização e limpeza:
```bash
uv run python main.py --tui
# ou
uv run python main.py tui
```

### 3. Utilitários de Linha de Comando (CLI)
```bash
# Verificar status dos bancos de dados, período e arquivos gerados
uv run python main.py status

# Resumo epidemiológico anual no terminal (ou com --json para scripts)
uv run python main.py summary
uv run python main.py summary --year 2025 --limit 10

# Limpar Data Warehouse e CSVs gerados (com -y para bypass de confirmação)
uv run python main.py clean -y

# Reset total (limpa DW e banco transacional OLTP)
uv run python main.py clean --all -y
```

### 4. Guia Rápido de Opções e Flags da CLI

| Flag / Comando | Argumentos | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `--all-diseases` | N/A | `False` | Coleta e carrega as 3 arboviroses (Dengue, Chikungunya e Zika) em lote. |
| `--diseases` | `<d1> <d2>...` | `None` | Permite selecionar múltiplas doenças (ex.: `--diseases dengue chikungunya`). |
| `--disease` | `dengue\|chikungunya\|zika` | `dengue` | Consulta uma única arbovirose. |
| `--start-year` | `YYYY` (2010 a 2026) | `2025` | Ano inicial da série histórica (auto-corrige se invertido). |
| `--end-year` | `YYYY` (2010 a 2026) | `2025` | Ano final da série histórica. |
| `--geocode` | Código IBGE | `3525904` | Município a monitorar (padrão: Jundiaí/SP). |
| `--ui` | N/A | `False` | Abre a interface analítica Streamlit no navegador ao concluir a carga. |
| `--tui` ou `-i` | N/A | `False` | Abre o menu interativo no terminal (TUI). |
| `status` | Subcomando | N/A | Exibe saúde dos bancos SQLite, períodos, tamanho em KB e CSVs gerados. |
| `summary` | `--year`, `--limit`, `--json` | N/A | Exibe resumo epidemiológico anual ou semanal diretamente no terminal. |
| `clean` | `--all`, `-y` | N/A | Remove tabelas analíticas do DW (ou reset total com `--all`). |

### 5. Rodar os Testes
```bash
uv run pytest
```

---

## Estrutura do Projeto

* `main.py`: Orquestrador ponta a ponta (coleta, OLTP, DW e abertura da interface).
* `sql/`: Scripts DDL relacionais (`01_create_transacional_oltp.sql`), dimensionais (`02_create_dw_star_schema.sql`) e consultas analíticas (`03_queries_analiticas.sql`).
* `src/api_service.py`: Requisição à API InfoDengue e tratamento inicial.
* `src/cli/`: Utilitários de terminal, inspeção de status, resumo e TUI interativa.
* `src/models.py`: Modelos Pydantic para parâmetros de requisição e validação de schema.
* `src/database.py`: Conexão com banco e execução de scripts SQL.
* `src/oltp_loader.py`: Carga relacional transacional em 3FN.
* `src/etl_pipeline.py`: Pipeline dimensional para carga do Star Schema e exportação de CSVs.
* `src/dashboard.py`: Dashboard analítico interativo em Streamlit.
* `tests/`: Suíte de testes automatizados do pipeline.
* `data/`: Armazenamento local dos bancos SQLite e dos CSVs dimensionais prontos para Power BI.

---

## Prints do Dashboard

<img width="1836" height="698" alt="Visão Geral do Painel" src="https://github.com/user-attachments/assets/0194105f-4906-4e3a-a095-9825f9151dd7" />

<img width="1562" height="976" alt="Gráficos de Correlação Climática" src="https://github.com/user-attachments/assets/5d3dcf58-542b-4af8-8d37-448a1ccb99c7" />

<img width="1561" height="941" alt="Tabela de Dados e Alertas" src="https://github.com/user-attachments/assets/e3567ab5-fac0-4a25-ba38-2d269f902030" />
