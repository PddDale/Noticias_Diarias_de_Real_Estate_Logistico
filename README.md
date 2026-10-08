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

A cada execução, o script pergunta o **período das notícias** (24 h, 48 h, 1 semana ou personalizado) e, com IA configurada, se deve gerar também o **relatório-resumo em PDF**. Depois, o pipeline percorre 6 etapas:

1. **Coleta** manchetes de:
   - Feeds RSS diretos (Exame Invest, Money Times).
   - Feeds globais confiáveis (BBC, The Guardian, Al Jazeera, UN News, NPR, Deutsche Welle).
   - Google News RSS por tema e por veículo (Valor, InfoMoney, Brazil Journal, Reuters, AP…).
2. **Filtra** pelo período escolhido, **deduplica** notícias repetidas e **rankeia por relevância**: `score = relevância temática × peso da fonte × fator de atualidade`.
   - **Relevância temática:** keywords com peso por tema, casadas só como palavra inteira ("war" não casa com "software"). Keyword no título vale 1,5×.
   - **Peso da fonte (0,85–1,25):** segue critérios de credibilidade e transparência (apuração própria, padrões editoriais, correções, transparência de propriedade) e a especialização no tema. Nas matérias do Google News, o veículo real é extraído do feed.
   - **Atualidade:** bônus de até 1,40× para as mais recentes, que cai pela metade a cada metade do período escolhido. Matérias sem data valem 0,85×.
   - **Com IA configurada** (qualquer provedor), a IA define a ordem final dos 15 melhores de cada tema: impacto para o leitor, novidade, duplicatas do mesmo fato no fim.
3. **Resume** cada matéria a partir da descrição do próprio feed RSS.
4. **Puxa o painel macro BR**:
   - **Banco Central (SGS)**: Selic, CDI, IPCA (mês e 12m), USD/BRL, IGP-M — com histórico de ~24 meses.
   - **Yahoo Finance** (`yfinance`): Ibovespa e IFIX.
5. *(opcional, com IA configurada)* **Aprimora os resumos** das notícias exibidas, gera uma **análise de tendência** por indicador macro e, se pedido, um **relatório-resumo em PDF** — ver [🤖 Integração com IA](#-integração-com-ia-opcional) abaixo.
6. **Gera um HTML** autossuficiente, com fundo branco, em `./briefings/briefing_AAAA-MM-DD_<período>.html` (ex.: `briefing_2026-10-05_48h.html`) e o abre no navegador.

### Gráficos do painel macro

Ao clicar num indicador, abre-se o histórico (1, 3, 6, 12 e 24 meses) com dois modos:

- **Comparar** (padrão): arraste entre duas datas (ou toque com dois dedos no celular) para destacar a área entre elas e ver a variação absoluta, a percentual, a direção (▲ verde / ▼ vermelho) e as datas. Para indicadores em % (Selic, CDI, IPCA, IGP-M), a variação aparece em **pontos percentuais (p.p.)**. Clique, `Esc` ou "✕ limpar seleção" removem a comparação.
- **Zoom**: arraste para ampliar um período personalizado.

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

O script cuida das dependências sozinho, no Python usado para rodá-lo:

- **Instala o que falta** a cada execução. Se o próprio `pip` não existir, ele é instalado com `ensurepip`.
- **Atualiza o que estiver desatualizado, uma vez por dia**: compara a versão instalada de cada dependência com a mais recente no PyPI e roda `pip install --upgrade` só nas desatualizadas. Isso vale para as dependências básicas e para as opcionais já instaladas (SDK de IA, `keyring`, `fpdf2`). Isso importa principalmente para o `yfinance`, que para de funcionar quando o Yahoo muda a API, e para os SDKs de IA. A data da última verificação fica em `deps_verificadas.json`, na pasta de configuração (`%APPDATA%\news_briefing\`).
- Dependências opcionais (SDK do provedor de IA, `keyring`, `fpdf2`) são instaladas **sob demanda**, só quando o recurso é usado.
- Fora de um venv, se a instalação falhar por permissão, o script tenta de novo com `--user`. Sem rede, a verificação é adiada para a próxima execução e o script segue normalmente.
- Para desligar tudo isso (ambiente já provisionado ou sem rede), defina `NEWS_BRIEFING_SKIP_PIP=1`.

Se preferir instalar manualmente:

```bash
pip install feedparser requests pandas yfinance beautifulsoup4 trafilatura
```

> `beautifulsoup4` é usado apenas para limpar HTML das descrições dos feeds. `trafilatura` extrai o texto das matérias que a IA resume; sem ele, os resumos usam só título e descrição. `yfinance` é opcional — sem ele, os índices de bolsa são apenas omitidos.

> Para habilitar os recursos de IA (resumos e análises — ver seção abaixo), instale também `pip install anthropic` e defina `ANTHROPIC_API_KEY`. Sem isso, o script roda normalmente do jeito que sempre rodou.

### Execução

```bash
python news_briefing.py
```

O relatório é salvo em `./briefings/` e aberto automaticamente no navegador padrão.

> Sem GPU no computador? Use a versão para Google Colab, que roda a IA local numa GPU T4 gratuita. Veja [☁️ Versão Google Colab](#️-versão-google-colab-gpu-t4--ia-local).

### Flags de linha de comando

| Flag | Efeito |
| --- | --- |
| `--periodo 48H` | Período das notícias sem perguntar: número + `H` (horas), `D` (dias) ou `S` (semanas), sem diferenciar maiúsculas e com espaço opcional (`12h`, `3 D`, `2s`). Máximo `4S`. |
| `--pdf` / `--sem-pdf` | Gera (ou não) o relatório-resumo em PDF sem perguntar. Exige IA. |
| `--reconfigurar-ia` | Reabre o menu de escolha do provedor/modelo de IA. |
| `--force` | Regenera o briefing (e o PDF) mesmo que já existam para o dia/período (ignora cache). |
| `--upgrade-deps` | Força a verificação de atualizações das dependências mesmo que ela já tenha rodado hoje. |

Sem flags, o script pergunta o período (Enter = 48 h) e, com IA, se deve gerar o PDF. Em execução sem terminal (ex.: Task Scheduler), as perguntas são puladas e valem os padrões (48 h, sem PDF).

O cache é **por dia e período**: rodar com 1 semana não reabre o HTML de 48 h do mesmo dia. Se o HTML do dia/período já existe e o PDF é pedido, o PDF é gerado a partir dos dados já coletados, sem refazer a coleta.

---

## ⚙️ Configuração

Os principais parâmetros ficam no topo do [news_briefing.py](news_briefing.py) e são fáceis de ajustar:

- `PERIODO_PADRAO_HORAS` / `PERIODO_MAX_HORAS` — período padrão do menu (48 h) e teto do período personalizado (4 semanas; os feeds RSS só trazem os itens mais recentes, então períodos maiores teriam cobertura rala). Acima de 48 h, as buscas do Google News ganham o operador `when:Xd`, e o log avisa quando as fontes não alcançam o início do período.
- `MAX_MANCHETES_POR_TEMA` — teto de itens exibidos por tema (padrão: 8).
- `PESOS_FONTE` — peso de cada veículo no ranking, por faixa: 1,25 (referência e agências), 1,15 (especializados e veículos globais), 0,85 (agregadores e press releases). Veículos não listados valem 1,0.
- `BONUS_ATUALIDADE_MAX` / `PENALIDADE_SEM_DATA` — bônus máximo por atualidade (0,40) e penalidade para matérias sem data (0,85).
- `REORDENAR_COM_IA` / `CANDIDATOS_REORDENACAO_IA` — liga ou desliga a reordenação por IA e define quantos candidatos por tema a IA avalia (15).
- `RETENCAO_DIAS` — por quantos dias manter cache e relatórios antigos (padrão: 3).
- `TEMAS` — dicionário de temas, cada um com suas **keywords ponderadas** e **queries** para o Google News. É aqui que se ajusta o foco setorial.
- `FEEDS_DIRETOS` / `FEEDS_GLOBAIS` — fontes RSS.
- `SGS_SERIES` / `YF_INDICES` — séries macro e índices de bolsa.
- `PROMPTS` / `PERFIL_LEITOR` / `CANAIS_INDICADOR` — os prompts das quatro tarefas de IA (resumo das matérias, análise de indicadores, reordenação por tema e resumo executivo do PDF), o perfil do leitor usado em todos eles e o canal de impacto de cada indicador no setor. Ajuste o tom e as regras da IA aqui.
- `CATALOGO_IA` — catálogo único de provedores e modelos de IA (pacote pip, variável de ambiente, modelo rápido, modelo padrão, tamanho do lote). Atualize nomes de modelos **só aqui**.

---

## 🤖 Integração com IA (opcional)

Com IA configurada, o script:

1. **Aprimora os resumos** das matérias exibidas no relatório (as mais importantes de cada tema, até `MAX_MANCHETES_POR_TEMA`), em lotes. Antes, baixa o **texto de cada matéria** (o link do Google News é convertido no link do veículo), e a IA escreve 3 a 5 frases com o fato, os números, os envolvidos e o contexto. Quando a página não abre (paywall, bloqueio), o resumo fica curto, só com o que o título e a descrição informam. O texto vai até `TEXTO_MAX_CHARS` caracteres por matéria (1.500 no Ollama, via `texto_max` no `CATALOGO_IA`).
2. Gera uma **análise de tendência por indicador**, exibida ao clicar num card do painel macro.
3. Gera, se pedido, o **relatório-resumo em PDF**: um parágrafo de visão geral, destaques por tema com links clicáveis para as fontes e um snapshot do painel macro. O PDF fica ao lado do HTML, com o mesmo nome, e o rodapé do HTML ganha um link discreto para ele. Sem o PDF pedido, o link não aparece (e é removido de um HTML do mesmo dia reaproveitado do cache).

### Provedores

Na primeira execução (ou com `--reconfigurar-ia`), um menu numerado oferece:

| Opção | Modelo dos resumos/análises | Modelo do PDF |
| --- | --- | --- |
| Anthropic (Claude) | `claude-sonnet-5-5` | `claude-sonnet-5-5` |
| OpenAI | `gpt-6-luna` | `gpt-6.1-sol` |
| Google Gemini | `gemini-3.5-flash-lite` | `gemini-3.8-flash` |
| Local via Ollama (Llama) | modelo baixado: `llama3.2:1b` (~4 GB RAM), `llama3.2:3b` (~8 GB RAM / 4 GB VRAM) ou `llama3.1:8b` (~16 GB RAM / 8 GB VRAM) | o mesmo |
| Sem IA | — | — (PDF indisponível) |

- **Nuvem**: o SDK do provedor é instalado automaticamente. A API key é pedida com entrada oculta e validada com uma chamada mínima antes de ser salva. Ela vai para o **cofre de credenciais do sistema** (`keyring`). Se o cofre não estiver disponível, fica no config, com aviso.
- **Ollama**: o script verifica se o Ollama está rodando em `http://localhost:11434` e, se estiver instalado mas parado, inicia `ollama serve` em segundo plano. Se o modelo ainda não foi baixado, roda `ollama pull` mostrando o progresso. Sem Ollama instalado, mostra como instalar (`winget install Ollama.Ollama`) e segue sem IA nessa execução. Os lotes de resumo são menores (5 matérias) por causa da janela de contexto dos modelos locais.
- A escolha fica em `%APPDATA%\news_briefing\config.json` (Linux: `~/.config/news_briefing/`; Mac: `~/Library/Application Support/news_briefing/`), **fora** de `briefings/.cache`, que é limpa periodicamente.
- Variáveis de ambiente já definidas (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY`) **têm prioridade** sobre a chave salva. Quem já usava `ANTHROPIC_API_KEY` continua com a Anthropic sem ver o menu.
- Se um modelo "rápido" for descontinuado (erro de modelo não encontrado), o script usa o modelo "padrão" do provedor e avisa no log para atualizar o `CATALOGO_IA`.

Sem IA, o script roda exatamente como antes: resumo a partir da descrição do RSS, sem análise de IA nos indicadores e sem PDF. Nenhuma chamada extra é feita e nada quebra. Falhas de IA ou de rede nunca derrubam o script: cada etapa volta ao comportamento sem IA.

### Retomada após falha (checkpoint de IA)

Chamadas de IA custam tempo e dinheiro, então o progresso é salvo incrementalmente em `./briefings/.cache/checkpoint_ia_AAAA-MM-DD.json` a cada lote de resumos e a cada indicador analisado. Se a execução for interrompida no meio (queda de rede, processo encerrado etc.), a **próxima execução no mesmo dia** recupera do checkpoint o que já foi gerado e chama a IA apenas para o que falta — em vez de reprocessar (e pagar) tudo de novo. Isso também acelera o `--force` no mesmo dia.

Checkpoints de dias anteriores são descartados automaticamente no início de cada execução (não seguem a retenção de `RETENCAO_DIAS`, já que só fazem sentido dentro do dia corrente).

---

## ☁️ Versão Google Colab (GPU T4 + IA local)

O [news_briefing_colab.ipynb](news_briefing_colab.ipynb) é uma versão alternativa para quem não tem GPU no computador. Ele roda no Google Colab com uma **GPU NVIDIA T4** e usa **somente um modelo de IA local (Ollama) na própria GPU** para gerar os resumos, as análises dos indicadores e o PDF, sem custo de API. O pipeline é o mesmo do `news_briefing.py`: coleta, ranking, painel macro, HTML/PDF, nomes dos arquivos, cache diário em `briefings/.cache/`, checkpoint de IA e limpeza de relatórios antigos (`RETENCAO_DIAS`). Ele roda **sempre no Colab** (no navegador ou pela extensão do Colab no VS Code); para rodar no próprio computador, use o `news_briefing.py`.

### Como usar

1. Abra o notebook no Colab (`Arquivo › Fazer upload de notebook`) ou no VS Code com o kernel do Colab. Ele já pede o ambiente **T4 GPU**. Se não pedir: `Ambiente de execução › Alterar o tipo de ambiente de execução › T4 GPU`.
2. Execute todas as células (`Ambiente de execução › Executar tudo`, Ctrl+F9).
3. Responda às perguntas da célula **⚙️ Configurações**. Cada pergunta aparece inteira, com as opções, no próprio campo de entrada (Enter = valor entre colchetes):
   - *"Usar as configurações atuais (período · modelo · PDF)?"*: **Enter** aceita. **`n`** pergunta o período (24 h / 48 h / 1 semana / personalizado), o modelo local e se deve gerar o PDF.
   - As respostas valem durante a sessão do Colab.
4. Se o briefing do dia para o período escolhido já existir, a célula **▶️ Gerar briefing** pergunta se deve gerá-lo de novo (equivale ao `--force`).

Sem interação (execução automatizada), todas as perguntas assumem o padrão.

Cada etapa mostra uma **barra de progresso** que se atualiza no lugar: dependências, Ollama, download do modelo (em GB), coleta das fontes, ordenação e resumos por IA, painel macro, análise dos indicadores, PDF e download dos arquivos, além de uma barra geral do briefing.

### Onde os arquivos são salvos

O HTML (e o PDF, se pedido) é salvo em `/content/news_briefing/briefings/`, no padrão `briefing_AAAA-MM-DD_<período>.html/.pdf`, com os metadados e as manchetes da execução em `briefings/.cache/`. Relatórios e cache com mais de `RETENCAO_DIAS` dias são apagados ao fim de cada execução, e checkpoints de IA de dias anteriores, no início.

Essa pasta é apagada quando a sessão do Colab termina. Por isso a célula **⬇️ Baixar os arquivos** baixa o HTML/PDF automaticamente para a pasta de downloads do navegador e também mostra links de download, que funcionam com um clique caso o download automático não esteja disponível.

O Colab não tem acesso ao disco do computador. Para levar os arquivos de Downloads para a pasta `briefings/` do projeto, rode no PC o [mover_downloads.py](mover_downloads.py):

```bash
python mover_downloads.py            # move o que já foi baixado
python mover_downloads.py --vigiar   # fica 30 min esperando os downloads e move ao chegar
```

Ele só mexe em `briefing_AAAA-MM-DD_<período>.html/.pdf`, e cópias renomeadas pelo navegador (`... (1).html`) substituem a versão anterior.

### Modelos locais escolhidos para a T4

A T4 tem **15 GB de VRAM** e o runtime do Colab tem ~12 GB de RAM. Para o modelo rodar rápido, os pesos **e** o cache da janela de contexto (até 32k tokens) precisam caber inteiros na VRAM. Por isso o menu oferece:

| Modelo | Download | Perfil |
| --- | --- | --- |
| `gemma4:12b` **(padrão)** | ~8 GB | Melhor equilíbrio entre qualidade e velocidade na T4. |
| `qwen3:14b` | 9,3 GB | O maior que cabe inteiro na T4; um pouco mais lento. |
| `gemma4:e4b` | 6,6-9,5 GB | O mais rápido; resumos mais simples. Também é o indicado se o notebook rodar sem GPU. |
| `llama3.1:8b` | 4,9 GB | Alternativa leve. |

Ficam de fora `gemma4:26b`/`31b` e `qwen3:30b`/`32b` (16-20 GB): não cabem na T4, e a parte que transbordasse para a CPU deixaria cada chamada várias vezes mais lenta. A opção *"outro"* aceita qualquer tag do [ollama.com/library](https://ollama.com/library). A lista fica em `MODELOS_T4`, na célula ⚙️ Configurações.

Ajustes específicos do Colab:

- O `ollama serve` sobe com **flash attention** e **cache de contexto em 8 bits** (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`), com um modelo e um pedido por vez. Isso reduz pela metade a VRAM da janela de 32k e é o que faz modelos de 12-14B caberem inteiros.
- Depois do download, o modelo é carregado na GPU (aquecimento), e o notebook avisa se ele não coube inteiro na VRAM.
- Em modelos com raciocínio (*thinking*, como o Qwen 3), o raciocínio é desligado nas chamadas, para que a resposta venha direto no JSON esperado.
- Lotes de resumo de 6 matérias (5 no script local), com até 3.000 caracteres do texto de cada matéria, porque a T4 comporta uma janela de contexto maior.
- **Banco Central no Colab:** os servidores do Colab ficam fora do Brasil, e a API do BCB costuma segurar ou recusar essas conexões (timeout, erro 400/502, página de bloqueio no lugar do JSON). Por isso, no notebook, cada endereço do BCB é tentado uma vez só (timeout de 12 s) e, depois de 2 falhas seguidas (`BCB_MAX_FALHAS`), o BCB é pulado no resto da execução. Entram os fallbacks: IBGE/SIDRA para o IPCA (mensal e 12 meses, com histórico), BrasilAPI para Selic/CDI e AwesomeAPI para o dólar. O IGP-M não tem fallback e pode sair "—".

### Limitações

- O runtime do Colab é descartável: o Ollama e o modelo são baixados de novo a cada sessão (~3-6 min). No plano gratuito, a sessão cai após um tempo ocioso e o uso da GPU tem cota.
- Pela extensão do Colab no VS Code, o download automático pode não estar disponível. Nesse caso, use os links de download da célula ⬇️.
- O instalador do Ollama avisa `WARNING: systemd is not running`: o Colab não usa o systemd, então o serviço automático do Ollama não é criado e o notebook inicia o `ollama serve` por conta própria. O aviso pode ser ignorado.

---

## 📁 Estrutura

```text
Noticias/
├── news_briefing.py     # script principal (coleta → ranking → macro → HTML)
├── news_briefing_colab.ipynb  # versão Google Colab (GPU T4 + IA local via Ollama)
├── briefings/           # relatórios HTML e PDF (briefing_AAAA-MM-DD_<período>.html/.pdf)
│   └── .cache/          # metadados, dados para o PDF (dados_*.json) e checkpoint de IA
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