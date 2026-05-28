# DataDengue

## Visao geral
Projeto para coletar dados da API InfoDengue, normalizar as colunas e abrir um dashboard em Streamlit com indicadores e graficos para Jundiai.

Fluxo principal:
- Baixa dados da API InfoDengue.
- Trata e padroniza o dataset.
- Salva o CSV em data/Dengue_Jundiai.csv.
- Abre o dashboard em src/dashboard.py.

## Requisitos

- Python >= 3.13
- uv instalado
- Acesso a internet para consultar a API

## Instalacao e Execução
```bash
git clone https://github.com/Arkmedess/DataDengue
cd DataDengue
uv sync
uv run main.py
```

O comando acima:
- Faz a requisicao na API.
- Gera o arquivo data/Dengue_Jundiai.csv.
- Inicia o Streamlit com o dashboard.

## Configuracao de parametros
Os parametros da requisicao ficam em src/models.py, classe RequisitionBody. Ali voce pode ajustar:

- geocode (cidade)
- disease (dengue, chikungunya, zika)
- ew_start, ew_end (semanas epidemiologicas)
- ey_start, ey_end (anos)

## O que o dashboard se propoe a responder
O painel foi pensado para apoiar o acompanhamento semanal e responder perguntas como:

- Como evoluem os casos notificados e os casos estimados ao longo do tempo.
- Qual foi o pico de casos e em qual semana epidemiologica ocorreu.
- Qual o nivel de alerta predominante no periodo filtrado.
- Como a temperatura media se relaciona com o volume de casos.
- Qual foi o comportamento recente (ultima semana) de casos e estimativas.

As informacoes exibidas consideram o municipio e o intervalo configurados na requisicao.

## Estrutura do projeto

- main.py: orquestra a coleta e abre o dashboard
- src/api_service.py: integra com a API e salva o CSV
- src/models.py: define o modelo e a URL de requisicao
- src/dashboard.py: interface Streamlit
- data/: saida de dados

## Prints

<img width="1836" height="698" alt="Captura de tela 2026-05-28 182819" src="https://github.com/user-attachments/assets/0194105f-4906-4e3a-a095-9825f9151dd7" />

<img width="1562" height="976" alt="Captura de tela 2026-05-28 182947" src="https://github.com/user-attachments/assets/5d3dcf58-542b-4af8-8d37-448a1ccb99c7" />

<img width="1561" height="941" alt="Captura de tela 2026-05-28 182920" src="https://github.com/user-attachments/assets/e3567ab5-fac0-4a25-ba38-2d269f902030" />


## Observacoes

- Se o arquivo data/Dengue_Jundiai.csv ja existir, ele sera sobrescrito.
- Se a API estiver indisponivel, o script exibira o erro no terminal.
