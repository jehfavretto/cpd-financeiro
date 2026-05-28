# CPD Financeiro — Instruções para o assistente

## Regra principal de deploy

**Após qualquer alteração de código, sempre fazer commit + push imediatamente**, sem esperar a usuária pedir.
O app roda no **Streamlit Cloud** — mudanças em arquivos locais NÃO aparecem no app até o push.

```bash
git add <arquivo>
git commit -m "mensagem"
git push
```

Nunca dizer "recarregue o app" ou "aguarde o Streamlit atualizar" sem ter feito o push antes.

## Stack

- **App:** Streamlit (Streamlit Cloud) — https://ad2jxgrkpssqk4dewzls67.streamlit.app/
- **Banco:** Supabase (variáveis em `.streamlit/secrets.toml`)
- **Repo:** https://github.com/jehfavretto/cpd-financeiro — branch `main` → deploy automático
- **Local:** `/Users/jessica/Applications/CPD - App/`

## Estrutura de arquivos

```
app.py                  # Home, sidebar, tema, navegação
pages/
  1_Importar.py         # Upload XLS/TXT → parse → Supabase + saldos
  2_DFC.py              # Demonstrativo de Fluxo de Caixa
  3_Conciliacao.py      # Conciliação Sponte ↔ Extrato Banco
  4_Evolucao.py         # Gráficos mês a mês
  5_Saldos.py           # Saldos banco/aplicação/caixa
core/
  parser.py             # parse_sponte_fluxo, parse_banco_txt, parse_sponte_plano
  dfc.py                # calcular_dfc(), SECOES
  theme.py              # css_completo(tema)
  utils.py              # fmt_br(), fmt_br_kpi()
db/
  client.py             # get_client() + todas as funções salvar_*/carregar_*
```

## Conciliação (3_Conciliacao.py) — pontos críticos

### Chave de matching
`DD/MM|E/S|valor` com vírgula decimal — ex: `06/01|S|1644,00`

### Vínculos 1:N
Salvar como **um único registro** com `banco_chave` separado por `§§`
(ex: `06/01|S|100,00§§06/01|S|200,00`). Nunca salvar N registros com mesmo `sponte_chave`.

### Lógica de pendentes usa Counter
`Counter` por chave para contar disponíveis após subtrair manuais já usados.
Não usar set exclusion (quebra duplicatas).

### `$` em markdown
Sempre escapar: `_md_val(v)` para markdown, `_html_val(v)` para HTML inline.

## CSS / Sidebar

- Sidebar mini (68px): `sidebar_oculta = True` em `app.py`
- Tooltips de nav: `overflow: visible` em todos os containers ancestrais
- Testids relevantes: `stSidebarHeader`, `stLogoLink`, `stSidebarLogo`, `stSidebarCollapseButton`
- Especificidade: usar `[data-testid="stSidebar"] [data-testid="stXxx"]` (duplo) para sobrescrever tema

## Banco de dados (Supabase)

| Tabela | Chave única |
|---|---|
| `plano_contas` | (mes, ano, codigo) |
| `lancamentos_sponte` | delete+insert por mês |
| `transacoes_banco` | delete+insert por mês |
| `saldos` | (mes, ano) |
| `ajustes` | (mes, ano, tipo) — tipo: `AR` ou `AD` |
| `conciliacoes` | append — tipo: `manual`, `ignorado_sponte`, `ignorado_banco`, `desvincular` |
