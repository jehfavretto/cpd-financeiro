import streamlit as st

st.set_page_config(
    page_title="CPD Financeiro",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Navegação ─────────────────────────────────────────────────────────────────
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

# ── Cabeçalho lateral ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏫 CPD Financeiro")
    st.markdown("Colégio Primeiros Degraus")
    st.divider()

pg.run()
