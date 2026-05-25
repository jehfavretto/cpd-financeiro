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

# ── Tema (claro / escuro) ──────────────────────────────────────────────────────
if "tema" not in st.session_state:
    st.session_state["tema"] = "light"

tema_atual = st.session_state["tema"]

# Injeta CSS do tema escolhido
st.markdown(css_completo(tema_atual), unsafe_allow_html=True)

# ── Logo: topo da sidebar (via API oficial — renderiza ACIMA dos itens de nav) ──
_logo = Path(__file__).parent / "logo.png"
if _logo.exists():
    st.logo(str(_logo))

# ── Header do conteúdo principal: logo esquerda + toggle direita ───────────────
_logo_b64 = base64.b64encode(_logo.read_bytes()).decode() if _logo.exists() else ""
icone_tema = "☀️" if tema_atual == "dark" else "🌙"

col_logo, _gap, col_toggle = st.columns([3, 9, 1])

with col_logo:
    if _logo_b64:
        st.markdown(
            f'<div style="padding:2px 0;">'
            f'<img src="data:image/png;base64,{_logo_b64}"'
            f' style="height:40px; width:auto;">'
            f'</div>',
            unsafe_allow_html=True,
        )

with col_toggle:
    st.markdown('<div class="cpd-toggle-wrap">', unsafe_allow_html=True)
    if st.button(icone_tema, key="btn_tema", help="Alternar tema claro/escuro"):
        st.session_state["tema"] = "light" if tema_atual == "dark" else "dark"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<hr class="cpd-header-divider"/>', unsafe_allow_html=True)

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
