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

# ── Tema ──────────────────────────────────────────────────────────────────────
if "tema" not in st.session_state:
    st.session_state["tema"] = "light"

tema_atual = st.session_state["tema"]
st.markdown(css_completo(tema_atual), unsafe_allow_html=True)

# ── Logo no topo da sidebar — símbolo circular (acima dos itens de navegação) ─
_logo     = Path(__file__).parent / "logo.png"
_logo_icn = Path(__file__).parent / "CDP_LOGO_CIRCULAR_A (1).png"
_logo_sid = _logo_icn if _logo_icn.exists() else _logo
if _logo_sid.exists():
    try:
        st.logo(PILImage.open(str(_logo_sid)), size="medium")
    except Exception:
        pass

# ── Logo base64 para o banner ─────────────────────────────────────────────────
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

# ── Toggle de tema — canto superior direito (fixo via CSS) ─────────────────────
# O botão é renderizado aqui mas posicionado via CSS position:fixed no canto
_, col_btn = st.columns([30, 1])
with col_btn:
    if st.button(icone_tema, key="btn_tema", help="Alternar tema claro/escuro"):
        st.session_state["tema"] = "light" if tema_atual == "dark" else "dark"
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
