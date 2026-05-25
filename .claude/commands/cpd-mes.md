# CPD — Processamento Mensal

Você está ajudando a Jessica a processar o fechamento financeiro mensal do
Colégio Primeiros Degraus. Este comando guia todo o fluxo de ponta a ponta.

---

## 1. Identificar o mês

Se a Jessica não especificou qual mês, pergunte antes de continuar.

---

## 2. Verificar os arquivos necessários

São 3 arquivos exportados do Sponte + CEF:

| Arquivo | Sistema | Tipo |
|---|---|---|
| FluxoCaixa do mês (ex: `FluxoCaixa_Abr2026.xls`) | Sponte | `.xls` ou `.xlsx` |
| Extrato bancário (ex: `Extrato_04_2026.txt`) | CEF | `.txt` |
| PlanoDeContas do mês (ex: `PlanoDeContas_Abr2026.xls`) | Sponte | `.xls` ou `.xlsx` |

Se algum estiver faltando, avise e espere antes de continuar.

---

## 3. Abrir o app (se não estiver rodando)

**Local:**
```bash
cd "/Users/jessica/Applications/CPD - App"
streamlit run app.py
```
URL: http://localhost:8501

**Na nuvem:** acesse o link do Streamlit Cloud (quando implantado).

---

## 4. Importar o mês — página "📥 Importar Mês"

1. Upload dos 3 arquivos nas colunas correspondentes
2. Verificar o mês/ano detectado automaticamente (confirmar com a Jessica)
3. Preencher os **saldos ao final do mês**:
   - **Saldo Banco**: calculado automaticamente pelo extrato — só ajusta se estiver errado
   - **Saldo Aplicação**: valor do fundo de aplicação (consultar extrato da aplicação)
   - **Saldo Caixa**: dinheiro físico no cofre/caixa da escola
4. Clicar em **✅ Confirmar importação**

---

## 5. Verificar o resultado — percorrer as páginas

### 📊 DFC / Resumo
- Checar o **Resultado Líquido** — se muito diferente do esperado, investigar
- Ajustar **AR** (Ajuste Receita) e **AD** (Ajuste Despesa) se necessário
  - AR: valores recebidos que não aparecem no Sponte (ex: transferência direta)
  - AD: despesas pagas fora do sistema (ex: dinheiro físico, reembolso manual)

### 🔍 Conciliação
- Itens conciliados automaticamente = data + tipo + valor idênticos nos dois sistemas
- Para cada item **pendente**:
  - Selecionar uma linha do Sponte e uma do Banco → **🔗 Vincular**
  - Ou selecionar só um lado → **🙈 Ignorar** com justificativa
- Justificativas comuns:
  - `saída em caixa físico` — pagamento feito em dinheiro, não aparece no banco
  - `tarifa bancária` — cobrança do banco sem lançamento no Sponte
  - `transferência entre contas` — movimentação interna
  - `diferença de data` — lançado num mês, compensado no seguinte

### 💰 Saldos
- Verificar se os saldos estão corretos
- Se precisar corrigir, usar o expander "✏️ Editar saldos deste mês"

### 📈 Evolução Mensal
- Checar se o mês recém importado aparece nos gráficos comparativos

---

## 6. Contas sem match no PlanoDeContas

Estas 4 contas do Sponte não têm equivalente direto no Book e precisam de
tratamento manual — verifique se têm valor e onde classificar:

- `2ª Via de Histórico Escolar` — receita avulsa, classificar em OUTRAS RECEITAS
- `Devolução` — depende do contexto
- `Assinaturas e Certificados Digitais` — despesa administrativa
- `Festa da Família` — evento especial

---

## 7. Finalizar

Após verificar tudo, informe um resumo:
- Total de lançamentos importados (Sponte + Banco)
- Resultado Líquido do mês
- % da conciliação completa
- Itens pendentes que precisam atenção

---

## Caminhos importantes

| O quê | Caminho |
|---|---|
| App Streamlit | `/Users/jessica/Applications/CPD - App/` |
| Script legado (CLI) | `/Users/jessica/Applications/Claude - CPD/processar_mes.py` |
| App rodando local | http://localhost:8501 |
