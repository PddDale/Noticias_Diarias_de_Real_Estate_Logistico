# 📊 News Briefing — Inteligência de Mercado em Real Estate Logístico

Briefing diário automatizado de **notícias + painel macroeconômico brasileiro**, voltado para inteligência de mercado no setor de **real estate logístico/industrial**, com uma seção dedicada a **notícias globais** (política e relações internacionais).

A cada execução, o script coleta manchetes de dezenas de fontes, filtra e rankeia por relevância, cruza com indicadores macro do Banco Central e da bolsa, e gera um **relatório HTML autossuficiente e estilizado** — pronto para leitura no navegador.

---

## 🎯 Intuito

Profissionais de mercado imobiliário, fundos e áreas de research gastam tempo demais garimpando notícias relevantes em dezenas de portais. Este projeto automatiza esse trabalho:

- **Centraliza** o que importa em um único relatório diário.
- **Prioriza** por relevância temática (galpões, FIIs, M&A, concorrentes, macro) em vez de cronologia pura.
- **Contextualiza** as notícias com um painel macroeconômico atualizado (Selic, IPCA, câmbio, IFIX, Ibovespa).
- **Roda sozinho**: instala as próprias dependências, faz cache diário e abre o resultado no navegador.

O foco setorial é logística/industrial, mas a arquitetura de temas e keywords é totalmente configurável.

---

## ✨ O que ele faz

A cada execução, o pipeline percorre 5 etapas:

1. **Coleta** manchetes de:
   - Feeds RSS diretos (Exame Invest, Money Times).
   - Feeds globais confiáveis (BBC, The Guardian, Al Jazeera, UN News, NPR, Deutsche Welle).
   - Google News RSS por tema e por veículo (Valor, InfoMoney, Brazil Journal, Reuters, AP…).
2. **Filtra** pelas últimas 24–36h, **deduplica** notícias repetidas e **rankeia por relevância** (peso de keywords por tema).
3. **Resume** cada matéria a partir da descrição do próprio feed RSS.
4. **Puxa o painel macro BR**:
   - **Banco Central (SGS)**: Selic, CDI, IPCA (mês e 12m), USD/BRL, IGP-M — com histórico de ~24 meses.
   - **Yahoo Finance** (`yfinance`): Ibovespa e IFIX.
5. **Gera um HTML** estilizado e autossuficiente em `./briefings/briefing_AAAA-MM-DD.html` e o abre no navegador.

### Temas monitorados

- 🏭 Real Estate Logístico/Industrial (galpões, BTS, cap rate, vacância, absorção líquida)
- 📈 FIIs de Logística e IFIX
- 🚚 Logística, Transporte e Supply Chain
- 💹 Macroeconomia BR
- 🤝 M&A, Private Equity e Investimentos
- 🏢 Players e Concorrentes (Prologis, GLP, LOG CP, Bresco, Barzel, VBI, JLL, Cushman…)
- 🌍 Notícias Globais (política e relações internacionais)

---

## 🚀 Instalação e uso

### Requisitos

- Python **3.11+**

### Dependências

O script tenta instalar as dependências automaticamente na primeira execução. Se preferir instalar manualmente:

```bash
pip install feedparser requests pandas yfinance beautifulsoup4
```

> `beautifulsoup4` é usado apenas para limpar HTML das descrições dos feeds. `yfinance` é opcional — sem ele, os índices de bolsa são apenas omitidos.

### Execução

```bash
python news_briefing.py
```

O relatório é salvo em `./briefings/` e aberto automaticamente no navegador padrão.

### Flags de linha de comando

| Flag | Efeito |
| --- | --- |
| `--force` | Regenera o briefing mesmo que o HTML de hoje já exista (ignora cache). |
| `--upgrade-deps` | Força a atualização das dependências antes de rodar. |

---

## ⚙️ Configuração

Os principais parâmetros ficam no topo do [news_briefing.py](news_briefing.py) e são fáceis de ajustar:

- `JANELA_HORAS` — janela temporal das notícias consideradas (padrão: 36h).
- `MAX_MANCHETES_POR_TEMA` — teto de itens exibidos por tema (padrão: 8).
- `RETENCAO_DIAS` — por quantos dias manter cache e relatórios antigos (padrão: 3).
- `TEMAS` — dicionário de temas, cada um com suas **keywords ponderadas** e **queries** para o Google News. É aqui que se ajusta o foco setorial.
- `FEEDS_DIRETOS` / `FEEDS_GLOBAIS` — fontes RSS.
- `SGS_SERIES` / `YF_INDICES` — séries macro e índices de bolsa.

---

## 📁 Estrutura

```text
Noticias/
├── news_briefing.py     # script principal (coleta → ranking → macro → HTML)
├── briefings/           # relatórios HTML gerados (+ cache em .cache/)
├── README.md
└── .vscode/             # configuração do interpretador para o Pylance
```

---

## 🧠 Ideias futuras

O objetivo de longo prazo é transformar o briefing de um agregador de manchetes em um **analista automatizado**. As frentes mais promissoras envolvem IA:

### 1. Resumo de notícias com IA (prioridade)

Hoje o "resumo" é apenas a descrição do próprio feed RSS. A evolução natural é usar um LLM (ex.: **Claude**) para:

- **Sínteses reais e coesas** de cada matéria, indo além do snippet do RSS.
- **Resumo executivo do dia** ("TL;DR") no topo do relatório, conectando as notícias entre si.
- **Análise de impacto setorial**: dado um conjunto de manchetes, gerar um parágrafo sobre o que isso significa para o mercado de galpões logísticos.
- **Deduplicação semântica**: usar embeddings para agrupar notícias que tratam do mesmo fato mas vêm de fontes diferentes (mais robusto que o dedup textual atual).

### 2. Classificação e ranking inteligentes

- Substituir (ou complementar) o ranking por contagem de keywords por **classificação semântica** via LLM/embeddings, entendendo relevância mesmo sem match exato de palavras.
- **Análise de sentimento** por notícia e por tema (mercado otimista/pessimista).

### 3. Distribuição e automação

- **Agendamento** (cron / Task Scheduler / GitHub Actions) para rodar toda manhã sem intervenção.

### 4. Contexto macro enriquecido

- **Comentário automático** sobre os indicadores ("Selic estável, IPCA em desaceleração…") gerado por IA.
- Alertas quando um indicador cruza um limite relevante (ex.: câmbio acima de X).

---

## ⚠️ Observações

- As fontes RSS e códigos de séries do SGS podem mudar; o script foi construído com **degradação graciosa** — falha em uma fonte não derruba as demais.
- Os códigos das séries do Banco Central estão documentados no próprio script e devem ser validados periodicamente no [portal do SGS](https://www3.bcb.gov.br/sgspub/).
- Este projeto é para **uso corporativo de inteligência de mercado**. Respeite os termos de uso das fontes consultadas.