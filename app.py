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
        overflow: hidden !important;
    }
    /* Esconder handle de resize */
    [data-testid="stSidebar"] [data-testid="stSidebarResizeHandle"] { display: none !important; }
    /* Logo centralizado — flex no anchor garante centralização */
    [data-testid="stSidebar"] a:has(img) {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
        padding: 0 !important;
        box-sizing: border-box !important;
    }
    /* Links de navegação: só ícone, centralizado */
    [data-testid="stSidebarNavLink"] {
        padding: 10px 0 !important;
        justify-content: center !important;
        gap: 0 !important;
        min-height: 44px !important;
    }
    [data-testid="stSidebarNavLink"] > *:not(:first-child) { display: none !important; }
    [data-testid="stSidebarNavLink"] > *:first-child       { font-size: 1.3rem !important; margin: 0 !important; }
    /* Conteúdo extra da sidebar (botões) */
    [data-testid="stSidebarContent"] { padding: 4px 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# ── Logo sidebar: versão sem subtítulo ────────────────────────────────────────
_logo     = Path(__file__).parent / "logo.png"               # banner
_logo_ass = Path(__file__).parent / "CDP_LOGO_ASS_A (1).png" # sidebar completa
_logo_sid = _logo_ass if _logo_ass.exists() else _logo

_logo_mini = Path(__file__).parent / "logo_mini.png"

try:
    if sidebar_oculta:
        # Mini sidebar: logo_mini.png se existir, senão símbolo circular
        _mini_path = _logo_mini if _logo_mini.exists() else _icon
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
    ]
}

pg = st.navigation(pages)
pg.run()
