# -*- coding: utf-8 -*-
"""
news_briefing.py
================
Briefing diário automatizado de notícias + painel macroeconômico BR,
voltado para inteligência de mercado em real estate logístico/industrial,
com uma seção de notícias globais (política e relações internacionais).

Ambiente-alvo: Python 3.11+

A cada execução o script:
  1. Coleta manchetes de feeds RSS (veículos econômicos BR + fontes globais
     confiáveis + Google News RSS por tema).
  2. Filtra pelas últimas 24-36h, deduplica e rankeia por relevância (peso de keywords).
  3. Resume cada matéria a partir da descrição do próprio feed RSS.
  4. Puxa painel macro BR (BCB/SGS: Selic, CDI, IPCA, câmbio, IGP-M; yfinance: Ibovespa, IFIX).
  5. Gera um HTML estilizado e autossuficiente em ./briefings/briefing_AAAA-MM-DD.html.

---------------------------------------------------------------------------
INSTALAÇÃO DAS DEPENDÊNCIAS (rodar uma vez no terminal / venv):

    pip install feedparser requests pandas yfinance beautifulsoup4

Observações:
  - 'beautifulsoup4' é usado apenas para limpar HTML das descrições dos feeds.
  - 'yfinance' é opcional: sem a lib, os índices de bolsa são omitidos.
---------------------------------------------------------------------------
"""

from __future__ import annotations

import os
import re
import sys
import json
import time
import html
import hashlib
import logging
import datetime as dt
import importlib.util
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

# =============================================================================
# 0. BOOTSTRAP DE DEPENDÊNCIAS
# =============================================================================
# Pacotes necessários: (nome do módulo importado, nome do pacote no pip).
_PACOTES_NECESSARIOS = [
    ("feedparser", "feedparser"),
    ("requests", "requests"),
    ("pandas", "pandas"),
    ("yfinance", "yfinance"),
    ("bs4", "beautifulsoup4"),
]


def _garantir_dependencias(forcar_upgrade: bool = False) -> None:
    """Instala automaticamente os pacotes ausentes via pip. Com `forcar_upgrade=True`
    (flag --upgrade-deps), também atualiza os já instalados para a versão mais recente.

    Roda em toda execução, mas só dispara o pip quando falta algo (ou quando o
    upgrade é pedido explicitamente) para não exigir rede/tempo extra num
    agendamento diário via Task Scheduler. Pode ser pulado com a variável de
    ambiente NEWS_BRIEFING_SKIP_PIP=1 (ex.: ambiente já provisionado/sem rede)."""
    if os.environ.get("NEWS_BRIEFING_SKIP_PIP", "").strip() == "1":
        return

    faltando = [pacote for modulo, pacote in _PACOTES_NECESSARIOS
                if importlib.util.find_spec(modulo) is None]

    alvo = [pacote for _, pacote in _PACOTES_NECESSARIOS] if forcar_upgrade else faltando
    if not alvo:
        return

    acao = "Atualizando" if forcar_upgrade else "Instalando dependências ausentes"
    print(f"[setup] {acao}: {', '.join(alvo)} …")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", *alvo])
        print("[setup] Dependências OK.")
    except Exception as e:
        print(f"[setup] AVISO: falha ao instalar/atualizar automaticamente ({str(e)[:200]}). "
              f"Instale manualmente: pip install {' '.join(alvo)}")


_garantir_dependencias(forcar_upgrade="--upgrade-deps" in sys.argv)

# ---- Dependências de terceiros (com degradação graciosa) --------------------
try:
    import requests
except ImportError:
    print("ERRO: instale as dependências -> pip install feedparser requests pandas yfinance beautifulsoup4")
    raise

try:
    import feedparser
except ImportError:
    print("ERRO: 'feedparser' ausente -> pip install feedparser")
    raise

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore[assignment]

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore[assignment]

# 'pandas' é carregado sob demanda (lazy) via yfinance mais abaixo.


# =============================================================================
# 1. CONFIGURAÇÃO
# =============================================================================

# --- Janela temporal e caminhos ---------------------------------------------
JANELA_HORAS = 36                      # considerar notícias das últimas N horas
MAX_MANCHETES_POR_TEMA = 8             # teto de itens exibidos por tema no HTML
PASTA_SAIDA = Path(__file__).resolve().parent / "briefings"
PASTA_CACHE = PASTA_SAIDA / ".cache"
RETENCAO_DIAS = 3                      # apaga cache/relatórios mais antigos que N dias

# --- Rede: timeouts e retry --------------------------------------------------
HTTP_TIMEOUT = 12                      # segundos por requisição
HTTP_RETRIES = 3                       # tentativas extras em caso de falha
HTTP_BACKOFF = 2.0                     # fator de backoff exponencial
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36 NewsBriefing/1.0")

# A API do BCB (WAF do gov.br) rejeita com 400 requisições que se passam por
# navegador sem os demais headers de browser. Usamos User-Agent "honesto" +
# Accept JSON, e um timeout maior porque o SGS costuma ser lento.
BCB_HEADERS = {"User-Agent": "news-briefing/1.0 (+requests)", "Accept": "application/json"}
BCB_TIMEOUT = 30                       # segundos (SGS é lento)
BCB_PAUSA = 0.4                        # pausa entre séries p/ não parecer flood


# --- Temas de relevância -----------------------------------------------------
# Cada tema tem: (a) rótulo exibido, (b) keywords com peso, (c) queries p/ Google News.
# O peso multiplica a contagem da keyword no ranking de relevância.
TEMAS: dict[str, dict] = {
    "Real Estate Logístico/Industrial": {
        "keywords": {
            "galpão": 3, "galpões": 3, "condomínio logístico": 4, "condomínios logísticos": 4,
            "built to suit": 4, "bts": 3, "cross-docking": 4, "cross docking": 4,
            "last mile": 3, "última milha": 3, "vacância": 3, "cap rate": 4,
            "absorção líquida": 4, "absorção": 2, "galpão logístico": 4,
            "imóvel logístico": 3, "imóveis logísticos": 3, "industrial": 2,
            "condomínio industrial": 4, "estoque logístico": 3,
        },
        "queries": [
            "galpão logístico Brasil",
            "condomínio logístico vacância cap rate",
            "built to suit galpão",
            "absorção líquida galpões logísticos",
        ],
    },
    "FIIs de Logística e IFIX": {
        "keywords": {
            "fii": 3, "fiis": 3, "fundo imobiliário": 3, "fundos imobiliários": 3,
            "ifix": 4, "fii logístico": 4, "fii de logística": 4, "dividendos fii": 3,
            "cotas": 2, "renda imobiliária": 2,
        },
        "queries": [
            "FII logística IFIX",
            "fundos imobiliários logísticos dividendos",
        ],
    },
    "Logística, Transporte e Supply Chain": {
        "keywords": {
            "logística": 2, "transporte": 2, "cadeia de suprimentos": 3, "supply chain": 3,
            "e-commerce": 3, "ecommerce": 3, "fulfillment": 3, "operador logístico": 3,
            "frete": 2, "distribuição": 2, "armazém": 3, "armazenagem": 3,
        },
        "queries": [
            "logística e-commerce Brasil",
            "cadeia de suprimentos supply chain Brasil",
        ],
    },
    "Macroeconomia BR": {
        "keywords": {
            "selic": 3, "ipca": 3, "inflação": 2, "pib": 3, "câmbio": 2, "dólar": 2,
            "juros": 2, "copom": 3, "atividade econômica": 3, "banco central": 2,
            "igp-m": 3, "cdi": 2,
        },
        "queries": [
            "Selic Copom decisão juros",
            "IPCA inflação Brasil",
            "PIB atividade econômica Brasil",
            "câmbio dólar real",
        ],
    },
    "M&A, Private Equity e Investimentos": {
        "keywords": {
            "m&a": 4, "fusão": 3, "aquisição": 3, "private equity": 4, "fundo de investimento": 2,
            "aporte": 2, "captação": 2, "investimento imobiliário": 3, "real estate": 2,
            "joint venture": 3, "portfólio": 2,
        },
        "queries": [
            "M&A real estate Brasil",
            "private equity investimento imobiliário Brasil",
            "aquisição galpões logísticos",
        ],
    },
    "Players e Concorrentes": {
        "keywords": {
            "prologis": 5, "glp": 5, "log cp": 5, "log commercial": 5, "bresco": 5,
            "barzel": 5, "vbi": 5, "siila": 5, "jll": 4, "cushman": 4, "wakefield": 4,
            "cushman & wakefield": 5,
        },
        "queries": [
            "LOG CP galpões",
            "Bresco Barzel VBI logística",
            "Prologis GLP Brasil",
            "SiiLA JLL Cushman Wakefield logística",
        ],
    },
    "Notícias Globais (Política e Relações Internacionais)": {
        "keywords": {
            "geopolítica": 4, "geopolitics": 4, "relações internacionais": 4,
            "international relations": 4, "diplomacia": 3, "diplomacy": 3,
            "eleições": 3, "election": 3, "guerra": 3, "war": 3, "conflito": 3,
            "conflict": 3, "sanções": 3, "sanctions": 3, "cúpula": 2, "summit": 2,
            "tratado": 3, "treaty": 3, "cessar-fogo": 3, "ceasefire": 3,
            "tarifas": 3, "tariffs": 3, "comércio internacional": 3,
            "united nations": 3, "onu": 3, "nato": 3, "otan": 3, "união europeia": 3,
            "european union": 3, "china": 2, "estados unidos": 2, "united states": 2,
            "rússia": 2, "russia": 2, "ucrânia": 3, "ukraine": 3,
            "oriente médio": 3, "middle east": 3,
        },
        "queries": [
            "geopolitics international relations",
            "global politics diplomacy summit",
            "international sanctions trade tariffs",
            "geopolítica relações internacionais",
        ],
    },
}

# --- Feeds RSS diretos (veículos econômicos BR) ------------------------------
# Observação: URLs de RSS mudam com o tempo. O script trata falha por fonte;
# uma fonte fora do ar não derruba o restante. Ajuste/adicione conforme necessário.
# InfoMoney e Exame/Economia foram movidos para o Google News (via site:) porque
# os feeds diretos passaram a bloquear robôs (SSL/anti-bot) e a URL /economia/feed
# retornava 404. O Google News cobre esses veículos de forma estável.
# Brazil Journal também foi movido (SSLError persistente no feed direto, não é
# falha transitória de rede -> retry não resolve).
FEEDS_DIRETOS: list[tuple[str, str]] = [
    ("Exame - Invest",           "https://exame.com/invest/feed/"),
    ("Money Times - Mercados",   "https://www.moneytimes.com.br/mercados/feed/"),
]

# --- Feeds globais confiáveis (política e relações internacionais) -----------
# Veículos internacionais de reputação estabelecida, com feeds RSS públicos e
# editorias de mundo/política. O filtro temático + ranking por keywords se
# encarrega de priorizar as manchetes de política e geopolítica.
FEEDS_GLOBAIS: list[tuple[str, str]] = [
    ("BBC News - World",         "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("The Guardian - World",     "https://www.theguardian.com/world/rss"),
    ("Al Jazeera - All",         "https://www.aljazeera.com/xml/rss/all.xml"),
    ("UN News",                  "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
    ("NPR - World",              "https://feeds.npr.org/1004/rss.xml"),
    ("Deutsche Welle - World",   "https://rss.dw.com/rdf/rss-en-world"),
]

# --- Google News RSS ---------------------------------------------------------
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

# Veículos consultados via Google News (feed próprio restrito/instável).
# Cada entrada vira uma query site: filtrada pelos temas de interesse.
FILTRO_TEMAS_SITE = '(logística OR galpão OR "fundo imobiliário" OR Selic OR IPCA OR imobiliário)'
VEICULOS_VIA_GOOGLE = {
    "Valor (Google News)":         "valor.globo.com",
    "InfoMoney (Google News)":     "infomoney.com.br",
    "Exame (Google News)":         "exame.com",
    "Brazil Journal (Google News)": "braziljournal.com",
}

# Fontes globais confiáveis sem RSS público estável (ex.: Reuters, AP) são
# consultadas via Google News com filtro de política/relações internacionais.
FILTRO_GLOBAL_SITE = ('(politics OR geopolitics OR "international relations" OR '
                      'diplomacy OR election OR sanctions OR war OR conflict OR summit)')
VEICULOS_GLOBAIS_VIA_GOOGLE = {
    "Reuters (Google News)":       "reuters.com",
    "Associated Press (Google News)": "apnews.com",
}


# --- Séries do SGS / Banco Central -------------------------------------------
# IMPORTANTE: valide os códigos no portal do SGS antes de uso prolongado:
#   https://www3.bcb.gov.br/sgspub/
# Endpoint por série (últimos N valores):
#   https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json
#
# Códigos usados (referência confirmada no SGS):
#   432   -> Meta Selic definida pelo Copom (% a.a.)
#   4389  -> Taxa de juros - CDI anualizada base 252 (% a.a., diária)
#            OBS: o código 12 é a taxa DIÁRIA do CDI (ex.: 0,05% ao dia) e não é
#            comparável à Selic meta -> era a causa do valor de CDI aparecer errado.
#   433   -> IPCA - variação mensal (%)
#   13522 -> IPCA - acumulado em 12 meses (%)
#   1     -> Taxa de câmbio - Dólar americano (venda) - diária (R$/US$)
#   10813 -> Taxa de câmbio - Dólar americano (compra) - diária (R$/US$)
#   189   -> IGP-M - variação mensal (%)
SGS_SERIES: dict[str, dict] = {
    "Selic (meta a.a.)":      {"codigo": 432,   "sufixo": "%",  "casas": 2, "periodicidade": "diaria"},
    "CDI (a.a.)":             {"codigo": 4389,  "sufixo": "%",  "casas": 2, "periodicidade": "diaria"},
    "IPCA (mês)":             {"codigo": 433,   "sufixo": "%",  "casas": 2, "periodicidade": "mensal"},
    "IPCA (12m acum.)":       {"codigo": 13522, "sufixo": "%",  "casas": 2, "periodicidade": "mensal"},
    "USD/BRL (compra)":       {"codigo": 10813, "sufixo": "R$", "casas": 2, "periodicidade": "diaria"},
    "USD/BRL (venda)":        {"codigo": 1,     "sufixo": "R$", "casas": 2, "periodicidade": "diaria"},
    "IGP-M (mês)":            {"codigo": 189,   "sufixo": "%",  "casas": 2, "periodicidade": "mensal"},
}

# Quantos pontos históricos puxar por periodicidade para cobrir ~24 meses de gráfico.
N_HISTORICO = {"diaria": 560, "mensal": 26}

# --- Índices via yfinance ----------------------------------------------------
YF_INDICES: dict[str, str] = {
    "Ibovespa": "^BVSP",
    "IFIX":     "IFIX.SA",   # nem sempre disponível no Yahoo; tratado com fallback
}


# =============================================================================
# 2. LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("briefing")


# =============================================================================
# 3. ESTRUTURAS DE DADOS
# =============================================================================
@dataclass
class Materia:
    titulo: str
    url: str
    fonte: str
    publicado: dt.datetime | None
    descricao: str = ""
    tema: str = ""
    score: float = 0.0
    resumo: str = ""

    @property
    def chave(self) -> str:
        """Chave de deduplicação baseada no título normalizado."""
        base = re.sub(r"\W+", "", self.titulo.lower())[:80]
        return hashlib.md5(base.encode("utf-8")).hexdigest()


# =============================================================================
# 4. UTILIDADES DE REDE (timeout + retry)
# =============================================================================
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})


def http_get(url: str, timeout: int = HTTP_TIMEOUT,
             headers: dict | None = None) -> requests.Response | None:
    """GET com retry e backoff exponencial. Retorna None em caso de falha final.

    `headers`, quando informado, é mesclado por requisição (sobrepõe os da sessão).
    Útil p/ fontes que exigem User-Agent/Accept específicos (ex.: API do BCB)."""
    for tentativa in range(HTTP_RETRIES + 1):
        try:
            resp = _session.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            return resp
        except Exception as e:
            espera = HTTP_BACKOFF ** tentativa
            if tentativa < HTTP_RETRIES:
                log.warning("  GET falhou (tentativa %d): %s | retry em %.1fs",
                            tentativa + 1, str(e)[:120], espera)
                time.sleep(espera)
            else:
                log.error("  GET desistiu: %s | %s", url[:80], str(e)[:120])
    return None


# =============================================================================
# 5. LIMPEZA DE TEXTO
# =============================================================================
def limpar_html(texto: str) -> str:
    """Remove tags HTML e normaliza espaços de uma descrição de RSS."""
    if not texto:
        return ""
    if BeautifulSoup is not None:
        texto = BeautifulSoup(texto, "html.parser").get_text(" ")
    else:
        texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def truncar(texto: str, limite: int = 320) -> str:
    texto = texto.strip()
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0]
    return corte + "…"


# =============================================================================
# 6. COLETA DE FEEDS RSS
# =============================================================================
def _parse_data(entry) -> dt.datetime | None:
    """Extrai datetime (UTC-naive) de uma entry do feedparser."""
    for campo in ("published_parsed", "updated_parsed"):
        val = getattr(entry, campo, None)
        if val:
            try:
                return dt.datetime.fromtimestamp(time.mktime(val))
            except Exception:
                continue
    return None


def coletar_feed(nome_fonte: str, url: str) -> list[Materia]:
    """Baixa e parseia um único feed RSS. Isolado para falhar sem derrubar o resto."""
    materias: list[Materia] = []
    try:
        resp = http_get(url)
        if resp is None:
            return materias
        parsed = feedparser.parse(resp.content)
        for entry in parsed.entries:
            titulo = limpar_html(getattr(entry, "title", "")).strip()
            link = getattr(entry, "link", "").strip()
            if not titulo or not link:
                continue
            desc = limpar_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
            # Google News às vezes anexa a fonte no título após " - "
            fonte = nome_fonte
            materias.append(Materia(
                titulo=titulo, url=link, fonte=fonte,
                publicado=_parse_data(entry), descricao=desc,
            ))
        log.info("  [OK] %-28s %3d itens", nome_fonte, len(materias))
    except Exception as e:
        log.error("  [FALHA] %-25s %s", nome_fonte, str(e)[:120])
    return materias


def montar_urls_google_news() -> list[tuple[str, str]]:
    """Gera (nome_fonte, url) para cada query de cada tema + veículos via site:."""
    urls: list[tuple[str, str]] = []
    for tema, cfg in TEMAS.items():
        for q in cfg["queries"]:
            urls.append((f"Google News · {tema}", GOOGLE_NEWS_BASE.format(q=quote_plus(q))))
    # Veículos específicos filtrados pelos temas (Valor, InfoMoney, Exame…).
    for nome, dominio in VEICULOS_VIA_GOOGLE.items():
        q = f"site:{dominio} {FILTRO_TEMAS_SITE}"
        urls.append((nome, GOOGLE_NEWS_BASE.format(q=quote_plus(q))))
    # Fontes globais confiáveis filtradas por política/relações internacionais.
    for nome, dominio in VEICULOS_GLOBAIS_VIA_GOOGLE.items():
        q = f"site:{dominio} {FILTRO_GLOBAL_SITE}"
        urls.append((nome, GOOGLE_NEWS_BASE.format(q=quote_plus(q))))
    return urls


def coletar_todas_as_fontes() -> list[Materia]:
    """Coleta feeds diretos + Google News em paralelo (I/O bound)."""
    tarefas: list[tuple[str, str]] = []

    # Feeds diretos (ignora entradas com URL None -> tratadas via Google News)
    for nome, url in FEEDS_DIRETOS + FEEDS_GLOBAIS:
        if url:
            tarefas.append((nome, url))

    # Google News por tema
    tarefas.extend(montar_urls_google_news())

    log.info("Coletando %d fontes RSS (paralelo)…", len(tarefas))
    resultado: list[Materia] = []
    # I/O bound -> threads. Limite conservador para não estourar rede/limites.
    # (reduzido de 8 p/ 5: muitas tarefas batem no mesmo host news.google.com em
    # rajada, e o Google rate-limita/derruba conexões concorrentes do mesmo IP.)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futuros = {executor.submit(coletar_feed, nome, url): nome for nome, url in tarefas}
        for fut in as_completed(futuros):
            try:
                resultado.extend(fut.result())
            except Exception as e:
                log.error("  Erro em fonte %s: %s", futuros[fut], str(e)[:120])
    return resultado


# =============================================================================
# 7. FILTRO TEMPORAL + DEDUPLICAÇÃO
# =============================================================================
def filtrar_recentes(materias: list[Materia]) -> list[Materia]:
    limite = dt.datetime.now() - dt.timedelta(hours=JANELA_HORAS)
    recentes: list[Materia] = []
    sem_data = 0
    for m in materias:
        if m.publicado is None:
            # Sem data confiável: mantém, mas com leve penalização no score depois.
            recentes.append(m)
            sem_data += 1
        elif m.publicado >= limite:
            recentes.append(m)
    log.info("Filtro temporal (%dh): %d de %d itens (%d sem data)",
             JANELA_HORAS, len(recentes), len(materias), sem_data)
    return recentes


def deduplicar(materias: list[Materia]) -> list[Materia]:
    vistos_chave: set[str] = set()
    vistos_url: set[str] = set()
    unicas: list[Materia] = []
    for m in materias:
        url_norm = re.sub(r"[?#].*$", "", m.url.lower())
        if m.chave in vistos_chave or url_norm in vistos_url:
            continue
        vistos_chave.add(m.chave)
        vistos_url.add(url_norm)
        unicas.append(m)
    log.info("Deduplicação: %d itens únicos (de %d)", len(unicas), len(materias))
    return unicas


# =============================================================================
# 8. RANKING DE RELEVÂNCIA
# =============================================================================
def classificar_e_rankear(materias: list[Materia]) -> list[Materia]:
    """Atribui tema e score por peso de keywords em (título + descrição)."""
    relevantes: list[Materia] = []
    for m in materias:
        alvo = f"{m.titulo} {m.descricao}".lower()
        melhor_tema, melhor_score = "", 0.0
        score_total = 0.0
        for tema, cfg in TEMAS.items():
            score_tema = 0.0
            for kw, peso in cfg["keywords"].items():
                if kw in alvo:
                    # Peso extra se a keyword aparece no título.
                    ocorrencias = alvo.count(kw)
                    bonus_titulo = 1.5 if kw in m.titulo.lower() else 1.0
                    score_tema += peso * ocorrencias * bonus_titulo
            if score_tema > melhor_score:
                melhor_score, melhor_tema = score_tema, tema
            score_total += score_tema
        if melhor_score > 0:
            m.tema = melhor_tema
            m.score = score_total
            if m.publicado is None:
                m.score *= 0.85   # leve penalização p/ itens sem data
            relevantes.append(m)

    relevantes.sort(key=lambda x: x.score, reverse=True)
    log.info("Ranking: %d itens relevantes (de %d)", len(relevantes), len(materias))
    return relevantes


# =============================================================================
# 9. RESUMO DAS MATÉRIAS
# =============================================================================
def resumir_materia(m: Materia) -> str:
    """Monta o resumo de uma matéria a partir da descrição do próprio feed RSS.
    Cai para o título quando o feed não traz descrição. Nunca lança exceção."""
    return truncar(m.descricao or m.titulo, 300)


def sumarizar_todas(materias: list[Materia]) -> None:
    """Preenche o campo `resumo` de cada matéria com o texto da descrição do RSS."""
    log.info("Montando resumos de %d matérias (descrição do RSS)…", len(materias))
    for m in materias:
        m.resumo = resumir_materia(m)


# =============================================================================
# 10. PAINEL MACROECONÔMICO
# =============================================================================
@dataclass
class Indicador:
    nome: str
    valor: str
    variacao: str = ""              # texto exibido (ex.: "+0,42%")
    direcao: int = 0                # 1 = alta, -1 = baixa, 0 = neutro
    sufixo: str = ""                # "%", "R$", "pts"
    casas: int = 2                  # casas decimais para o gráfico
    fonte: str = ""                 # rótulo curto da fonte
    fonte_url: str = ""             # link para conferir o dado na origem
    historico: list = field(default_factory=list)  # [(iso_date, valor), ...]


def _fmt_num(v: float, casas: int = 2) -> str:
    s = f"{v:,.{casas}f}"
    # formato BR: milhar '.' e decimal ','
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _br_to_iso(data_br: str) -> str:
    """Converte 'DD/MM/AAAA' (formato do SGS) para 'AAAA-MM-DD'."""
    try:
        d, m, y = data_br.strip().split("/")
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        return ""


def _iso_to_br(data_iso: str) -> str:
    """Converte 'AAAA-MM-DD' para 'DD/MM/AAAA' (exibição)."""
    try:
        y, m, d = data_iso.split("-")
        return f"{d}/{m}/{y}"
    except Exception:
        return ""


def _valor_txt(v: float, sufixo: str, casas: int) -> str:
    if sufixo == "R$":
        return f"R$ {_fmt_num(v, casas)}"
    if sufixo == "pts":
        return f"{_fmt_num(v, casas)} pts"
    return f"{_fmt_num(v, casas)} {sufixo}".strip()


def _parse_sgs(dados: list) -> list[tuple[str, float]]:
    """Converte a resposta do SGS em [(iso_date, valor), ...] descartando inválidos."""
    historico: list[tuple[str, float]] = []
    for pt in dados or []:
        try:
            v = float(str(pt["valor"]).replace(",", "."))
            iso = _br_to_iso(pt.get("data", ""))
            if iso:
                historico.append((iso, v))
        except Exception:
            continue
    return historico


def _buscar_serie_sgs(cod: int, meses: int) -> list[tuple[str, float]]:
    """Busca uma série do SGS. Tenta a janela de datas (endpoint canônico e mais
    estável) e, se falhar, cai para /ultimos/{n}. Usa headers e timeout dedicados."""
    hoje = dt.date.today()
    ini = hoje - dt.timedelta(days=int(meses * 31))  # folga p/ cobrir a janela
    di, df = ini.strftime("%d/%m/%Y"), hoje.strftime("%d/%m/%Y")

    # 1ª opção: janela de datas (dataInicial/dataFinal) — bem abaixo do limite de 10 anos.
    url_datas = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados"
                 f"?formato=json&dataInicial={di}&dataFinal={df}")
    resp = http_get(url_datas, timeout=BCB_TIMEOUT, headers=BCB_HEADERS)
    if resp is not None:
        hist = _parse_sgs(resp.json())
        if hist:
            return hist

    # 2ª opção (fallback): últimos N pontos.
    n = N_HISTORICO.get("diaria", 560) if meses >= 12 else N_HISTORICO.get("mensal", 26)
    url_ultimos = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados/ultimos/{n}?formato=json"
    resp = http_get(url_ultimos, timeout=BCB_TIMEOUT, headers=BCB_HEADERS)
    if resp is not None:
        return _parse_sgs(resp.json())
    return []


def puxar_sgs() -> list[Indicador]:
    """Puxa séries do SGS/BCB com histórico (~24m). Cada série é isolada."""
    indicadores: list[Indicador] = []
    hoje = dt.date.today()
    di_24m = (hoje - dt.timedelta(days=24 * 31)).strftime("%d/%m/%Y")
    df_hoje = hoje.strftime("%d/%m/%Y")
    for nome, cfg in SGS_SERIES.items():
        cod = cfg["codigo"]
        sufixo = cfg["sufixo"]
        casas = cfg.get("casas", 2)
        fonte = f"Banco Central (SGS {cod})"
        # Janela de datas explícita: pedir a série inteira sem dataInicial estoura o
        # limite de 10 anos do BCB em séries diárias (erro 400 "janela de consulta").
        fonte_url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados"
                     f"?formato=json&dataInicial={di_24m}&dataFinal={df_hoje}")
        base_ind = lambda: Indicador(nome, "—", sufixo=sufixo, casas=casas,
                                     fonte=fonte, fonte_url=fonte_url)
        try:
            historico = _buscar_serie_sgs(cod, meses=24)
            if not historico:
                log.warning("  [SGS %5s] %-18s sem dados (400/vazio) -> '—'", cod, nome)
                indicadores.append(base_ind())
                time.sleep(BCB_PAUSA)
                continue

            ultimo = historico[-1][1]
            data_ref = _iso_to_br(historico[-1][0])
            ind = Indicador(nome, _valor_txt(ultimo, sufixo, casas),
                            sufixo=sufixo, casas=casas, fonte=fonte,
                            fonte_url=fonte_url, historico=historico)
            if len(historico) >= 2:
                anterior = historico[-2][1]
                # Séries que já são taxas percentuais (Selic, CDI, IPCA, IGP-M): a variação
                # relevante é a diferença em pontos percentuais, não "% de variação sobre
                # a taxa anterior" (isso inflava/distorcia o número, ex.: IPCA 0,10% -> 0,50%
                # aparecia como "+400%" em vez de "+0,40 p.p.").
                if sufixo == "%":
                    diff = ultimo - anterior
                    ind.variacao = f"{'+' if diff >= 0 else ''}{_fmt_num(diff, casas)} p.p."
                    ind.direcao = 1 if diff > 0 else (-1 if diff < 0 else 0)
                elif anterior:
                    var = (ultimo - anterior) / anterior * 100
                    ind.variacao = f"{'+' if var >= 0 else ''}{_fmt_num(var, 2)}%"
                    ind.direcao = 1 if var > 0 else (-1 if var < 0 else 0)
            if data_ref:
                ind.variacao = (ind.variacao + f" · {data_ref}").strip(" ·")
            indicadores.append(ind)
            log.info("  [SGS %5s] %-18s %s (%d pts)", cod, nome, ind.valor, len(historico))
        except Exception as e:
            log.error("  [SGS FALHA] %-18s %s", nome, str(e)[:120])
            indicadores.append(base_ind())
        time.sleep(BCB_PAUSA)   # cortesia com o servidor entre séries
    return indicadores


def puxar_indices_yf() -> list[Indicador]:
    """Puxa índices via yfinance com histórico de 2 anos. Isolado por índice."""
    indicadores: list[Indicador] = []
    if yf is None:
        log.warning("yfinance ausente -> índices de bolsa omitidos. (pip install yfinance)")
        return indicadores
    for nome, ticker in YF_INDICES.items():
        fonte = "Yahoo Finance"
        fonte_url = f"https://finance.yahoo.com/quote/{ticker}"
        base_ind = lambda: Indicador(nome, "—", sufixo="pts", casas=0,
                                     fonte=fonte, fonte_url=fonte_url)
        try:
            hist = yf.Ticker(ticker).history(period="2y")
            if hist is None or hist.empty or "Close" not in hist:
                log.warning("  [YF] sem dados para %s (%s)", nome, ticker)
                indicadores.append(base_ind())
                continue
            fechamentos = hist["Close"].dropna()
            # idx é um pandas.Timestamp (DatetimeIndex); os stubs o tipam como Hashable.
            historico = [(idx.strftime("%Y-%m-%d"), float(v))  # type: ignore[attr-defined]
                         for idx, v in fechamentos.items()]
            atual = historico[-1][1]
            ind = Indicador(nome, _valor_txt(atual, "pts", 0), sufixo="pts", casas=0,
                            fonte=fonte, fonte_url=fonte_url, historico=historico)
            if len(historico) >= 2:
                anterior = historico[-2][1]
                if anterior:
                    var = (atual - anterior) / anterior * 100
                    ind.variacao = f"{'+' if var >= 0 else ''}{_fmt_num(var, 2)}%"
                    ind.direcao = 1 if var > 0 else (-1 if var < 0 else 0)
            indicadores.append(ind)
            log.info("  [YF] %-10s %s  %s (%d pts)", nome, ind.valor, ind.variacao, len(historico))
        except Exception as e:
            log.error("  [YF FALHA] %-10s %s", nome, str(e)[:120])
            indicadores.append(base_ind())
    return indicadores


def montar_painel_macro() -> list[Indicador]:
    log.info("Puxando painel macroeconômico…")
    return puxar_sgs() + puxar_indices_yf()


# =============================================================================
# 11. CACHE DIÁRIO
# =============================================================================
def caminho_cache(hoje: dt.date) -> Path:
    return PASTA_CACHE / f"briefing_{hoje.isoformat()}.json"


def caminho_html(hoje: dt.date) -> Path:
    return PASTA_SAIDA / f"briefing_{hoje.isoformat()}.html"


def limpar_arquivos_antigos(dias: int = RETENCAO_DIAS) -> None:
    """Apaga relatórios HTML e cache com mais de `dias` dias de idade."""
    limite = time.time() - dias * 86400
    for pasta, padrao in ((PASTA_SAIDA, "briefing_*.html"), (PASTA_CACHE, "briefing_*.json")):
        if not pasta.exists():
            continue
        for arq in pasta.glob(padrao):
            try:
                if arq.stat().st_mtime < limite:
                    arq.unlink()
                    log.info("  [limpeza] removido: %s", arq.name)
            except Exception as e:
                log.warning("  [limpeza] falha ao remover %s: %s", arq.name, str(e)[:120])


# =============================================================================
# 12. GERAÇÃO DO HTML
# =============================================================================
MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
           "sexta-feira", "sábado", "domingo"]


def data_por_extenso(d: dt.date) -> str:
    return f"{DIAS_PT[d.weekday()]}, {d.day} de {MESES_PT[d.month - 1]} de {d.year}"


def _classe_var(direcao: int) -> str:
    return {1: "up", -1: "down", 0: "flat"}[direcao]


def _seta(direcao: int) -> str:
    return {1: "▲", -1: "▼", 0: "•"}[direcao]


# JavaScript do modal + gráfico SVG (vanilla, sem CDN). MACRO_DATA é injetado antes deste bloco.
_CHART_JS = r"""
(function () {
  const MONTHS_DEFAULT = 12;
  const C = { linha:'#4c8bf5', area1:'rgba(76,139,245,0.28)', area2:'rgba(76,139,245,0.02)',
              grid:'#2a303c', texto:'#9aa4b2' };
  const NS = 'http://www.w3.org/2000/svg';
  const state = { key:null, months:MONTHS_DEFAULT };

  const modal   = document.getElementById('modal');
  const elTit    = document.getElementById('modal-titulo');
  const elVal    = document.getElementById('modal-valor');
  const elFonte  = document.getElementById('modal-fonte');
  const svg      = document.getElementById('chart');
  const ranges   = document.getElementById('ranges');

  const fmt = (v, d) => Number(v).toLocaleString('pt-BR',
      { minimumFractionDigits:d, maximumFractionDigits:d });
  function fmtValor(v, unit, d) {
    if (unit === 'R$')  return 'R$ ' + fmt(v, d);
    if (unit === 'pts') return fmt(v, 0) + ' pts';
    return fmt(v, d) + (unit ? ' ' + unit : '');
  }
  function fmtData(iso) { const [y,m,dd] = iso.split('-'); return dd+'/'+m+'/'+y.slice(2); }

  function filtrar(series, months) {
    if (!series.length) return [];
    const last = new Date(series[series.length-1][0]);
    const lim = new Date(last); lim.setMonth(lim.getMonth() - months);
    const pts = series.filter(p => new Date(p[0]) >= lim);
    return pts.length >= 2 ? pts : series.slice(-2);
  }

  function el(tag, attrs) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function drawChart(points, unit, decimals) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const W=720, H=320, mL=64, mR=18, mT=18, mB=42;
    const plotW=W-mL-mR, plotH=H-mT-mB;

    if (points.length < 2) {
      svg.appendChild(Object.assign(el('text',
        {x:W/2, y:H/2, fill:C.texto, 'text-anchor':'middle', 'font-size':13}),
        {textContent:'Dados insuficientes para este intervalo.'}));
      return;
    }

    const xs = points.map(p => new Date(p[0]).getTime());
    const ys = points.map(p => p[1]);
    const minX=Math.min(...xs), maxX=Math.max(...xs);
    let minY=Math.min(...ys), maxY=Math.max(...ys);
    if (minY===maxY) { minY-=1; maxY+=1; }
    const padY=(maxY-minY)*0.08; minY-=padY; maxY+=padY;
    const sx = x => mL + (maxX===minX ? plotW/2 : (x-minX)/(maxX-minX)*plotW);
    const sy = y => mT + (1-(y-minY)/(maxY-minY))*plotH;

    // Gridlines Y + rótulos
    const nY=4;
    for (let i=0;i<=nY;i++){
      const val=minY+(maxY-minY)*i/nY, yy=sy(val);
      svg.appendChild(el('line',{x1:mL,x2:W-mR,y1:yy,y2:yy,stroke:C.grid,'stroke-width':1}));
      svg.appendChild(Object.assign(el('text',
        {x:mL-8,y:yy+4,fill:C.texto,'font-size':11,'text-anchor':'end'}),
        {textContent:fmt(val,decimals)}));
    }
    // Rótulos X (datas)
    const nX=Math.min(5, points.length);
    for (let i=0;i<nX;i++){
      const idx=Math.round(i*(points.length-1)/(nX-1)), p=points[idx];
      const xx=sx(new Date(p[0]).getTime());
      const anchor = i===0 ? 'start' : (i===nX-1 ? 'end' : 'middle');
      svg.appendChild(Object.assign(el('text',
        {x:xx,y:H-mB+20,fill:C.texto,'font-size':11,'text-anchor':anchor}),
        {textContent:fmtData(p[0])}));
    }
    // Área com gradiente
    const defs=el('defs',{});
    const grad=el('linearGradient',{id:'gArea',x1:'0',y1:'0',x2:'0',y2:'1'});
    grad.appendChild(el('stop',{offset:'0%','stop-color':C.area1}));
    grad.appendChild(el('stop',{offset:'100%','stop-color':C.area2}));
    defs.appendChild(grad); svg.appendChild(defs);
    let dA='M '+sx(xs[0])+' '+sy(ys[0]);
    for (let i=1;i<points.length;i++) dA+=' L '+sx(xs[i])+' '+sy(ys[i]);
    dA+=' L '+sx(xs[xs.length-1])+' '+(mT+plotH)+' L '+sx(xs[0])+' '+(mT+plotH)+' Z';
    svg.appendChild(el('path',{d:dA,fill:'url(#gArea)',stroke:'none'}));
    // Linha
    let dL='M '+sx(xs[0])+' '+sy(ys[0]);
    for (let i=1;i<points.length;i++) dL+=' L '+sx(xs[i])+' '+sy(ys[i]);
    svg.appendChild(el('path',{d:dL,fill:'none',stroke:C.linha,'stroke-width':2,
      'stroke-linejoin':'round','stroke-linecap':'round'}));
    // Último ponto
    svg.appendChild(el('circle',{cx:sx(xs[xs.length-1]),cy:sy(ys[ys.length-1]),r:3.5,fill:C.linha}));

    // Hover
    const hLine=el('line',{stroke:C.texto,'stroke-width':1,'stroke-dasharray':'3 3',
      opacity:0,y1:mT,y2:mT+plotH});
    const hDot=el('circle',{r:4,fill:'#fff',stroke:C.linha,'stroke-width':2,opacity:0});
    const tip=el('g',{opacity:0});
    const tBg=el('rect',{rx:6,fill:'#0b0d11',stroke:C.grid});
    const t1=el('text',{fill:C.texto,'font-size':11});
    const t2=el('text',{fill:'#fff','font-size':13,'font-weight':700});
    tip.appendChild(tBg); tip.appendChild(t1); tip.appendChild(t2);
    svg.appendChild(hLine); svg.appendChild(hDot); svg.appendChild(tip);
    const ov=el('rect',{x:mL,y:mT,width:plotW,height:plotH,fill:'transparent'});
    ov.style.cursor='crosshair'; svg.appendChild(ov);

    function nearest(clientX){
      const r=svg.getBoundingClientRect();
      const px=(clientX-r.left)/r.width*W;
      let best=0,bd=Infinity;
      for (let i=0;i<points.length;i++){ const d=Math.abs(sx(xs[i])-px); if(d<bd){bd=d;best=i;} }
      return best;
    }
    function show(clientX){
      const i=nearest(clientX), x=sx(xs[i]), y=sy(ys[i]);
      hLine.setAttribute('x1',x); hLine.setAttribute('x2',x); hLine.setAttribute('opacity',1);
      hDot.setAttribute('cx',x); hDot.setAttribute('cy',y); hDot.setAttribute('opacity',1);
      t1.textContent=fmtData(points[i][0]);
      t2.textContent=fmtValor(ys[i],unit,decimals);
      const w=Math.max(t1.getComputedTextLength?t1.getComputedTextLength():60,
                       t2.getComputedTextLength?t2.getComputedTextLength():60)+16;
      const h=38; let tx=x+10; if (tx+w>W-mR) tx=x-w-10;
      let ty=y-h-8; if (ty<mT) ty=mT+4;
      tBg.setAttribute('x',tx); tBg.setAttribute('y',ty);
      tBg.setAttribute('width',w); tBg.setAttribute('height',h);
      t1.setAttribute('x',tx+8); t1.setAttribute('y',ty+15);
      t2.setAttribute('x',tx+8); t2.setAttribute('y',ty+31);
      tip.setAttribute('opacity',1);
    }
    function hide(){ hLine.setAttribute('opacity',0); hDot.setAttribute('opacity',0); tip.setAttribute('opacity',0); }
    ov.addEventListener('mousemove', e => show(e.clientX));
    ov.addEventListener('mouseleave', hide);
    ov.addEventListener('touchmove', e => { if(e.touches[0]){ show(e.touches[0].clientX); e.preventDefault(); } }, {passive:false});
    ov.addEventListener('touchend', hide);
  }

  function render(){
    const d=MACRO_DATA[state.key]; if(!d) return;
    elTit.textContent=d.label;
    const u=d.series[d.series.length-1];
    elVal.textContent=fmtValor(u[1],d.unit,d.decimals)+'  ·  '+fmtData(u[0]);
    elFonte.innerHTML = d.sourceUrl
      ? 'Fonte: <a href="'+d.sourceUrl+'" target="_blank" rel="noopener">'+d.source+' ↗</a>'
      : 'Fonte: '+d.source;
    ranges.querySelectorAll('button').forEach(b =>
      b.classList.toggle('ativo', Number(b.dataset.m)===state.months));
    drawChart(filtrar(d.series, state.months), d.unit, d.decimals);
  }
  function open(key){
    if(!MACRO_DATA[key]) return;
    state.key=key; state.months=MONTHS_DEFAULT;
    modal.classList.add('aberto'); modal.setAttribute('aria-hidden','false');
    document.body.style.overflow='hidden'; render();
  }
  function close(){
    modal.classList.remove('aberto'); modal.setAttribute('aria-hidden','true');
    document.body.style.overflow='';
  }

  document.querySelectorAll('.card.clicavel').forEach(card => {
    card.addEventListener('click', () => open(card.dataset.key));
    card.addEventListener('keydown', e => {
      if(e.key==='Enter'||e.key===' '){ e.preventDefault(); open(card.dataset.key); }
    });
  });
  ranges.querySelectorAll('button').forEach(b =>
    b.addEventListener('click', () => { state.months=Number(b.dataset.m); render(); }));
  modal.querySelectorAll('[data-close]').forEach(x => x.addEventListener('click', close));
  document.addEventListener('keydown', e => { if(e.key==='Escape') close(); });
})();
"""


def gerar_html(materias: list[Materia], macro: list[Indicador], hoje: dt.date) -> str:
    # Agrupa manchetes por tema, respeitando o teto por tema.
    por_tema: dict[str, list[Materia]] = {}
    for m in materias:
        por_tema.setdefault(m.tema, [])
        if len(por_tema[m.tema]) < MAX_MANCHETES_POR_TEMA:
            por_tema[m.tema].append(m)

    # Cards de indicadores (clicáveis quando há histórico para o gráfico)
    cards = []
    macro_data: dict[str, dict] = {}
    for ind in macro:
        cls = _classe_var(ind.direcao)
        var_html = ""
        if ind.variacao:
            var_html = f'<div class="var {cls}">{_seta(ind.direcao)} {html.escape(ind.variacao)}</div>'
        fonte_html = f'<div class="card-fonte">{html.escape(ind.fonte)}</div>' if ind.fonte else ""

        tem_grafico = len(ind.historico) >= 2
        if tem_grafico:
            macro_data[ind.nome] = {
                "label": ind.nome,
                "unit": ind.sufixo,
                "decimals": ind.casas,
                "source": ind.fonte,
                "sourceUrl": ind.fonte_url,
                "series": [[iso, v] for iso, v in ind.historico],
            }
            attrs = (f' class="card clicavel" data-key="{html.escape(ind.nome)}"'
                     f' role="button" tabindex="0"'
                     f' aria-label="Ver histórico de {html.escape(ind.nome)}"')
            dica = '<div class="card-dica">ver histórico ↗</div>'
        else:
            attrs = ' class="card"'
            dica = ""

        cards.append(f"""
        <div{attrs}>
          <div class="card-nome">{html.escape(ind.nome)}</div>
          <div class="card-valor">{html.escape(ind.valor)}</div>
          {var_html}
          {fonte_html}
          {dica}
        </div>""")
    cards_html = "\n".join(cards)
    macro_json = json.dumps(macro_data, ensure_ascii=False)

    # Seções de manchetes (mantém a ordem de TEMAS)
    secoes = []
    total_manchetes = 0
    for tema in TEMAS.keys():
        itens = por_tema.get(tema, [])
        if not itens:
            continue
        linhas = []
        for m in itens:
            total_manchetes += 1
            hora = m.publicado.strftime("%d/%m %H:%M") if m.publicado else "s/ data"
            linhas.append(f"""
            <article class="materia">
              <h3><a href="{html.escape(m.url)}" target="_blank" rel="noopener">{html.escape(m.titulo)}</a></h3>
              <div class="meta">{html.escape(m.fonte)} · {hora}</div>
              <a class="resumo-link" href="{html.escape(m.url)}" target="_blank" rel="noopener"
                 title="Abrir notícia original em {html.escape(m.fonte)}">
                <p class="resumo">{html.escape(m.resumo)}</p>
                <span class="ler-mais">Ver notícia original ↗</span>
              </a>
            </article>""")
        secoes.append(f"""
        <section class="tema">
          <h2>{html.escape(tema)} <span class="contador">{len(itens)}</span></h2>
          {''.join(linhas)}
        </section>""")
    secoes_html = "\n".join(secoes) if secoes else '<p class="vazio">Nenhuma manchete relevante encontrada na janela definida.</p>'

    gerado_em = dt.datetime.now().strftime("%d/%m/%Y %H:%M")

    html_doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Briefing Diário · {hoje.isoformat()}</title>
<style>
  :root {{
    --bg: #0f1115; --surface: #171a21; --surface-2: #1f2430;
    --texto: #e8eaed; --muted: #9aa4b2; --linha: #2a303c;
    --azul: #4c8bf5; --verde: #2ecc71; --vermelho: #e74c3c; --neutro: #7f8c9a;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--texto);
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.55; font-size: 16px;
  }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 32px 20px 64px; }}
  header.topo {{ border-bottom: 2px solid var(--linha); padding-bottom: 18px; margin-bottom: 28px; }}
  header.topo .kicker {{ color: var(--azul); font-weight: 700; letter-spacing: .5px; text-transform: uppercase; font-size: 13px; }}
  header.topo h1 {{ margin: 6px 0 4px; font-size: 26px; }}
  header.topo .data {{ color: var(--muted); font-size: 15px; text-transform: capitalize; }}

  .painel {{ margin-bottom: 36px; }}
  .painel h2, .tema h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: .6px;
    color: var(--muted); border-left: 3px solid var(--azul); padding-left: 10px; margin: 0 0 14px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
  .card {{ background: var(--surface); border: 1px solid var(--linha); border-radius: 12px; padding: 14px 16px; }}
  .card-nome {{ color: var(--muted); font-size: 12.5px; text-transform: uppercase; letter-spacing: .4px; }}
  .card-valor {{ font-size: 22px; font-weight: 700; margin-top: 4px; }}
  .var {{ font-size: 13px; font-weight: 600; margin-top: 2px; }}
  .var.up {{ color: var(--verde); }}
  .var.down {{ color: var(--vermelho); }}
  .var.flat {{ color: var(--neutro); }}
  .card-fonte {{ color: var(--neutro); font-size: 10.5px; margin-top: 8px;
    text-transform: uppercase; letter-spacing: .3px; }}
  .card-dica {{ color: var(--azul); font-size: 11px; font-weight: 600; margin-top: 4px; opacity: .65; }}
  .card.clicavel {{ cursor: pointer; }}
  .card.clicavel:hover {{ border-color: var(--azul); }}
  .card.clicavel:hover .card-dica {{ opacity: 1; }}
  .card.clicavel:focus-visible {{ outline: 2px solid var(--azul); outline-offset: 2px; }}

  /* Modal do gráfico */
  .modal {{ position: fixed; inset: 0; display: none; z-index: 50; }}
  .modal.aberto {{ display: block; }}
  .modal-fundo {{ position: absolute; inset: 0; background: rgba(0,0,0,.65); }}
  .modal-box {{ position: relative; max-width: 780px; width: calc(100% - 32px);
    margin: 6vh auto 0; background: var(--surface); border: 1px solid var(--linha);
    border-radius: 16px; padding: 22px 24px 20px; box-shadow: 0 20px 60px rgba(0,0,0,.5); }}
  .modal-x {{ position: absolute; top: 14px; right: 14px; background: var(--surface-2);
    color: var(--muted); border: none; border-radius: 8px; width: 32px; height: 32px;
    font-size: 14px; cursor: pointer; }}
  .modal-x:hover {{ color: var(--texto); }}
  .modal-box h3 {{ margin: 0 40px 2px 0; font-size: 20px; }}
  .modal-valor {{ color: var(--muted); font-size: 14px; margin-bottom: 14px; }}
  .ranges {{ display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }}
  .ranges button {{ background: var(--surface-2); color: var(--muted); border: 1px solid var(--linha);
    border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .12s; }}
  .ranges button:hover {{ color: var(--texto); border-color: var(--azul); }}
  .ranges button.ativo {{ background: var(--azul); color: #fff; border-color: var(--azul); }}
  .chart-wrap {{ width: 100%; }}
  .chart-wrap svg {{ width: 100%; height: auto; display: block; }}
  .modal-fonte {{ margin-top: 12px; color: var(--neutro); font-size: 12px; }}
  .modal-fonte a {{ color: var(--azul); text-decoration: none; }}
  .modal-fonte a:hover {{ text-decoration: underline; }}
  .painel .painel-dica {{ color: var(--neutro); font-size: 12.5px; margin: -8px 0 14px; }}

  .tema {{ margin-bottom: 34px; }}
  .tema h2 .contador {{ background: var(--surface-2); color: var(--muted); border-radius: 20px;
    padding: 1px 9px; font-size: 12px; margin-left: 6px; }}
  .materia {{ background: var(--surface); border: 1px solid var(--linha); border-radius: 12px;
    padding: 16px 18px; margin-bottom: 12px; transition: border-color .15s; }}
  .materia:hover {{ border-color: var(--azul); }}
  .materia h3 {{ margin: 0 0 4px; font-size: 17px; line-height: 1.35; }}
  .materia h3 a {{ color: var(--texto); text-decoration: none; }}
  .materia h3 a:hover {{ color: var(--azul); text-decoration: underline; }}
  .materia .meta {{ color: var(--muted); font-size: 12.5px; margin-bottom: 8px; }}
  .materia .resumo-link {{ display: block; text-decoration: none; color: inherit; }}
  .materia .resumo {{ margin: 0; color: #cdd3dd; font-size: 15px; transition: color .15s; }}
  .materia .resumo-link:hover .resumo {{ color: var(--texto); }}
  .materia .ler-mais {{ display: inline-block; margin-top: 8px; font-size: 13px; font-weight: 600;
    color: var(--azul); opacity: .8; transition: opacity .15s; }}
  .materia .resumo-link:hover .ler-mais {{ opacity: 1; text-decoration: underline; }}
  .vazio {{ color: var(--muted); }}

  footer {{ margin-top: 40px; border-top: 1px solid var(--linha); padding-top: 16px;
    color: var(--muted); font-size: 12.5px; }}
  @media (max-width: 520px) {{ .card-valor {{ font-size: 19px; }} header.topo h1 {{ font-size: 22px; }} }}
</style>
</head>
<body>
  <div class="wrap">
    <header class="topo">
      <div class="kicker">Briefing Diário · Inteligência de Mercado</div>
      <h1>Briefing de Real Estate Logístico &amp; Notícias Globais</h1>
      <div class="data">{data_por_extenso(hoje)}</div>
    </header>

    <div class="painel">
      <h2>Painel Macroeconômico</h2>
      <p class="painel-dica">Clique em um indicador para ver o histórico (1, 3, 6, 12 e 24 meses).</p>
      <div class="cards">
        {cards_html}
      </div>
    </div>

    {secoes_html}

    <footer>
      Gerado automaticamente em {gerado_em} · {total_manchetes} manchetes · janela de {JANELA_HORAS}h.<br>
      <strong>Fontes dos dados macroeconômicos:</strong>
      indicadores de juros, inflação e câmbio (Selic, CDI, IPCA, IGP-M, USD/BRL) do
      <a href="https://www3.bcb.gov.br/sgspub/" target="_blank" rel="noopener">Banco Central do Brasil — Sistema Gerenciador de Séries Temporais (SGS)</a>;
      índices de bolsa (Ibovespa, IFIX) do
      <a href="https://finance.yahoo.com/" target="_blank" rel="noopener">Yahoo Finance</a>.
      Notícias coletadas via RSS de veículos econômicos, fontes globais de
      reputação estabelecida (BBC, The Guardian, Al Jazeera, ONU, NPR,
      Deutsche Welle, Reuters, Associated Press) e Google News.
      Confira sempre a fonte original antes de decisões.
    </footer>
  </div>

  <!-- Modal do gráfico histórico -->
  <div id="modal" class="modal" aria-hidden="true">
    <div class="modal-fundo" data-close></div>
    <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="modal-titulo">
      <button class="modal-x" data-close aria-label="Fechar">✕</button>
      <h3 id="modal-titulo"></h3>
      <div class="modal-valor" id="modal-valor"></div>
      <div class="ranges" id="ranges">
        <button data-m="1">1M</button>
        <button data-m="3">3M</button>
        <button data-m="6">6M</button>
        <button data-m="12">12M</button>
        <button data-m="24">24M</button>
      </div>
      <div class="chart-wrap">
        <svg id="chart" viewBox="0 0 720 320" preserveAspectRatio="xMidYMid meet"
             role="img" aria-label="Gráfico histórico do indicador"></svg>
      </div>
      <div class="modal-fonte" id="modal-fonte"></div>
    </div>
  </div>
  __SCRIPT__
</body>
</html>"""

    # Injeta o JS separadamente para não precisar escapar as chaves do script na f-string.
    script = "<script>\nconst MACRO_DATA = " + macro_json + ";\n" + _CHART_JS + "\n</script>"
    return html_doc.replace("__SCRIPT__", script)


# =============================================================================
# 13. ORQUESTRAÇÃO
# =============================================================================
def main() -> int:
    inicio = time.time()
    hoje = dt.date.today()

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    PASTA_CACHE.mkdir(parents=True, exist_ok=True)
    log.info("=" * 64)
    log.info("BRIEFING DIÁRIO · %s", data_por_extenso(hoje))
    log.info("Pasta de saída: %s", PASTA_SAIDA)
    log.info("=" * 64)

    # Cache diário: se já existe HTML de hoje e não foi forçado, apenas informa.
    destino_html = caminho_html(hoje)
    forcar = "--force" in sys.argv
    if destino_html.exists() and not forcar:
        log.info("HTML de hoje já existe: %s", destino_html)
        log.info("Use '--force' para regenerar. Encerrando (cache diário).")
        webbrowser.open(destino_html.resolve().as_uri())
        limpar_arquivos_antigos()
        return 0

    # 1-2. Coleta + filtro + dedup + ranking
    try:
        brutas = coletar_todas_as_fontes()
    except Exception as e:
        log.error("Falha geral na coleta: %s", e)
        brutas = []

    if not brutas:
        log.warning("Nenhuma matéria coletada. Gerando HTML apenas com painel macro.")

    recentes = filtrar_recentes(brutas)
    unicas = deduplicar(recentes)
    rankeadas = classificar_e_rankear(unicas)

    # 3. Sumarização (nunca derruba o script)
    try:
        sumarizar_todas(rankeadas)
    except Exception as e:
        log.error("Falha na sumarização (seguindo com fallback): %s", e)
        for m in rankeadas:
            if not m.resumo:
                m.resumo = truncar(m.descricao or m.titulo, 300)

    # 4. Painel macro
    try:
        macro = montar_painel_macro()
    except Exception as e:
        log.error("Falha no painel macro: %s", e)
        macro = []

    # 5. HTML
    html_final = gerar_html(rankeadas, macro, hoje)
    try:
        destino_html.write_text(html_final, encoding="utf-8")
        log.info("HTML salvo: %s", destino_html)
    except Exception as e:
        log.error("Falha ao salvar HTML: %s", e)
        return 1

    # Cache leve (metadados da execução)
    try:
        caminho_cache(hoje).write_text(json.dumps({
            "gerado_em": dt.datetime.now().isoformat(),
            "manchetes": len(rankeadas),
            "html": str(destino_html),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    log.info("=" * 64)
    log.info("Concluído em %.1fs · %d manchetes · %s",
             time.time() - inicio, len(rankeadas), destino_html.name)
    log.info("=" * 64)

    # Abre o relatório automaticamente no navegador padrão.
    try:
        webbrowser.open(destino_html.resolve().as_uri())
    except Exception as e:
        log.warning("Falha ao abrir o navegador automaticamente: %s", str(e)[:120])

    # Limpa cache e relatórios mais antigos que RETENCAO_DIAS dias.
    limpar_arquivos_antigos()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("Interrompido pelo usuário.")
        sys.exit(130)
