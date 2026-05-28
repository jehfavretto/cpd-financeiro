import streamlit as st
from pathlib import Path
import base64
from PIL import Image as PILImage
from core.theme import css_completo

_icon = Path(__file__).parent / "CDP_LOGO_CIRCULAR_A (1).png"
st.set_page_config(
    page_title="CPD Financeiro",
    page_icon=str(_icon) if _icon.exists() else "🏫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Estado global ─────────────────────────────────────────────────────────────
if "tema" not in st.session_state:
    st.session_state["tema"] = "light"
if "sidebar_oculta" not in st.session_state:
    st.session_state["sidebar_oculta"] = False

tema_atual     = st.session_state["tema"]
sidebar_oculta = st.session_state["sidebar_oculta"]
st.markdown(css_completo(tema_atual), unsafe_allow_html=True)

# ── Mini sidebar: estreitar + mostrar só ícones (nunca display:none) ──────────
if sidebar_oculta:
    st.markdown("""
    <style>
    /* Estreitar sidebar para ~68 px */
    section[data-testid="stSidebar"] {
        min-width: 68px !important;
        max-width: 68px !important;
        width:     68px !important;
        overflow: visible !important;
    }
    /* Esconder handle de resize */
    [data-testid="stSidebar"] [data-testid="stSidebarResizeHandle"] { display: none !important; }

    /* ─── Logo centralizada ─────────────────────────────────────────────
       Testids confirmados no fonte do Streamlit:
         stSidebarContent  → div com paddingLeft/Right
         stSidebarHeader   → div flex justify-content:space-between
         stLogoLink        → <a> que envolve a logo
         stSidebarLogo     → <img> da logo
         stSidebarCollapseButton → botão nativo de recolher (esconde)
       Usa seletor duplo [stSidebar][stXxx] para especificidade > tema.py
    ──────────────────────────────────────────────────────────────────── */

    /* Sem padding horizontal + overflow visible para tooltips funcionarem */
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-left: 0 !important;
        padding-right: 0 !important;
        overflow: visible !important;
    }
    /* Nav container: também precisa ser visible */
    [data-testid="stSidebar"] [data-testid="stSidebarNav"],
    [data-testid="stSidebar"] [data-testid="stSidebarNavItems"],
    [data-testid="stSidebar"] [data-testid="stSidebarNavItems"] > *,
    [data-testid="stSidebar"] [data-testid="stSidebarNavLinkContainer"] {
        overflow: visible !important;
    }
    /* Header: flex centrado (original é space-between) */
    [data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        padding: 0 !important;
        margin: 0 !important;
        background: #FFFFFF !important;
        border-radius: 0 0 10px 10px !important;
        min-height: 60px !important;
        height: auto !important;
    }
    /* Oculta botão de colapso nativo (temos o nosso próprio) */
    [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
    /* Anchor da logo */
    [data-testid="stSidebar"] [data-testid="stLogoLink"],
    [data-testid="stSidebar"] a:has(img) {
        display: inline-flex !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    /* Imagem da logo */
    [data-testid="stSidebar"] [data-testid="stSidebarLogo"],
    [data-testid="stSidebar"] a:has(img) img {
        width: 36px !important;
        height: 36px !important;
        object-fit: contain !important;
        display: block !important;
        border-radius: 50% !important;
    }

    /* Links de navegação: só ícone, centralizado */
    [data-testid="stSidebarNavLink"] {
        position: relative !important;
        padding: 10px 0 !important;
        justify-content: center !important;
        gap: 0 !important;
        min-height: 44px !important;
    }
    /* Ícone */
    [data-testid="stSidebarNavLink"] > *:first-child { font-size: 1.3rem !important; margin: 0 !important; }
    /* Label: escondida, vira tooltip no hover */
    [data-testid="stSidebarNavLink"] > *:not(:first-child) {
        position: absolute !important;
        left: 100% !important;
        margin-left: 8px !important;
        top: 50% !important;
        transform: translateY(-50%) !important;
        background: #1C2B5F !important;
        color: #FFFFFF !important;
        padding: 5px 12px !important;
        border-radius: 6px !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        white-space: nowrap !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.25) !important;
        z-index: 99999 !important;
        opacity: 0 !important;
        visibility: hidden !important;
        pointer-events: none !important;
        transition: opacity 0.15s, visibility 0.15s !important;
        display: block !important;
    }
    /* Mostrar tooltip ao hover */
    [data-testid="stSidebarNavLink"]:hover > *:not(:first-child) {
        opacity: 1 !important;
        visibility: visible !important;
    }
    /* Conteúdo extra da sidebar (botões) */
    [data-testid="stSidebarContent"] { padding: 4px 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# ── Logo sidebar: versão sem subtítulo ────────────────────────────────────────
_logo     = Path(__file__).parent / "logo.png"               # banner
_logo_ass = Path(__file__).parent / "CDP_LOGO_ASS_A (1).png" # sidebar completa
_logo_sid = _logo_ass if _logo_ass.exists() else _logo

_logo_mini = next(
    (Path(__file__).parent / f for f in ["logo_mini.jpg", "logo_mini.png"] if (Path(__file__).parent / f).exists()),
    None
)

try:
    if sidebar_oculta:
        # Mini sidebar: logo_mini (jpg ou png) se existir, senão símbolo circular
        _mini_path = _logo_mini if _logo_mini else _icon
        _icon_img = PILImage.open(str(_mini_path))
        st.logo(_icon_img, size="small")
    elif _logo_sid.exists():
        # Sidebar completa: logo com nome, sem subtítulo
        _img = PILImage.open(str(_logo_sid))
        w, h = _img.size
        _img_crop = _img.crop((0, 0, w, int(h * 0.85)))
        st.logo(_img_crop, size="medium")
except Exception:
    pass

# ── Logo base64 para o banner — usa logo.png original (com subtítulo) ─────────
_logo_b64 = base64.b64encode(_logo.read_bytes()).decode() if _logo.exists() else ""
icone_tema = "☀️" if tema_atual == "dark" else "🌙"

logo_html = (
    f'<div class="cpd-banner-logo-card">'
    f'<img src="data:image/png;base64,{_logo_b64}" class="cpd-banner-logo-img">'
    f'</div>'
    if _logo_b64
    else '<span class="cpd-banner-title">Colégio Primeiros Degraus</span>'
)

# ── Banner CPD com ondas ────────────────────────────────────────────────────────
st.markdown(f"""
<div class="cpd-banner">
    <svg class="cpd-onda cpd-onda-esq" viewBox="0 0 240 220" xmlns="http://www.w3.org/2000/svg">
        <circle cx="0" cy="220" r="185" fill="none" stroke="#C4153A" stroke-width="26"/>
    </svg>
    <svg class="cpd-onda cpd-onda-dir" viewBox="0 0 240 220" xmlns="http://www.w3.org/2000/svg">
        <circle cx="240" cy="0" r="185" fill="none" stroke="#C4153A" stroke-width="26"/>
    </svg>
    <div class="cpd-banner-inner">
        {logo_html}
    </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
# Âncoras invisíveis antes de cada botão permitem identificá-los no CSS
# via seletor de sibling adjacente (+), independente do testid interno do Streamlit.
with st.sidebar:
    st.markdown('<div id="cpd-tema-anchor"></div>', unsafe_allow_html=True)
    if st.button(icone_tema, key="btn_tema"):
        st.session_state["tema"] = "light" if tema_atual == "dark" else "dark"
        st.rerun()

    st.markdown('<div id="cpd-recolher-anchor"></div>', unsafe_allow_html=True)
    if sidebar_oculta:
        if st.button("▶", key="btn_expandir"):
            st.session_state["sidebar_oculta"] = False
            st.rerun()
    else:
        if st.button("◀", key="btn_recolher"):
            st.session_state["sidebar_oculta"] = True
            st.rerun()

# ── Navegação ──────────────────────────────────────────────────────────────────
pages = {
    "": [
        st.Page("pages/1_Importar.py",    title="Importar Mês",      icon="📥"),
        st.Page("pages/2_DFC.py",         title="DFC / Resumo",      icon="📊"),
        st.Page("pages/3_Conciliacao.py", title="Conciliação",       icon="🔍"),
        st.Page("pages/4_Evolucao.py",    title="Evolução Mensal",   icon="📈"),
        st.Page("pages/5_Saldos.py",      title="Saldos",            icon="💰"),
        st.Page("pages/6_Alunos.py",      title="Alunos",            icon="👨‍🎓"),
    ]
}

pg = st.navigation(pages)
pg.run()
