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

# Injeta CSS do tema escolhido
st.markdown(css_completo(st.session_state["tema"]), unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo em card branco (visível na sidebar escura)
    _logo = Path(__file__).parent / "logo.png"
    if _logo.exists():
        _img_b64 = base64.b64encode(_logo.read_bytes()).decode()
        st.markdown(
            f'<div style="background:#FFFFFF; border-radius:10px; padding:14px 12px 10px 12px;'
            f' margin:8px 4px 12px 4px; text-align:center;">'
            f'<img src="data:image/png;base64,{_img_b64}" style="max-width:100%; height:auto;">'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown("""
        <div style="text-align:center; padding:12px 0 4px 0;">
            <p style="font-size:1.1rem; font-weight:800; color:#FFF; margin:0;">Colégio Primeiros Degraus</p>
            <p style="font-size:0.75rem; color:rgba(255,255,255,0.65); margin:0; font-style:italic;">Evoluindo a cada passo.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr class="cpd-divider"/>', unsafe_allow_html=True)

    # ── Toggle claro / escuro ──────────────────────────────────────────────
    tema_atual = st.session_state["tema"]
    icone  = "☀️" if tema_atual == "dark" else "🌙"
    rotulo = "Modo Claro" if tema_atual == "dark" else "Modo Escuro"

    if st.button(f"{icone} {rotulo}", key="btn_tema", use_container_width=True):
        st.session_state["tema"] = "light" if tema_atual == "dark" else "dark"
        st.rerun()

    st.markdown('<hr class="cpd-divider"/>', unsafe_allow_html=True)

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
