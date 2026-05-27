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

# ── Toggle sidebar via query params (evita conflito com CSS do btn_tema) ──────
if st.query_params.get("expand") == "1":
    st.session_state["sidebar_oculta"] = False
    st.query_params.clear()
    st.rerun()
if st.query_params.get("recolher") == "1":
    st.session_state["sidebar_oculta"] = True
    st.query_params.clear()
    st.rerun()

# ── Estado global ─────────────────────────────────────────────────────────────
if "tema" not in st.session_state:
    st.session_state["tema"] = "light"
if "sidebar_oculta" not in st.session_state:
    st.session_state["sidebar_oculta"] = False

tema_atual     = st.session_state["tema"]
sidebar_oculta = st.session_state["sidebar_oculta"]
st.markdown(css_completo(tema_atual), unsafe_allow_html=True)

# ── Ocultar sidebar + mostrar botão flutuante ▶ fixo na borda esquerda ────────
if sidebar_oculta:
    st.markdown("""
    <style>
    section[data-testid='stSidebar'] { display: none !important; }
    </style>
    <a href="?expand=1"
       title="Expandir barra lateral"
       style="
         position: fixed;
         top: 50%;
         left: 0;
         transform: translateY(-50%);
         background: #1C2B5F;
         color: white !important;
         padding: 18px 8px;
         border-radius: 0 8px 8px 0;
         z-index: 9999;
         font-size: 20px;
         text-decoration: none;
         font-weight: bold;
         box-shadow: 2px 2px 8px rgba(0,0,0,0.25);
       ">▶</a>
    """, unsafe_allow_html=True)

# ── Logo sidebar: versão sem subtítulo ────────────────────────────────────────
_logo     = Path(__file__).parent / "logo.png"               # banner
_logo_ass = Path(__file__).parent / "CDP_LOGO_ASS_A (1).png" # sidebar
_logo_sid = _logo_ass if _logo_ass.exists() else _logo

if _logo_sid.exists():
    try:
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

# ── Sidebar: tema (botão real) + recolher (link HTML, não quebra CSS do tema) ──
with st.sidebar:
    if st.button(icone_tema, key="btn_tema"):
        st.session_state["tema"] = "light" if tema_atual == "dark" else "dark"
        st.rerun()
    # Link HTML em vez de st.button — evita que o CSS position:fixed do tema
    # seja aplicado a dois botões ao mesmo tempo
    st.markdown(
        '<a href="?recolher=1" style="'
        'display:block;text-align:center;margin-top:48px;'
        'color:rgba(255,255,255,0.55)!important;text-decoration:none;'
        'font-size:0.78rem;letter-spacing:0.03em;'
        '">◀ Recolher barra</a>',
        unsafe_allow_html=True,
    )

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
