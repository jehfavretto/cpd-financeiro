"""
Sistema de temas do CPD Financeiro.
Gera CSS completo (fonte + variáveis visuais) para modo claro e escuro,
baseado na identidade visual do site colegiocpd.com.br.
"""


def css_completo(tema: str) -> str:
    """Retorna HTML com Google Font + CSS do tema especificado."""
    dark = (tema == "dark")

    # ── Paleta ───────────────────────────────────────────────────────────────
    bg        = "#0C1426"      if dark else "#FFFFFF"
    bg2       = "#162040"      if dark else "#F0F4F8"
    card      = "#1A2550"      if dark else "#FFFFFF"
    sidebar   = "#080E1C"      if dark else "#1C2B5F"
    txt       = "#E8EDF6"      if dark else "#1C2B5F"
    txt2      = "#8FA0C0"      if dark else "#5A6A88"
    accent    = "#E63A5C"      if dark else "#C4153A"
    accent_h  = "#FF5577"      if dark else "#A01030"
    border    = "rgba(232,237,246,0.08)" if dark else "rgba(28,43,95,0.09)"
    shadow    = "0 2px 14px rgba(0,0,0,0.28)" if dark else "0 2px 14px rgba(28,43,95,0.06)"
    inp_bg    = "#162040"      if dark else "#F8FAFC"
    card_pos  = "#0d2a1a"      if dark else "#eaffea"
    card_neg  = "#2a0d14"      if dark else "#fff0f0"
    card_neu  = "#1A2550"      if dark else "#f8f9fb"
    txt_pos   = "#2ed64f"      if dark else "#1a7f37"
    txt_neg   = "#E63A5C"      if dark else "#C4153A"

    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');

/* ── Fonte global (Nunito — mesma do site CPD) ─────────────────────────── */
/* Seletores específicos evitam sobrescrever fontes de ícones do Streamlit */
html, body, button, select, textarea,
p, li, td, th, label, a,
h1, h2, h3, h4, h5, h6,
.stMarkdown, .stText {{
    font-family: 'Nunito', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}
input:not([type="file"]) {{
    font-family: 'Nunito', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}
/* div e span: sem !important, para não sobrescrever Material Symbols (ícones) */
div, span {{
    font-family: 'Nunito', -apple-system, BlinkMacSystemFont, sans-serif;
}}
/* Garante que ícones Material Symbols do Streamlit mantenham a fonte correta */
.material-symbols-rounded,
.material-symbols-outlined,
.material-icons,
[class*="material-symbol"],
[class*="material-icon"] {{
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    font-weight: normal !important;
    font-style: normal !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
}}

/* ── Fundo principal ───────────────────────────────────────────────────── */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMainBlockContainer"],
.block-container,
section.main > div {{
    background-color: {bg} !important;
}}
[data-testid="stHeader"] {{
    background-color: {bg} !important;
    border-bottom: 1px solid {border};
}}
[data-testid="stBottom"] {{
    background-color: {bg} !important;
}}

/* ── Texto global ──────────────────────────────────────────────────────── */
p, div, span, li, td, th, label {{
    color: {txt};
}}
.stMarkdown p,
.stMarkdown li,
.stMarkdown span {{
    color: {txt} !important;
}}
h1, h2, h3, h4, h5, h6 {{
    color: {txt} !important;
    font-weight: 800 !important;
    letter-spacing: -0.3px;
}}
[data-testid="stCaptionContainer"] p {{
    color: {txt2} !important;
    font-size: 0.82rem !important;
}}
small {{ color: {txt2} !important; }}

/* ── Sidebar ───────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: {sidebar} !important;
}}
[data-testid="stSidebar"] * {{
    color: #FFFFFF !important;
}}
[data-testid="stSidebarNav"] a {{
    color: rgba(255,255,255,0.85) !important;
    border-radius: 6px;
    padding: 4px 8px;
    font-weight: 600;
    transition: background 0.15s;
}}
[data-testid="stSidebarNav"] a:hover,
[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background-color: rgba(196,21,58,0.28) !important;
    color: #FFFFFF !important;
}}
.cpd-divider {{
    border: none;
    border-top: 1px solid rgba(255,255,255,0.15);
    margin: 10px 0;
}}

/* ── Botão primário (vermelho CPD) ─────────────────────────────────────── */
.stButton > button[kind="primary"] {{
    background-color: {accent} !important;
    border-color: {accent} !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    letter-spacing: 0.2px;
    transition: all 0.15s ease;
}}
.stButton > button[kind="primary"]:hover {{
    background-color: {accent_h} !important;
    border-color: {accent_h} !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(196,21,58,0.35) !important;
}}

/* ── Botão secundário ──────────────────────────────────────────────────── */
.stButton > button:not([kind="primary"]) {{
    background-color: transparent !important;
    border: 1.5px solid {accent} !important;
    color: {accent} !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}}
.stButton > button:not([kind="primary"]):hover {{
    background-color: rgba(196,21,58,0.08) !important;
}}

/* ── Métricas ──────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {{
    border-left: 4px solid {accent} !important;
    padding-left: 14px !important;
    background-color: {card} !important;
    border-radius: 0 8px 8px 0 !important;
    box-shadow: {shadow} !important;
}}
[data-testid="stMetricLabel"] p  {{ color: {txt2} !important; font-size: 0.8rem !important; font-weight: 600 !important; }}
[data-testid="stMetricValue"] div {{ color: {txt}  !important; font-weight: 800 !important; }}

/* ── Expanders ─────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background-color: {card} !important;
    border: 1px solid {border} !important;
    border-radius: 10px !important;
    box-shadow: {shadow} !important;
}}
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span {{
    color: {txt} !important;
    font-weight: 700 !important;
}}

/* ── Abas ──────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background-color: {card} !important;
    border-radius: 10px !important;
    border: 1px solid {border} !important;
    padding: 3px !important;
    gap: 3px !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 7px !important;
    color: {txt2} !important;
    font-weight: 600 !important;
    background-color: transparent !important;
}}
.stTabs [aria-selected="true"] {{
    background-color: {accent} !important;
    color: #FFFFFF !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    background-color: {bg} !important;
    padding-top: 12px !important;
}}

/* ── DataFrames ────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    background-color: {card} !important;
    border-radius: 10px !important;
    box-shadow: {shadow} !important;
    overflow: hidden !important;
    border: 1px solid {border} !important;
}}

/* ── Selectbox / inputs ────────────────────────────────────────────────── */
[data-baseweb="select"] > div:first-child {{
    background-color: {inp_bg} !important;
    border-color: {border} !important;
    border-radius: 8px !important;
    color: {txt} !important;
}}
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {{
    background-color: {inp_bg} !important;
    color: {txt} !important;
    border-color: {border} !important;
    border-radius: 8px !important;
}}
[data-baseweb="select"] span {{ color: {txt} !important; }}

/* ── Alertas / info / success / warning ───────────────────────────────── */
[data-testid="stAlert"] {{
    background-color: {card} !important;
    border-radius: 8px !important;
}}
[data-testid="stAlert"] p {{ color: {txt} !important; }}

/* ── Barra de progresso ────────────────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {{
    background-color: {accent} !important;
}}

/* ── Divisores ─────────────────────────────────────────────────────────── */
hr {{ border-color: {border} !important; margin: 16px 0 !important; }}

/* ── Cards HTML inline (KPIs das páginas) ─────────────────────────────── */
/* Neutro */
.stMarkdown div[style*="background:#f8f9fb"],
.stMarkdown div[style*="background: #f8f9fb"] {{
    background-color: {card_neu} !important;
    background:       {card_neu} !important;
}}
/* Positivo (verde) */
.stMarkdown div[style*="background:#eaffea"],
.stMarkdown div[style*="background: #eaffea"] {{
    background-color: {card_pos} !important;
    background:       {card_pos} !important;
}}
/* Negativo (vermelho) */
.stMarkdown div[style*="background:#fff0f0"],
.stMarkdown div[style*="background: #fff0f0"] {{
    background-color: {card_neg} !important;
    background:       {card_neg} !important;
}}
/* Texto label dentro dos cards */
.stMarkdown div[style*="color:#555"],
.stMarkdown div[style*="color: #555"] {{
    color: {txt2} !important;
}}
/* Cor dos valores positivos/negativos */
.stMarkdown div[style*="color:#1a7f37"] {{ color: {txt_pos} !important; }}
.stMarkdown div[style*="color:#C4153A"] {{ color: {txt_neg} !important; }}
.stMarkdown div[style*="color:#1C2B5F"] {{ color: {txt}     !important; }}
.stMarkdown div[style*="color:#2A9D8F"] {{ color: #2A9D8F   !important; }}
.stMarkdown div[style*="color:#E9A020"] {{ color: #E9A020   !important; }}

/* ── Spinner ───────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] {{ color: {txt} !important; }}

/* ══════════════════════════════════════════════════════════════════════════
   BANNER CPD — cabeçalho com identidade visual (azul marinho + ondas vermelhas)
   Inspirado no rodapé do site colegiocpd.com.br
   ══════════════════════════════════════════════════════════════════════════ */
.cpd-banner {{
    background: #1C2B5F;         /* azul marinho CPD — igual ao site */
    position: relative;
    overflow: hidden;
    border-radius: 14px;
    height: 106px;
    display: flex;
    align-items: center;
    padding: 0 40px;
    margin-bottom: 6px;
    box-shadow: 0 6px 32px rgba(28,43,95,0.35);
}}

/* Ondas decorativas (SVGs grandes nos cantos, igual ao site CPD) */
.cpd-onda {{
    position: absolute;
    pointer-events: none;
}}
/* Onda esquerda: canto superior-esquerdo (mesma lógica do lado direito) */
.cpd-onda-esq {{
    left: -80px;
    top:  -120px;
    width: 300px;
    height: 280px;
}}
/* Onda direita: canto superior-direito */
.cpd-onda-dir {{
    right: -80px;
    top:   -120px;
    width: 300px;
    height: 280px;
}}

/* Conteúdo do banner (logo + espaço) */
.cpd-banner-inner {{
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    width: 100%;
}}

/* Card branco ao redor do logo dentro do banner escuro */
.cpd-banner-logo-card {{
    background: #FFFFFF;
    border-radius: 10px;
    padding: 7px 16px;
    display: inline-flex;
    align-items: center;
    box-shadow: 0 2px 10px rgba(0,0,0,0.18);
}}
.cpd-banner-logo-img {{
    height: 40px;
    width: auto;
}}
.cpd-banner-title {{
    color: #FFFFFF;
    font-size: 1.25rem;
    font-weight: 800;
    letter-spacing: -0.3px;
}}

/* ── Toggle de tema — ícone compacto abaixo/direita do banner ─────────── */
#cpd-toggle-anchor .stButton > button {{
    background-color: {card} !important;
    border: 1px solid {border} !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.10) !important;
    color: {txt} !important;
    border-radius: 50% !important;
    width: 36px !important;
    height: 36px !important;
    padding: 0 !important;
    font-size: 1.15rem !important;
    line-height: 1 !important;
    margin-top: -40px !important;   /* sobe para ficar ao lado do banner */
}}
#cpd-toggle-anchor .stButton > button:hover {{
    background-color: {bg2} !important;
    border-color: {accent} !important;
    box-shadow: 0 4px 12px rgba(196,21,58,0.20) !important;
    transform: none !important;
}}

/* ── File uploader ─────────────────────────────────────────────────────── */
[data-testid="stFileUploaderDropzone"] {{
    background-color: {inp_bg} !important;
    border: 1px dashed {border} !important;
    border-radius: 8px !important;
}}
[data-testid="stFileUploaderDropzone"] small {{
    color: {txt2} !important;
}}
/*
 * "uploadUpload": o input[type=file] nativo do browser renderiza seu próprio
 * texto "upload". Ocultamos via color:transparent sem tirar do DOM
 * (o elemento precisa existir para o file picker funcionar).
 */
[data-testid="stFileUploaderDropzone"] input[type="file"] {{
    color: transparent !important;
    -webkit-text-fill-color: transparent !important;
}}
/*
 * Streamlit também duplica o texto do botão internamente para animação.
 * Escondemos o segundo elemento (aria-hidden ou :nth-child(n+2)).
 */
[data-testid="stFileUploaderDropzone"] [aria-hidden="true"] {{
    display: none !important;
}}
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-content"] > *:nth-child(n+2) {{
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
    position: absolute !important;
    opacity: 0 !important;
}}

/* ── Radio / Checkbox / Slider ─────────────────────────────────────────── */
[data-testid="stRadio"] label span,
[data-testid="stCheckbox"] label span {{ color: {txt} !important; }}
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {{
    background-color: {accent} !important;
}}

/* ══════════════════════════════════════════════════════════════════════════
   ESTILO PLATTANO HUB — cards KPI modernos, separadores, tabelas
   ══════════════════════════════════════════════════════════════════════════ */

/* Títulos de página com linha de destaque */
h1 {{
    border-left: 5px solid {accent} !important;
    padding-left: 14px !important;
    margin-bottom: 4px !important;
}}

/* Métricas — card limpo com borda-esquerda colorida */
[data-testid="stMetric"] {{
    background-color: {card} !important;
    border: 1px solid {border} !important;
    border-left: 4px solid {accent} !important;
    border-radius: 10px !important;
    padding: 16px 18px !important;
    box-shadow: {shadow} !important;
    transition: box-shadow 0.15s ease !important;
}}
[data-testid="stMetric"]:hover {{
    box-shadow: 0 4px 20px rgba(28,43,95,0.13) !important;
}}
[data-testid="stMetricLabel"] p  {{
    color: {txt2} !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}}
[data-testid="stMetricValue"] div {{
    color: {txt} !important;
    font-weight: 800 !important;
    font-size: 1.6rem !important;
}}

/* Sidebar — itens de navegação mais polidos */
[data-testid="stSidebarNav"] {{
    padding: 8px 0 !important;
}}
[data-testid="stSidebarNav"] a {{
    color: rgba(255,255,255,0.80) !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    margin: 2px 8px !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    transition: all 0.15s ease !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
}}
[data-testid="stSidebarNav"] a:hover {{
    background-color: rgba(196,21,58,0.20) !important;
    color: #FFFFFF !important;
}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background-color: rgba(196,21,58,0.32) !important;
    color: #FFFFFF !important;
    border-left: 3px solid #C4153A !important;
}}

/* Containers / cards de seção */
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {{
    background-color: transparent !important;
}}

/* Tabs com estilo mais limpo */
.stTabs [data-baseweb="tab-list"] {{
    background-color: {bg2} !important;
    border-radius: 10px !important;
    border: 1px solid {border} !important;
    padding: 4px !important;
    gap: 4px !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 7px !important;
    color: {txt2} !important;
    font-weight: 700 !important;
    font-size: 0.88rem !important;
    padding: 6px 16px !important;
}}
.stTabs [aria-selected="true"] {{
    background-color: {accent} !important;
    color: #FFFFFF !important;
    box-shadow: 0 2px 8px rgba(196,21,58,0.30) !important;
}}

/* Info / alertas mais sutis */
[data-testid="stAlert"] {{
    background-color: {card} !important;
    border-radius: 10px !important;
    border: 1px solid {border} !important;
}}

/* Expanders — linha de destaque removida (já tem a borda do card) */
[data-testid="stExpander"] {{
    background-color: {card} !important;
    border: 1px solid {border} !important;
    border-radius: 10px !important;
    box-shadow: {shadow} !important;
    margin-bottom: 4px !important;
}}
[data-testid="stExpander"] summary {{
    padding: 10px 14px !important;
}}
[data-testid="stExpander"] summary p {{
    color: {txt} !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
}}

</style>
"""
