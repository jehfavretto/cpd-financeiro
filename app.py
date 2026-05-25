import streamlit as st
from pathlib import Path
import base64
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

# ── Logo ───────────────────────────────────────────────────────────────────────
_logo = Path(__file__).parent / "logo.png"
_logo_b64 = base64.b64encode(_logo.read_bytes()).decode() if _logo.exists() else ""
icone_tema = "☀️" if tema_atual == "dark" else "🌙"

# ── Banner CPD com ondas ────────────────────────────────────────────────────────
logo_html = (
    f'<div class="cpd-banner-logo-card">'
    f'<img src="data:image/png;base64,{_logo_b64}" class="cpd-banner-logo-img">'
    f'</div>'
    if _logo_b64
    else '<span class="cpd-banner-title">Colégio Primeiros Degraus</span>'
)

st.markdown(f"""
<div class="cpd-banner">
    <!-- Onda esquerda — canto superior esquerdo, UM arco bem grosso -->
    <svg class="cpd-onda cpd-onda-esq" viewBox="0 0 300 280" xmlns="http://www.w3.org/2000/svg">
        <circle cx="0" cy="0" r="210" fill="none" stroke="#C4153A" stroke-width="64"/>
    </svg>
    <!-- Onda direita — canto superior direito, UM arco bem grosso -->
    <svg class="cpd-onda cpd-onda-dir" viewBox="0 0 300 280" xmlns="http://www.w3.org/2000/svg">
        <circle cx="300" cy="0" r="210" fill="none" stroke="#C4153A" stroke-width="64"/>
    </svg>
    <!-- Logo -->
    <div class="cpd-banner-inner">
        {logo_html}
    </div>
</div>
""", unsafe_allow_html=True)

# ── Toggle de tema — flutuante no topo direito ─────────────────────────────────
col_sp, col_btn = st.columns([30, 1])
with col_btn:
    st.markdown('<div id="cpd-toggle-anchor">', unsafe_allow_html=True)
    if st.button(icone_tema, key="btn_tema", help="Alternar tema claro/escuro"):
        st.session_state["tema"] = "light" if tema_atual == "dark" else "dark"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

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
