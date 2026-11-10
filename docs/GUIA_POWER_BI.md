# Guia Prático de Construção do Painel no Power BI (.pbix)

Este guia orienta o passo a passo para conectar os dados gerados pelo pipeline do **DataDengue** no **Power BI Desktop**, configurar os relacionamentos do **Star Schema**, criar as medidas DAX e montar os visuais para a entrega do Desafio de Business Intelligence.

---

## 1. Importando os Dados no Power BI Desktop

Os arquivos dimensionais foram gerados em formato CSV estruturado com codificação UTF-8-BOM na pasta `data/dw/`:

1. Abra o **Power BI Desktop**.
2. Clique em **Obter Dados (Get Data) -> Texto/CSV**.
3. Selecione e carregue os **6 arquivos** presentes em `data/dw/`:
   * `fato_casos_dengue.csv`
   * `dim_tempo.csv`
   * `dim_doenca.csv`
   * `dim_municipio.csv`
   * `dim_alerta.csv`
   * `dim_clima.csv`
4. Na tela de prévia, selecione **Carregar (Load)**.

> **Dica Alternativa:** Você também pode conectar via banco SQLite instalando o driver ODBC para SQLite (`SQLite3 ODBC Driver`) ou conectando diretamente à view `vw_star_schema_completo`. No entanto, a importação dos 6 CSVs dimensionais é o método mais rápido e 100% nativo.

---

## 2. Configurando o Modelo Dimensional (Star Schema)

No menu lateral esquerdo do Power BI, clique no ícone de **Modelo (Model View)**.  
Organize a tabela `fato_casos_dengue` no centro e as 5 dimensões ao redor, criando os seguintes **relacionamentos 1 para N (1:*) com direção de filtro único (Dimensão -> Fato)**:

| Tabela de Origem (Dimensão) | Coluna na Dimensão | Tabela de Destino (Fato) | Coluna na Fato | Cardinalidade |
| :--- | :--- | :--- | :--- | :--- |
| **`dim_tempo`** | `sk_tempo` | **`fato_casos_dengue`** | `sk_tempo` | 1:* (1 para Muitos) |
| **`dim_doenca`** | `sk_doenca` | **`fato_casos_dengue`** | `sk_doenca` | 1:* (1 para Muitos) |
| **`dim_municipio`** | `sk_municipio` | **`fato_casos_dengue`** | `sk_municipio` | 1:* (1 para Muitos) |
| **`dim_alerta`** | `sk_alerta` | **`fato_casos_dengue`** | `sk_alerta` | 1:* (1 para Muitos) |
| **`dim_clima`** | `sk_clima` | **`fato_casos_dengue`** | `sk_clima` | 1:* (1 para Muitos) |

*(O Power BI costuma detectar a maioria desses relacionamentos automaticamente ao carregar).*

---

## 3. Criando a Tabela de Medidas DAX

Para manter o modelo limpo e profissional:
1. Na guia **Página Inicial**, clique em **Inserir Dados (Enter Data)**.
2. Nomeie a tabela como **`_Medidas`** e clique em **Carregar**.
3. Clique com o botão direito na tabela `_Medidas` e selecione **Nova Medida**.
4. Copie e cole as medidas do arquivo [dax/medidas_power_bi.dax](dax/medidas_power_bi.dax).

**Medidas Fundamentais a Adicionar:**
* `Total Casos = SUM(fato_casos_dengue[casos_notificados])`
* `Total Estimado = SUM(fato_casos_dengue[casos_estimados])`
* `Gap Subnotificacao = [Total Estimado] - [Total Casos]`
* `Taxa Incidencia 100k = DIVIDE([Total Casos], MAX(dim_municipio[populacao]), 0) * 100000`
* `Rt Medio = AVERAGE(fato_casos_dengue[taxa_rt])`
* `Media Movel 4 Semanas = CALCULATE([Total Casos], DATESINPERIOD(dim_tempo[data_inicio_semana], LASTDATE(dim_tempo[data_inicio_semana]), -28, DAY)) / 4`
* `Variacao Semanal WoW % = ...`

---

## 4. Estrutura Recomendada de Páginas do Dashboard

### Página 1: Painel Executivo & Vigilância Epidemiológica
* **Cabeçalho:** Filtro de Segmentação de Dados (*Slicer*) com `dim_doenca[nome_doenca]` e linha do tempo de `dim_tempo[ano]`.
* **Cartões de KPI (Linha Superior):**
  1. *Total de Casos Notificados* (Valor: `[Total Casos]`)
  2. *Casos Estimados Nowcasting* (Valor: `[Total Estimado]`)
  3. *Taxa de Incidência* (Valor: `[Taxa Incidencia 100k]` / 100 mil hab)
  4. *Ritmo de Contágio* (Valor: `[Rt Medio]`)
* **Gráfico de Linhas e Barras (Centro):**
  * Eixo X: `dim_tempo[data_inicio_semana]` ou `dim_tempo[semana_epidem]`
  * Linha 1: `[Total Casos]` (Vermelho)
  * Linha 2: `[Total Estimado]` (Laranja tracejado)
  * Linha 3: `[Media Movel 4 Semanas]` (Azul)
* **Gráfico de Barras Horizontais (Lateral Direita):**
  * Distribuição de semanas por `dim_alerta[status_alerta_nome]`

### Página 2: Clima & Correlação Vetorial
* **Gráfico de Dispersão (Scatter Plot):**
  * Eixo X: `fato_casos_dengue[temp_media_semana]`
  * Eixo Y: `fato_casos_dengue[casos_notificados]`
  * Tamanho da Bolha: `fato_casos_dengue[umid_media_semana]`
  * Legenda: `dim_alerta[status_alerta_nome]`
* **Matriz de Calor / Tabela:**
  * Linhas: `dim_clima[faixa_temperatura]`
  * Colunas: `dim_clima[faixa_umidade]`
  * Valores: `[Total Casos]` e `[Rt Medio]`

---

## 5. Salvando e Entregando o Arquivo PBIX
1. Clique em **Arquivo -> Salvar Como**.
2. Salve com o nome **`Dashboard_DataDengue_Jundiai.pbix`** na raiz ou pasta de entregas do projeto.
3. Este arquivo contém o modelo relacional completo, todas as fórmulas DAX e os visuais renderizados, atendendo 100% dos requisitos mínimos do edital.
