-- ============================================================
-- CPD Financeiro — Schema do Supabase
-- Cole e execute no SQL Editor do Supabase (uma vez só)
-- ============================================================

-- PlanoDeContas: valores mensais por conta
CREATE TABLE IF NOT EXISTS plano_contas (
    id          BIGSERIAL PRIMARY KEY,
    mes         INT  NOT NULL,
    ano         INT  NOT NULL,
    codigo      TEXT NOT NULL,
    descricao   TEXT NOT NULL,
    valor       NUMERIC(14, 2) NOT NULL DEFAULT 0,
    UNIQUE (mes, ano, codigo)
);

-- Lançamentos do Sponte (FluxoCaixa)
CREATE TABLE IF NOT EXISTS lancamentos_sponte (
    id              BIGSERIAL PRIMARY KEY,
    mes             INT  NOT NULL,
    ano             INT  NOT NULL,
    data            DATE,
    data_rep        DATE,
    categoria       TEXT,
    es              TEXT,
    origem_destino  TEXT,
    valor           NUMERIC(14, 2)
);

-- Transações do extrato bancário CEF
CREATE TABLE IF NOT EXISTS transacoes_banco (
    id          BIGSERIAL PRIMARY KEY,
    mes         INT  NOT NULL,
    ano         INT  NOT NULL,
    data_mov    TEXT,
    nr_doc      TEXT,
    historico   TEXT,
    valor       NUMERIC(14, 2),
    deb_cred    TEXT
);

-- Saldos mensais (banco, aplicação, caixa)
CREATE TABLE IF NOT EXISTS saldos (
    id                  BIGSERIAL PRIMARY KEY,
    mes                 INT  NOT NULL,
    ano                 INT  NOT NULL,
    saldo_banco         NUMERIC(14, 2) DEFAULT 0,
    saldo_aplicacao     NUMERIC(14, 2) DEFAULT 0,
    saldo_caixa         NUMERIC(14, 2) DEFAULT 0,
    UNIQUE (mes, ano)
);

-- Ajustes manuais: AR (Ajuste Receita) e AD (Ajuste Despesa)
CREATE TABLE IF NOT EXISTS ajustes (
    id      BIGSERIAL PRIMARY KEY,
    mes     INT  NOT NULL,
    ano     INT  NOT NULL,
    tipo    TEXT NOT NULL,   -- 'AR' ou 'AD'
    valor   NUMERIC(14, 2) DEFAULT 0,
    UNIQUE (mes, ano, tipo)
);

-- Índices para acelerar consultas por mês/ano
CREATE INDEX IF NOT EXISTS idx_plano_mes_ano       ON plano_contas      (mes, ano);
CREATE INDEX IF NOT EXISTS idx_lancamentos_mes_ano ON lancamentos_sponte (mes, ano);
CREATE INDEX IF NOT EXISTS idx_banco_mes_ano       ON transacoes_banco  (mes, ano);
CREATE INDEX IF NOT EXISTS idx_saldos_mes_ano      ON saldos            (mes, ano);
CREATE INDEX IF NOT EXISTS idx_ajustes_mes_ano     ON ajustes           (mes, ano);
