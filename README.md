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

A cada execução, o pipeline percorre 6 etapas:

1. **Coleta** manchetes de:
   - Feeds RSS diretos (Exame Invest, Money Times).
   - Feeds globais confiáveis (BBC, The Guardian, Al Jazeera, UN News, NPR, Deutsche Welle).
   - Google News RSS por tema e por veículo (Valor, InfoMoney, Brazil Journal, Reuters, AP…).
2. **Filtra** pelas últimas 24–36h, **deduplica** notícias repetidas e **rankeia por relevância** (peso de keywords por tema).
3. **Resume** cada matéria a partir da descrição do próprio feed RSS.
4. **Puxa o painel macro BR**:
   - **Banco Central (SGS)**: Selic, CDI, IPCA (mês e 12m), USD/BRL, IGP-M — com histórico de ~24 meses.
   - **Yahoo Finance** (`yfinance`): Ibovespa e IFIX.
5. *(opcional, com IA habilitada)* **Aprimora os resumos** das notícias e gera uma **análise de tendência** por indicador macro — ver [🤖 Integração com IA](#-integração-com-ia-opcional) abaixo.
6. **Gera um HTML** estilizado e autossuficiente em `./briefings/briefing_AAAA-MM-DD.html` e o abre no navegador.

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

> Para habilitar os recursos de IA (resumos e análises — ver seção abaixo), instale também `pip install anthropic` e defina `ANTHROPIC_API_KEY`. Sem isso, o script roda normalmente do jeito que sempre rodou.

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
- `IA_MODELO` / `TAMANHO_LOTE_IA` — modelo da Anthropic usado e tamanho do lote de resumos (ver seção de IA abaixo).

---

## 🤖 Integração com IA (opcional)

O script pode usar a **API da Anthropic (Claude Haiku)** para dois recursos, ambos **desligados por padrão**:

1. **Resumos de notícias aprimorados** — em vez de só truncar a descrição do RSS, um resumo de ~2 frases é gerado por IA a partir do título + descrição de cada matéria (em lote, para eficiência).
2. **Análise de tendência por indicador** — ao clicar em um card do painel macro (Selic, IPCA, câmbio, Ibovespa, IFIX…), o modal de histórico exibe uma análise curta gerada por IA sobre a tendência recente e o que ela pode sinalizar para o mercado de real estate logístico.

### Como habilitar

```bash
pip install anthropic
```

```powershell
# Windows (PowerShell) — só a sessão atual:
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Windows — persiste entre sessões:
setx ANTHROPIC_API_KEY "sk-ant-..."
```

```bash
# Linux/Mac:
export ANTHROPIC_API_KEY="sk-ant-..."
```

Sem a variável de ambiente definida, o script roda exatamente como antes (resumo a partir do RSS, sem análise de IA nos indicadores) — nenhuma chamada extra é feita e nada quebra.

### Retomada após falha (checkpoint de IA)

Chamadas de IA custam tempo e dinheiro, então o progresso é salvo incrementalmente em `./briefings/.cache/checkpoint_ia_AAAA-MM-DD.json` a cada lote de resumos e a cada indicador analisado. Se a execução for interrompida no meio (queda de rede, processo encerrado etc.), a **próxima execução no mesmo dia** recupera do checkpoint o que já foi gerado e chama a IA apenas para o que falta — em vez de reprocessar (e pagar) tudo de novo. Isso também acelera o `--force` no mesmo dia.

Checkpoints de dias anteriores são descartados automaticamente no início de cada execução (não seguem a retenção de `RETENCAO_DIAS`, já que só fazem sentido dentro do dia corrente).

---

## 📁 Estrutura

```text
Noticias/
├── news_briefing.py     # script principal (coleta → ranking → macro → HTML)
├── briefings/           # relatórios HTML gerados
│   └── .cache/          # cache diário + checkpoint de IA (checkpoint_ia_AAAA-MM-DD.json)
├── README.md
└── .vscode/             # configuração do interpretador para o Pylance
```

---

## 🧠 Ideias futuras

O objetivo de longo prazo é transformar o briefing de um agregador de manchetes em um **analista automatizado**. Com o resumo de notícias e a análise por indicador já implementados via IA (ver seção acima), as próximas frentes são:

### 1. Síntese e contexto macro mais ricos

- **Resumo executivo do dia** ("TL;DR") no topo do relatório, conectando as notícias entre si em vez de tratá-las isoladamente.
- **Análise de impacto setorial**: dado o conjunto de manchetes do dia, gerar um parágrafo sobre o que isso significa para o mercado de galpões logísticos.
- **Alertas** quando um indicador cruza um limite relevante (ex.: câmbio acima de X).

### 2. Deduplicação e ranking semânticos

- **Deduplicação semântica** via embeddings, para agrupar notícias que tratam do mesmo fato mas vêm de fontes diferentes (mais robusto que o dedup textual/hash atual).
- Substituir (ou complementar) o ranking por contagem de keywords por **classificação semântica** via LLM/embeddings, entendendo relevância mesmo sem match exato de palavras.
- **Análise de sentimento** por notícia e por tema (mercado otimista/pessimista).

### 3. Distribuição e automação

- **Agendamento** (cron / Task Scheduler / GitHub Actions) para rodar toda manhã sem intervenção.

---

## ⚠️ Observações

- As fontes RSS e códigos de séries do SGS podem mudar; o script foi construído com **degradação graciosa** — falha em uma fonte não derruba as demais.
- Os códigos das séries do Banco Central estão documentados no próprio script e devem ser validados periodicamente no [portal do SGS](https://www3.bcb.gov.br/sgspub/).
- Este projeto é para **uso corporativo de inteligência de mercado**. Respeite os termos de uso das fontes consultadas.