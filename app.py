import streamlit as st
from pathlib import Path
import base64

_icon = Path(__file__).parent / "CDP_LOGO_CIRCULAR_A (1).png"
st.set_page_config(
    page_title="CPD Financeiro",
    page_icon=str(_icon) if _icon.exists() else "🏫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Identidade visual CPD ──────────────────────────────────────────────────────
st.markdown("""
<style>
/* Sidebar: fundo azul escuro CPD */
[data-testid="stSidebar"] {
    background-color: #1C2B5F !important;
}
[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label {
    color: #FFFFFF !important;
}
/* Links de navegação na sidebar */
[data-testid="stSidebarNav"] a {
    color: rgba(255,255,255,0.85) !important;
    border-radius: 6px;
    padding: 4px 8px;
}
[data-testid="stSidebarNav"] a:hover,
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background-color: rgba(196,21,58,0.25) !important;
    color: #FFFFFF !important;
}
/* Botões primários: vermelho CPD */
.stButton > button[kind="primary"] {
    background-color: #C4153A !important;
    border-color: #C4153A !important;
    color: #FFFFFF !important;
    border-radius: 6px;
}
.stButton > button[kind="primary"]:hover {
    background-color: #A01030 !important;
    border-color: #A01030 !important;
}
/* Métricas: borda azul esquerda */
[data-testid="stMetric"] {
    border-left: 4px solid #C4153A;
    padding-left: 12px;
}
/* Cabeçalho da sidebar */
.cpd-header {
    text-align: center;
    padding: 12px 0 4px 0;
}
.cpd-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #FFFFFF;
    margin: 0;
    line-height: 1.3;
}
.cpd-sub {
    font-size: 0.75rem;
    color: rgba(255,255,255,0.65);
    margin: 0;
    font-style: italic;
}
.cpd-divider {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.2);
    margin: 10px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Cabeçalho lateral ──────────────────────────────────────────────────────────
with st.sidebar:
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
        <div class="cpd-header">
            <p class="cpd-title">Colégio Primeiros Degraus</p>
            <p class="cpd-sub">Evoluindo a cada passo.</p>
        </div>
        """, unsafe_allow_html=True)
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
