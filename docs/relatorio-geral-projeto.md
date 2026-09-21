# Relatório geral do projeto Nivra

> Controle financeiro inteligente, simples e automatizado.

Este documento consolida os relatórios de implementação, migração,
segurança, Open Finance, parcelamentos e inteligência financeira que estavam
espalhados em vários arquivos. Ele serve como registro técnico e histórico do
projeto. O progresso oficial continua sendo controlado por
[`docs/roadmap.md`](roadmap.md), e o código, o banco e os testes permanecem as
fontes de verdade quando houver diferença entre um relato histórico e o
estado atual.

**Consolidação:** 21 de setembro de 2026  
**Produto:** Nivra  
**Status:** Alpha funcional  
**Aplicação:** <https://nivra-finance.vercel.app>  
**Repositório:** `joaordantas/Nivra`  
**Banco oficial:** PostgreSQL no Neon  
**Hospedagem:** Vercel

## 1. Visão do produto

A Nivra evoluiu de um controle financeiro pessoal para uma plataforma que
reduz o tempo necessário para registrar, consultar e compreender as próprias
finanças. O produto prioriza contexto, automação progressiva e avisos úteis.

**Lumi** é o nome da futura assistente financeira. A identidade está definida,
mas a assistente, o modelo de linguagem e o tool calling ainda não foram
implementados. A Nivra permanece em Alpha e não deve ser apresentada como um
produto financeiro pronto para produção crítica.

## 2. Linha do tempo consolidada

| Marco | Resultado |
| --- | --- |
| Fundação e núcleo financeiro | React/TypeScript/Vite, FastAPI, navegação responsiva, contas, transações, categorias, transferências e dashboard |
| Infraestrutura | PostgreSQL/Neon, SQLAlchemy Core, Psycopg 3, Alembic, importador SQLite e deploy React + FastAPI na Vercel |
| Autenticação segura | Sessões server-side, cookies HTTP-only, CSRF, isolamento por usuário e hardening de conta |
| Cartões e faturas | Cartões, compras, ciclos, limites, estados de fatura e pagamento integral integrado às contas |
| Open Finance MVP | Pluggy Sandbox, persistência, sincronização, idempotência, integração com o núcleo, webhooks, UX, demo e conciliação |
| Parcelamentos | Entidade de parcelamento, parcelas, projeções, UX de criação/edição e rota mobile dedicada |
| Inteligência determinística | Insights, projeção de cartões, tendências, contexto financeiro estruturado e área inicial “Sua atenção” |

## 3. Fundação e experiência do frontend

O frontend foi reconstruído em React + TypeScript + Vite com React Router,
layout desktop, navegação mobile, sidebar, bottom navigation, botão de ação
rápida e componentes reutilizáveis. O design system possui tema claro e escuro,
tipografia consistente, estados de carregamento/erro/vazio, responsividade e
safe area para dispositivos móveis.

A identidade pública usa **Nivra**. Serviços, vendas e outras áreas comerciais
foram retirados da navegação principal durante a fase financeira pessoal. A
interface atual contempla dashboard, transações, contas, cartões, faturas,
parcelamentos, configurações e a experiência de Open Finance.

Foram corrigidos os fluxos de logout desktop e mobile, inclusive o menu “Mais”
e a navegação inferior. A aplicação foi validada nos tamanhos de referência
375, 390, 430, 612 e 1440 px durante as revisões de UX.

## 4. Núcleo financeiro

O núcleo mantém as regras no fluxo Router → Schema → Service → Repository →
Database. As funcionalidades disponíveis são:

- contas financeiras com saldo inicial, saldo atual, saldo consolidado, conta
  principal e conta mais utilizada;
- receitas, despesas, edição, exclusão e histórico;
- transferências atômicas entre contas, sem contar como receita ou despesa;
- categorias privadas por usuário, categorias padrão com `chave_sistema` e
  categorias personalizadas;
- busca e filtros de movimentações;
- dashboard com saldo, entradas, gastos, economia, transações recentes e o
  bloco inicial “Sua atenção”;
- isolamento lógico das informações por usuário no backend.

As categorias padrão são criadas para usuários existentes pela migration e para
novos usuários no service de cadastro. Categorias padrão não podem ser
excluídas, podem ser renomeadas sem perder sua chave estável e usam `other`
como fallback do mapeamento externo. Categorias personalizadas continuam com o
CRUD atual.

## 5. Cartões e faturas

A fase de cartões foi entregue em Alpha. É possível criar e editar cartões,
ativá-los ou desativá-los, informar limites e dias de fechamento/vencimento,
registrar compras e consultar ciclos de fatura. O sistema representa faturas
abertas, fechadas, vencidas e pagas, incluindo virada de mês, ano, fevereiro e
ano bissexto.

O pagamento integral reduz o saldo da conta e libera o limite sem criar uma
segunda despesa econômica. A compra no cartão permanece a despesa econômica;
seu pagamento é liquidação. As regras foram mantidas durante a integração com
Open Finance.

## 6. Parcelamentos

A Prioridade 3.1 criou a entidade `parcelamentos` relacionada à transação e às
parcelas, com valor total, quantidade, valor por parcela, datas, parcela atual,
parcelas restantes, status e ownership. Valores usam `NUMERIC`/`Decimal` e a
divisão de centavos distribui o restante de forma determinística.

A Prioridade 3.2 integrou parcelamentos ao fluxo de transações: criação,
listagem, detalhe, edição e exclusão segura. A interface mostra badges de
parcela, estado temporal e acesso mobile dedicado em `/installments`. A UX foi
validada em desktop e nos tamanhos móveis definidos. A integração específica
com cartões/faturas, recorrências, orçamentos e metas permanece fora desta
entrega.

## 7. Autenticação e segurança

### Base segura

- sessões server-side persistidas no PostgreSQL;
- token de sessão guardado somente como hash;
- cookie HTTP-only, Secure em produção, SameSite e expiração;
- `/api/auth/me`, `current_user`, logout com revogação e remoção do cookie;
- CSRF no login, cadastro e operações de escrita;
- APIs privadas sem aceitar `usuario_id` do frontend como autoridade;
- validação de ownership para contas, transações, categorias, cartões, faturas,
  transferências, conexões e candidatos de conciliação.

### Hardening

Foram adicionados fluxos de verificação de e-mail, recuperação de senha,
alteração de senha, tokens de uso único armazenados como hash, expiração,
revogação de sessões após redefinição e rate limiting compatível com o
ambiente serverless. A integração de e-mail exige configuração externa (como
Resend) e seus segredos ficam somente no backend.

O sistema continua em evolução para produção: recuperação, verificação e
limites precisam permanecer cobertos por testes e observabilidade quando a
aplicação for aberta a um grupo maior. Nenhum frontend deve confiar em
`localStorage` para identidade.

## 8. Banco, migrations e deploy

O banco oficial é PostgreSQL no Neon. A camada de acesso usa SQLAlchemy Core e
Psycopg 3, sem ORM obrigatório. Alembic versiona o schema; a aplicação não
recria tabelas no startup serverless. O head atual registrado no projeto é
`f7b3c1d8e920`.

As migrations cobrem usuários, sessões, categorias, contas, transações,
transferências, cartões, compras, faturas, pagamentos, Open Finance,
parcelamentos, conciliação e as estruturas de segurança. Valores financeiros
usam `NUMERIC`, datas financeiras usam `DATE`, foreign keys, constraints e
índices protegem integridade e consultas frequentes.

O SQLite legado (`storage/banco.db`) deixou de ser a fonte de produção. Ele foi
mantido como origem/backup do desenvolvimento e pode ser importado pelo
script seguro de migração. O importador preserva IDs quando possível, é
idempotente, não apaga o SQLite e exige opção explícita para os três órfãos
conhecidos; órfãos novos continuam bloqueando a execução.

Variáveis sensíveis, como `DATABASE_URL`, ficam no ambiente local ou na Vercel.
Nenhuma connection string, senha, Client Secret ou token deve estar no
frontend, na documentação pública ou no Git.

## 9. Open Finance MVP

O Open Finance foi desenvolvido em etapas com Pluggy Sandbox. Bancos reais e
o ambiente Production da Pluggy continuam desabilitados.

### 2A — Provider e Sandbox

Foi criada uma abstração de provider Pluggy com credenciais somente no backend,
cache de autenticação, geração de Connect Token e integração do widget Connect
no frontend. A ausência de configuração Pluggy não impede auth, dashboard,
contas ou transações; somente o endpoint de Connect Token falha de modo
controlado.

### 2B — Persistência

A migration `e81f72c4a93b` criou `conexoes_bancarias`,
`contas_bancarias_externas`, `transacoes_bancarias` e
`eventos_sincronizacao`, com ownership, foreign keys, unicidade e timestamps.
Conexões persistem após F5, logout/login e novos deployments.

### 2B.5 — Categorias padrão

O mapper central traduz provider/category IDs para chaves internas Nivra, com
fallback `other`. O mapeamento não depende do texto exibido ao usuário e não
cria categorias arbitrárias recebidas do banco.

### 2C e 2D — Sincronização e idempotência

A sincronização importa instituições, contas, saldos e transações com
paginação, atualiza registros existentes, trata remoções e registra eventos.
Chaves externas e upserts evitam duplicação em reprocessamentos. O fluxo é
idempotente e mantém a última sincronização e os erros de forma controlada.

### 2D.5 — Integração com o núcleo

Contas externas podem criar uma conta Nivra ou ser vinculadas a uma conta já
existente. O vínculo é protegido por ownership e unicidade. Saldos do provider
são exibidos como saldo bancário da conta vinculada, e o histórico combina
movimentações manuais e bancárias sem copiar fisicamente registros de forma
desnecessária. A conciliação básica evita dupla contabilização.

### 2E — Webhooks

O endpoint público recebe webhooks Pluggy com segredo no backend, persiste a
inbox e processa eventos suportados (`item/updated`, `item/error`,
`transactions/created`, `transactions/updated` e `transactions/deleted`).
Eventos desconhecidos são ignorados com segurança. A inbox possui unicidade por
`provider` + `provider_event_id`, lease/retry e processamento idempotente.

Há evidência real em produção de entregas Pluggy com HTTP 200 para
`item/updated`, `transactions/updated` e `transactions/created`. A repetição
externa do mesmo eventId ainda não foi observada; os testes automatizados e a
constraint cobrem esse comportamento.

### 2F — UX Open Finance

A página Contas apresenta conexão, ambiente Sandbox, estado, última
sincronização, atualização manual, contas externas, saldos, vínculo/criação de
conta Nivra e cartões externos somente leitura. Há estados de carregamento,
erro, atenção e conta não vinculada, com adaptação para desktop e mobile.

### 2G — Demo para testers

Foi criado um fluxo guiado curto e o guia
[`docs/testing/open-finance-sandbox.md`](testing/open-finance-sandbox.md).
O tester é avisado de que o ambiente é demonstração, recebe apenas credenciais
fictícias oficiais do Sandbox (`user-ok`, `password-ok`, MFA `123456`) e é
orientado a nunca informar dados bancários reais. O guia inclui checklist
desktop/mobile e modelo de relato de bug.

### 2H — Conciliação avançada

O motor compara valor, direção, conta relacionada e datas próximas, calcula
confiança, mantém candidatos e decisões persistidas (sugerida, confirmada,
rejeitada ou reaberta), suporta confirmação/rejeição individuais e em lote e
preserva os registros físicos. Após confirmação, manual + banco representam um
único evento econômico no histórico e no dashboard. Alterações relevantes na
transação bancária podem reabrir a decisão; reprocessamentos não duplicam
efeitos.

### Gate técnico do Open Finance

O gate técnico foi aprovado sem blocker de segurança, persistência,
idempotência ou duplicação econômica. O gate externo permanece pendente para:

- repetição real do mesmo eventId pela Pluggy;
- validação de aceitação por testers independentes em dispositivos e
  navegadores reais.

Essas pendências não significam que o código de webhook ou conciliação esteja
sem cobertura; elas são evidências externas que não devem ser inventadas.

## 10. Inteligência financeira e preparação para Lumi

As entregas P5.1–P5.3 criaram um motor determinístico antes de qualquer IA:

- `/api/insights` calcula resumo, comparação de períodos, categorias, maiores e
  gastos incomuns, situação de orçamentos e alertas de atenção;
- projeções distinguem realizado, conhecido futuro e projetado, incluindo
  compromissos de cartões e faturas próximas;
- tendências usam períodos comparáveis e crescimento de gastos;
- `get_financial_context` fornece contexto estruturado para uma futura camada
  de tools, sempre com a identidade da sessão;
- transferências internas, conciliação e pagamentos de fatura não são tratados
  como novas despesas econômicas.

Não existe chat, modelo de linguagem, tool calling efetivo ou ação financeira
autônoma. A próxima unidade prevista no roadmap é o refinamento determinístico
de recorrências e gastos fora do padrão, antes da implementação da Lumi.

## 11. Arquitetura atual

```text
React + TypeScript
        ↓ REST
FastAPI / routers
        ↓
Schemas
        ↓
Services (regras e ownership)
        ↓
Repositories (persistência)
        ↓ SQLAlchemy Core + Psycopg 3
PostgreSQL / Neon
```

O frontend não acessa o banco. Routers permanecem finos, services concentram
regras financeiras e repositories cuidam de consultas e mutações. Pluggy é
acessado somente pelo backend; a integração é lazy/on-demand.

## 12. Evidências de validação

As contagens abaixo são snapshots por etapa e não devem ser somadas: 

- base de autenticação: 44 testes registrados no relatório da etapa;
- hardening de conta: suíte geral e testes específicos de tokens, sessões,
  rate limit e IDOR/BOLA;
- Open Finance e conciliação: 102 testes na validação final da Prioridade 2;
- parcelamentos e UX mobile: 118 testes na revisão P3.2;
- inteligência P5.1–P5.3: 135 testes na última consolidação local;
- build React/TypeScript, compilação Python, `alembic check` e `git diff --check`
  foram executados nas validações correspondentes.

O resultado exato de uma execução deve ser sempre confirmado no CI ou na
execução local atual, pois os relatórios históricos preservam o número da
época em que cada etapa foi validada.

## 13. Limitações e pendências

- Open Finance continua em Sandbox; bancos reais exigem gate separado,
  consentimento, privacidade e revisão LGPD.
- A repetição externa real do mesmo webhook ainda não foi produzida.
- Testers independentes ainda precisam executar o checklist completo.
- Parcelamentos ainda não cobrem toda a futura integração com cartões, e
  recorrências, orçamentos e metas seguem no roadmap.
- O motor de insights é determinístico; Lumi, IA, notificações e WhatsApp não
  estão implementados.
- Paginação ampla, observabilidade, política de privacidade, termos, backup e
  demais itens de production readiness continuam pendentes.

Essas limitações mantêm o produto em Alpha e não devem ser ocultadas em uma
apresentação pública.

## 14. Organização documental

Este arquivo substitui os relatórios individuais de implementação que estavam
espalhados em `docs/relatorio-*.md`. Documentos de referência que não são
relatórios de etapa permanecem separados, como:

- [`architecture.md`](architecture.md);
- [`development.md`](development.md);
- [`roadmap.md`](roadmap.md);
- avaliação e configuração do provider Open Finance;
- guia de testes do Sandbox;
- release notes e changelog.

Manter o histórico Git permite consultar o conteúdo anterior mesmo após a
consolidação. Novas etapas devem atualizar este relatório ou acrescentar uma
seção claramente datada, sem recriar uma coleção de relatórios redundantes.

## 15. Próxima direção do projeto

O roadmap continua sendo a fonte oficial. Depois das entregas P5.1–P5.3, a
próxima unidade prevista é o refinamento do motor determinístico de recorrências
e gastos fora do padrão. Esta consolidação é apenas documental e não inicia
essa etapa.

