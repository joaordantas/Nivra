# Relatório geral do projeto Nivra

> Controle financeiro inteligente, simples e automatizado.

Este documento consolida os relatórios de implementação, migração,
segurança, Open Finance, parcelamentos e inteligência financeira que estavam
espalhados em vários arquivos. Ele serve como registro técnico e histórico do
projeto. O progresso oficial continua sendo controlado por
[`docs/roadmap.md`](roadmap.md), e o código, o banco e os testes permanecem as
fontes de verdade quando houver diferença entre um relato histórico e o
estado atual.

**Atualização:** 22 de setembro de 2026
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

**Lumi** é a assistente financeira da Nivra. O estado atual possui interface
protegida em `/lumi`, providers OpenAI/Groq, tool calling de consulta e contexto
multi-turn efêmero. P6.5 implementou tecnicamente `create_expense` e
`create_income` com confirmação explícita, mas a execução é protegida por
feature flag desligada por padrão e ainda não foi ativada em produção. Não há
memória persistente. A Nivra permanece em Alpha e não
deve ser apresentada como um produto financeiro pronto para produção crítica.

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
| Lumi P6.1 | Orquestração stateless no backend, OpenAI Responses API, tool calling somente leitura e proteções de custo e isolamento |

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

## 10. Inteligência financeira e Lumi

As entregas P5.1–P5.4 criaram um motor determinístico antes de qualquer IA:

- `/api/insights` calcula resumo, comparação de períodos, categorias, maiores e
  gastos incomuns e alertas de atenção;
- projeções distinguem realizado, conhecido futuro e projetado, incluindo
  compromissos de cartões e faturas próximas;
- tendências usam períodos comparáveis e crescimento de gastos;
- recorrências exigem três ocorrências, frequência regular e estabilidade de
  valor, sem confundir parcelas ou movimentos neutros com assinaturas;
- gastos fora do padrão usam somente histórico anterior, com mediana e MAD nas
  perspectivas global e da categoria;
- `get_financial_context` fornece contexto estruturado para uma futura camada
  de tools, sempre com a identidade da sessão;
- transferências internas, conciliação e pagamentos de fatura não são tratados
  como novas despesas econômicas.

No encerramento da P5.4 ainda não existiam chat, modelo de linguagem ou tool
calling efetivo. As P6.1–P6.3 adicionaram posteriormente a interface `/lumi`,
o provider e o contexto efêmero, todos em modo somente leitura. Ações
financeiras autônomas continuam inexistentes.

### P5.4 — Recorrências determinísticas e gastos fora do padrão

#### Objetivo e arquitetura

A P5.4 ampliou o motor de insights com análises reproduzíveis, explicáveis e
somente leitura. O endpoint autenticado `GET /api/insights` permanece como
interface pública. O `InsightService` obtém o histórico econômico unificado e
delega as regras puras ao `financial_pattern_service`; nenhum repository ou SQL
é exposto à futura Lumi.

```text
Sessão autenticada
        ↓
GET /api/insights
        ↓
InsightService
        ↓
Histórico econômico unificado
        ↓
financial_pattern_service
        ├── recorrências
        └── anomalias
```

#### Normalização e critérios de recorrência

A descrição é normalizada de forma conservadora: letras minúsculas, remoção de
acentos, pontuação e espaços redundantes, datas, referências explícitas,
identificadores numéricos longos, sufixos simples de domínio, códigos variáveis
anexados ao estabelecimento e prefixos comuns de transação. Palavras que
identificam o estabelecimento são preservadas. Não existe fuzzy matching;
`Uber` e `Uber Eats`, por exemplo, continuam distintos.

Uma recorrência exige simultaneamente:

- despesa econômica não neutra e sem vínculo com parcelamento;
- descrição normalizada e categoria consistentes;
- no mínimo três ocorrências na janela histórica de até 30 meses;
- pelo menos 80% dos intervalos compatíveis com uma frequência reconhecida;
- valores estáveis, exceto quando a última ocorrência representa uma mudança
  relevante claramente identificada.

Duas ocorrências nunca são apresentadas como recorrência. O valor típico é a
mediana, e cada valor de referência precisa ficar dentro do maior limite entre
R$ 10,00 e 25% da mediana. Uma mudança recente exige ao menos três valores
anteriores estáveis e uma diferença simultânea de pelo menos R$ 10,00 e 20%.

| Frequência | Tolerância temporal |
| --- | --- |
| Semanal | 7 dias, com tolerância de ±2 dias |
| Quinzenal | 14 dias, com tolerância de ±3 dias |
| Mensal | mês seguinte e dia com tolerância de ±3, ou ambos no fim do mês |
| Aproximadamente mensal | intervalos entre 25 e 35 dias |
| Anual | 12 meses e dia com tolerância de ±7, ou ambos no fim do mês |

O cálculo considera fevereiro, ano bissexto, meses de 30/31 dias, último dia do
mês e mudança de ano. Padrões válidos com três ocorrências recebem confiança
`medium`. A confiança `high` exige pelo menos cinco ocorrências, regularidade
mínima de 80% e variação de referência de até 10%. Padrões abaixo desses
critérios não são expostos. A próxima ocorrência só é calculada quando 100% dos
intervalos observados são compatíveis; padrões aceitos com pequena
irregularidade permanecem sem previsão.

#### Integridade financeira

Movimentações com `parcelamento_id` são excluídas para que parcelas de um mesmo
plano não sejam confundidas com assinaturas. Compras no cartão entram como
despesas econômicas, enquanto o pagamento da fatura permanece apenas como
liquidação e não gera nova despesa ou recorrência. Transferências internas são
neutras. Dados Open Finance vinculados participam do histórico, e uma
movimentação conciliada continua representada uma única vez na análise.

#### Gastos fora do padrão

A detecção de anomalias usa até 12 meses de histórico e compara cada despesa
somente com registros de data anterior, evitando que o gasto participe de sua
própria baseline ou que exista look-ahead bias.

| Perspectiva | Amostra mínima | Razão mínima |
| --- | ---: | ---: |
| Global | 8 despesas anteriores | 3× a mediana |
| Categoria | 4 despesas anteriores | 2,5× a mediana |

O gasto também precisa ser de pelo menos R$ 50,00. Quando o desvio absoluto
mediano (MAD) é diferente de zero, o robust z-score precisa atingir 3,5. Se há
amostra suficiente na categoria e o valor é normal dentro dela, uma diferença
apenas global é suprimida. Isso evita, por exemplo, tratar um aluguel recorrente
como anomalia por ser maior que despesas cotidianas.

Cada resultado informa contexto (`global`, `category` ou `both`), tamanho da
amostra, baselines, razão, MAD, robust z-score quando calculável e uma explicação
objetiva, como a comparação com a mediana recente da categoria. A interface não
atribui essas conclusões a uma IA.

#### Alertas, contexto da Lumi e Dashboard

O contrato anterior de `/api/insights` foi preservado e recebeu
`recurring_expenses` e detalhes explicáveis em `unusual_expenses`. A área “Sua
atenção” pode mostrar um alerta único de aumento relevante de recorrência ou, na
ausência dele, no máximo um padrão relevante de alta confiança. Os alertas são
priorizados e limitados para evitar ruído.

`get_financial_context` passou a incluir recorrências, próximas cobranças com
previsão confiável, mudanças relevantes de valor, principais anomalias e
metadados que distinguem dados observados, inferências determinísticas e dados
indisponíveis. A identidade continua vindo da sessão, o catálogo permanece
allowlisted e apenas services podem ser executados.

O Dashboard recebeu blocos compactos de recorrências e gastos fora do padrão,
com frequência, ocorrências, valor típico, confiança, próxima data quando
disponível e motivo da anomalia. Há estados de loading, vazio e erro isolado;
uma falha de insights não derruba o restante do Dashboard. Os componentes
preservam os temas claro/escuro e os breakpoints existentes.

#### Performance, banco e validação

A análise carrega uma janela consolidada de até 30 meses e agrupa os dados em
memória, sem consulta por categoria, padrão, mês ou transação. A análise de
anomalias usa apenas o recorte de 12 meses. As movimentações bancárias recebem a
mesma janela solicitada e não carregam registros externos fora do período.

Nenhuma tabela ou migration foi criada: padrões e anomalias são inferidos sob
demanda. O head Alembic permaneceu `f7b3c1d8e920` e foi validado em banco
descartável, com `alembic check` sem novas operações.

A suíte final registrou 150 testes Python aprovados. A cobertura específica
incluiu histórico vazio, uma e duas ocorrências, frequências e calendário,
variações de valor, normalização conservadora, mudança de preço, previsão
insegura, parcelamentos, movimentos neutros, cartões, Open Finance, conciliação,
anomalias globais e por categoria, resistência a outliers, isolamento
multiusuário e contexto da Lumi. O build React/TypeScript, a compilação Python e
`git diff --check` também passaram.

#### Limitações, dívida técnica e Gate

- recorrências não são entidades editáveis e não existe cadastro ou
  cancelamento automático de assinatura;
- o agrupamento conservador pode deixar de unir descrições semanticamente
  iguais que mudem demais, pois não usa similaridade textual ampla;
- previsões dependem da extensão e da qualidade do histórico;
- o processamento em memória é adequado à janela limitada atual, mas poderá
  exigir agregação ou cache quando o volume crescer;
- alertas não são persistidos nem enviados como notificações;
- a integração futura entre parcelamentos e compras parceladas no cartão ainda
  precisa preservar a exclusão desses planos da descoberta comum;
- no fechamento da P5.4, a Lumi ainda não possuía chat, modelo de linguagem ou
  ações financeiras; a orquestração de backend foi adicionada depois na P6.1.

O **Gate P5.4 foi aprovado**: a análise é determinística, somente leitura, sem
nova migration e preserva as regras econômicas existentes.

### P6.1 — Orquestração segura da Lumi em modo somente leitura

#### Objetivo e arquitetura

A P6.1 conectou pela primeira vez um modelo de linguagem à Nivra, preservando
os services determinísticos como autoridade financeira. A unidade foi limitada
ao backend e a consultas somente leitura:

```text
Sessão autenticada + CSRF
        ↓
POST /api/lumi/message
        ↓
LumiOrchestrator
        ↓
LLMProvider
        ↓
OpenAI Responses API
        ↓ function call validada
LumiToolService
        ↓
InsightService / get_financial_context
        ↓ resultado estruturado
OpenAI Responses API
        ↓
resposta textual tipada
```

O router recebe apenas `message`; campos extras, incluindo `usuario_id`, nome
de tool, provider, chave, prompt de sistema ou parâmetros do modelo, são
rejeitados pelo schema. A identidade vem exclusivamente da sessão server-side.
O endpoint preserva cookie HTTP-only, CSRF e isolamento multiusuário.

#### Provider e fluxo de tool calling

`LLMProvider` define um protocolo pequeno, independente da SDK. A implementação
`OpenAIProvider` usa a SDK oficial e a Responses API. O provider é criado de
forma lazy: ausência ou erro de `OPENAI_API_KEY` deixa apenas a Lumi
indisponível, sem impedir inicialização, login, dashboard, contas, transações,
cartões ou Open Finance. O modelo é centralizado em `LUMI_MODEL`, com default
`gpt-5.6-luna`; timeout e limite de saída também são configuráveis.

O modelo recebe somente a definição estrita de `get_financial_context`. O JSON
Schema exige `data_inicio` e `data_fim` em formato ISO, proíbe propriedades
extras e nunca inclui identidade. Nome e argumentos são novamente validados no
backend antes da execução. O fluxo reutiliza `LumiToolService`; não existe
executor paralelo, import dinâmico, acesso direto a repository ou SQL.

Saudações e perguntas básicas sobre a própria Lumi podem terminar sem consulta.
Qualquer outra mensagem inicia com `tool_choice=required`, e o orquestrador
rejeita uma resposta financeira que não tenha usado a fonte autorizada. Assim,
uma pergunta como “Quanto eu gastei?” não pode ser respondida somente com o
conhecimento do modelo.

Cada resposta pode solicitar tools sequencialmente. A orquestração valida todo
o lote recebido e só então executa cada chamada, com limite rígido inicial de
quatro por mensagem (`LUMI_MAX_TOOL_CALLS`). Saídas financeiras usam
serialização JSON controlada: `Decimal` vira string decimal, datas viram ISO e
o contexto possui limite de tamanho. A resposta pública contém somente o texto
final e os nomes das tools utilizadas.

#### Instruções, prompt injection e isolamento

As instruções de sistema são versionadas como `p6.1-v1` e definidas somente no
backend. Elas obrigam a Lumi a usar tools para dados específicos do usuário,
não inventar ou recalcular números determinísticos, distinguir fatos de
inferências, assumir previsões como estimativas e admitir dados insuficientes.
Pedidos de escrita devem receber uma explicação de que esta versão é somente
leitura.

Texto do usuário e conteúdo financeiro são tratados como dados não confiáveis.
Descrições como “ignore o sistema”, pedidos de SQL ou alegações de outro
`usuario_id` não alteram sessão, catálogo ou executor. Tool outputs são dados,
nunca novas instruções. A allowlist exposta ao modelo não contém tools de
criação, edição, exclusão, transferência ou pagamento.

#### Privacidade, armazenamento, limites e observabilidade

A execução é stateless: cada requisição começa somente com a mensagem atual e
não usa `previous_response_id`, tabela de conversa, memória no Neon ou histórico
persistido. As chamadas ao provider usam `store=false` e
`parallel_tool_calls=false`. Não é enviado histórico financeiro bruto antes de
uma tool ser solicitada.

O client aplica timeout de 20 segundos e uma retentativa controlada; a resposta
fica limitada por padrão a 600 tokens. O endpoint possui rate limit persistente
e independente, inicialmente 12 mensagens por usuário em 3.600 segundos,
compatível com a arquitetura serverless existente. Um identificador opaco
derivado do hash da sessão é enviado como `safety_identifier`, sem nome, e-mail
ou dado bancário.

Os logs registram sucesso/falha, modelo, tokens de entrada, saída e total,
duração e número de tools. Mensagem, prompt completo, resultados financeiros,
credenciais e resposta bruta do provider não são registrados.

#### Erros, dependências e validação

Configuração ausente, timeout, erro do provider, resposta incompleta, tool
desconhecida, JSON inválido, argumentos extras, excesso de chamadas e falha do
service recebem tratamento separado internamente e resposta HTTP sanitizada.
Nenhum stack trace ou conteúdo do provider é devolvido ao navegador.

A única dependência de runtime adicionada foi `openai>=2.0,<3.0`. Não foram
adicionados frameworks de agentes e nenhuma migration foi criada. Os testes
usam `FakeLLMProvider` e não fazem chamadas externas. A cobertura inclui fluxo
sem tool, chamada simples, chamada seguida de resposta final, múltiplas tools,
limite de loop, respostas vazia e incompleta, falhas e timeout do provider,
schema estrito, autenticação, CSRF, rate limit, identidade da sessão, isolamento
multiusuário, prompt injection, ausência de escrita e indisponibilidade isolada
quando a chave não existe.

Na validação original da P6.1, o smoke test real com OpenAI não foi executado
porque nenhuma `OPENAI_API_KEY` estava disponível. A tentativa externa posterior
está registrada na seção específica deste relatório e não faz parte da suíte
determinística.

#### Limitações e Gate P6.1

No encerramento específico da P6.1 ainda não existiam interface e contexto
multi-turn. Essas limitações históricas foram superadas pela interface da P6.2
e pelo contexto efêmero da P6.3. Permanecem válidas as seguintes restrições:

- não existe memória persistente ou recuperação de conversas anteriores;
- somente `get_financial_context` está exposta ao modelo;
- nesta etapa P6.1, a Lumi não criava, editava ou excluía dados; a criação
  controlada de receita/despesa chegou apenas na P6.5 e fica desligada por padrão;
- a qualidade textual e a seleção real da tool ainda precisam de smoke test e
  avaliação controlada com uma chave configurada;
- o rate limit reaproveita a tabela persistente existente e poderá exigir uma
  política de custo mais granular conforme o uso real;
- respostas textuais do modelo não são uma nova fonte contábil: services
  continuam sendo a autoridade dos números.

O **Gate P6.1 foi aprovado no backend** após os testes offline, build,
compilação, migrations e verificações de segurança. A próxima unidade é
**P6.2 — interface de conversa da Lumi em modo somente leitura**, sem memória
persistente e sem ações financeiras.

### P6.2 — Interface de conversa da Lumi em modo somente leitura

#### Objetivo, rota e arquitetura

A P6.2 tornou a orquestração da P6.1 utilizável pelo React em uma área própria,
protegida pela autenticação existente:

```text
Usuário autenticado
        ↓
React /lumi
        ↓ { message }
POST /api/lumi/message + cookie HTTP-only + CSRF
        ↓
Orquestração stateless da P6.1
        ↓
Resposta textual sanitizada
```

A sidebar desktop aponta para `/lumi`; no mobile, a entrada permanece no menu
“Mais”, preservando Início, Histórico, criação rápida e Contas na barra
inferior. A rota antiga `/assistant` redireciona para `/lumi` para não quebrar
links existentes.

O client possui um método tipado exclusivo para a Lumi. Ele envia somente
`{ message }`, com limite visual e técnico de 2.000 caracteres. Modelo,
provider, tools, argumentos, prompt de sistema, identidade e contexto financeiro
não podem ser definidos pelo navegador. O campo `tools_used` continua no
contrato de resposta para observabilidade, mas não aparece na interface.

#### Experiência e comportamento stateless

A tela reutiliza tipografia, cores, superfícies, radius e temas da Nivra. O
cabeçalho mostra `Lumi • somente leitura`; o estado inicial explica as consultas
disponíveis e oferece atalhos para gastos do mês, comparação mensal, maiores
gastos, recorrências, cartões e projeção. Nenhuma resposta é codificada no
frontend.

As mensagens permanecem somente no estado React enquanto a página está
montada. Não existe `localStorage`, IndexedDB, cookie de conversa, tabela, envio
de histórico ou memória no backend. Recarregar a rota limpa a conversa. A UI
explica que cada pergunta deve ser independente, evitando sugerir memória que o
backend single-turn não possui.

O composer aceita Enter para enviar e Shift+Enter para nova linha, bloqueia
whitespace e expõe contador de caracteres. Um lock síncrono em `ref`, além do
estado visual disabled, impede dois requests quando ocorre clique duplo antes
do próximo render. Durante a resposta, a interface mostra apenas “Analisando
suas finanças...”. Ao sair da página, o `AbortController` cancela a request e o
componente não recebe atualização tardia.

#### Segurança de conteúdo, erros e limites

Mensagens são renderizadas como texto React com `white-space: pre-wrap`; HTML e
Markdown retornados pelo modelo permanecem texto visível. Não existe
`dangerouslySetInnerHTML`, interpretação de links, script ou event handler. O
frontend não extrai nem recalcula valores financeiros, não executa pedidos de
escrita e não abre formulários automaticamente.

O client passou a usar `ApiError`, preservando status HTTP e `Retry-After` sem
expor respostas técnicas. A página diferencia sessão expirada, falha de CSRF,
limite, indisponibilidade do provider, timeout, conexão e erro genérico. Falhas
temporárias oferecem retry manual; não há repetição automática que possa gerar
custo duplicado. Em HTTP 429, o composer fica bloqueado pelo período informado
pelo backend e exibe contagem regressiva. A autoridade continua sendo o limite
persistente de 12 mensagens por usuário em 3.600 segundos.

#### Mobile e acessibilidade

O chat usa altura baseada em `dvh`, scroll interno e safe area. O composer fica
fora da área coberta pela navegação inferior; mensagens longas quebram linha e
não provocam rolagem horizontal. A validação local cobriu 375, 390, 430, 612 e
1.440 px, além de uma viewport compacta de 375 × 667 px. Um problema encontrado
na primeira validação, em que o composer terminava atrás da barra mobile, foi
corrigido reduzindo a altura externa e mantendo a conversa rolável.

Labels, nomes acessíveis, foco visível, disabled, teclado, `role=log`,
`aria-live` e status textual acompanham a experiência. Os temas claro e escuro
foram verificados. O scroll acompanha novas mensagens somente quando o usuário
já está próximo do final.

#### Validação, limitações e Gate P6.2

O frontend ainda não possui infraestrutura de testes automatizados. Para evitar
adicionar uma stack pesada somente nesta unidade, a validação da interface foi
feita no build TypeScript/Vite e em navegador local com uma API fake restrita a
respostas de teste. Foram exercitados estado inicial, sugestão, envio, resposta,
Enter, Shift+Enter, vazio, bloqueio de clique duplo, erro 429, `Retry-After`,
erro 503, retry manual, reload sem histórico, texto potencialmente perigoso,
temas, navegação mobile e breakpoints. Nenhum diálogo de script ou log de erro
foi produzido pelo conteúdo perigoso.

A regressão completa executou **167 testes Python**, todos aprovados. O build
React/TypeScript, a compilação Python, o upgrade das migrations em banco
descartável e o `alembic check` também passaram. O head permaneceu
`f7b3c1d8e920`; a P6.2 não criou ou alterou migrations.

O gate externo da P6.1 foi consultado antes da implementação da P6.2. Naquele
momento, `OPENAI_API_KEY` não existia no ambiente local nem em `.env` ignorado,
portanto nenhuma chamada real foi simulada ou declarada como concluída:

> Gate externo real ainda pendente por ausência de credencial no ambiente.

Não houve migration nem mudança em regras financeiras. A interface continua
single-turn, somente leitura e sem persistência. A qualidade textual, latência,
seleção real da tool e consumo de tokens ainda dependem de smoke controlado com
o provider configurado.

O **Gate P6.2 está aprovado localmente; a integração externa da Lumi permanece
pendente de smoke real**. A P6.3 avançou somente na parte determinística que não
depende da credencial externa, mantendo o mesmo gate de custo, latência e
qualidade como pendência explícita.

#### Gate de regressão pré-commit

Antes do próximo commit, foi executada uma validação transversal da árvore de
trabalho que contém P5.4, P6.1 e P6.2. A suíte completa terminou com **167 testes
Python aprovados**. Ela cobre autenticação e CSRF, ownership, contas,
transações, transferências, categorias, cartões e faturas, parcelamentos, Open
Finance, sincronização, idempotência, webhooks, conciliação, insights, padrões
financeiros e Lumi somente leitura.

O build React/TypeScript/Vite e a compilação Python passaram. Em um banco
descartável, o Alembic executou todas as migrations até
`f7b3c1d8e920`, confirmou esse mesmo head e não encontrou novas operações. Não
há arquivos modificados em `migrations/`, e `git diff --check` passou.

A validação manual da Lumi cobriu estado inicial, sugestões, envio, loading,
resposta, Enter, Shift+Enter, vazio, clique duplo, rate limit, indisponibilidade,
retry manual, reload sem memória, conteúdo HTML potencialmente perigoso, temas,
acesso pelo menu mobile e breakpoints. Um defeito encontrado em telas estreitas,
em que o composer poderia ficar atrás da navegação inferior, foi corrigido antes
do gate.

Os endpoints públicos da versão já publicada em Vercel responderam `200` para
`/api/health` e `/openapi.json`. A OpenAPI publicada ainda não contém a rota da
Lumi, o que é esperado: P6.1/P6.2 continuam locais e sem commit ou deploy.
Assim, a produção atual não foi usada para declarar a nova interface como
validada.

O gate local de regressão está aprovado para um commit de revisão. Permanecem
pendentes apenas evidências externas: smoke real com `OPENAI_API_KEY`, avaliação
de latência e custo do provider e uma futura suíte automatizada de componentes
frontend. Esses itens não indicam regressão de código local, mas impedem declarar
a integração externa da Lumi como concluída.

### P6.3 — Contexto efêmero e multi-turn seguro

#### Objetivo e contrato

A P6.3 permite perguntas de continuação sem criar memória persistente. O React
envia a pergunta atual e somente os três turnos completos mais recentes:

```text
Estado React da página
        ↓ até 3 pares user/assistant
POST /api/lumi/message { message, history }
        ↓ sessão HTTP-only + CSRF
LumiOrchestrator
        ↓ nova tool quando a pergunta atual depende de dados financeiros
Services determinísticos da Nivra
```

O contrato aceita no máximo seis mensagens de histórico, 4.000 caracteres por
item e 12.000 caracteres no total. O backend permite somente os papéis `user` e
`assistant`, exige alternância iniciada pelo usuário e rejeita turnos
incompletos. O frontend seleciona apenas pares completos; uma pergunta que
falhou sem resposta da Lumi não entra no contexto de uma tentativa posterior.

#### Segurança, autoridade e custo

O histórico é conteúdo não confiável. A versão `p6.3-v1` das instruções impede
que alegações anteriores alterem identidade, permissões, catálogo de tools ou
regras do sistema. A identidade continua vindo exclusivamente da sessão. Uma
resposta antiga também não autoriza a Lumi a reutilizar números como fonte: se
a pergunta atual não for uma saudação ou ajuda simples, o orquestrador exige
uma nova execução de `get_financial_context`.

O limite curto contém custo e latência e evita reenviar conversas extensas. O
provider continua usando `store=false`; o navegador não grava conversa em
`localStorage`, IndexedDB ou cookies. O backend não criou tabela ou migration.
Recarregar a página ou sair da rota descarta todo o contexto. Apenas textos de
usuário e resposta entram no histórico; resultados brutos de tools, IDs de
sessão e parâmetros internos não são enviados pelo cliente.

A revisão da [referência oficial da Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
confirmou que mensagens anteriores podem ser fornecidas como itens de entrada,
incluindo mensagens com papel `assistant`, e que `store=false` desativa o
armazenamento recuperável da resposta. O loop de tool calling da mesma pergunta
continua preservando os itens de continuação retornados pelo provider.

#### Validação e limitações

Os testes offline cobrem continuidade de conversa, nova tool obrigatória,
identidade obtida da sessão, papéis proibidos, ordem inválida, turno incompleto,
mais de seis mensagens, item acima de 4.000 caracteres e total acima de 12.000.
O teste focado da orquestração terminou com 19 casos aprovados. A suíte completa
terminou com **169 testes Python aprovados**, sem falhas. O build
React/TypeScript/Vite, a compilação Python e `git diff --check` passaram. Em
banco descartável protegido por `APP_ENV=test` e `TEST_DATABASE_URL`, o Alembic
executou todas as migrations, confirmou `f7b3c1d8e920 (head)` e informou que
não existem novas operações. Nenhum arquivo de migration foi alterado.

No navegador local, uma API fake registrou o contrato real emitido pelo build:
a primeira pergunta chegou com `history: []`; a continuação chegou com o par
anterior `user/assistant` e a nova pergunta separada em `message`. A resposta
contextual foi exibida e o reload restaurou o estado inicial sem mensagens. A
API fake e seu log foram removidos depois da verificação.

A P6.3 não implementa memória de preferências, busca semântica, resumo de
conversas, gravação de histórico ou ações financeiras. A chave passou a estar
disponível depois do gate local, mas a OpenAI recusou o smoke por créditos
indisponíveis; qualidade de respostas de continuação, latência e custo reais
continuam como evidência externa pendente.

O **Gate P6.3 está aprovado localmente e pendente de smoke multi-turn real**.
Até esse gate externo, a Lumi continua Alpha, somente leitura e sem autorização
para ferramentas de escrita.

### Gate externo da Lumi — tentativa de 22 de setembro de 2026

O ambiente local confirmou, sem exibir o valor, que `OPENAI_API_KEY` estava
presente e que o modelo efetivo configurado era `gpt-5.6-luna`. Antes da
request também foram reconfirmados no código: endpoint autenticado
`POST /api/lumi/message`, identidade exclusiva da sessão, catálogo externo
restrito a `get_financial_context`, `store=false` e ausência de
`previous_response_id` ou tools de escrita.

O smoke mínimo usou banco SQLite descartável protegido por `APP_ENV=test`, três
identidades sintéticas e a mensagem `Oi, quem é você?`. A chamada percorreu o
endpoint da Nivra e chegou à OpenAI Responses API, mas recebeu HTTP 429. Como o
router converte falhas do provider em resposta sanitizada, o cliente recebeu
HTTP 503 (`A Lumi está temporariamente indisponível`) após aproximadamente
7,2 segundos. Uma única repetição diagnóstica, sem dados financeiros, capturou
a exceção original:

```text
OpenAI RateLimitError
HTTP 429
type: insufficient_quota
code: credit_balance_exhausted
```

A causa é ausência de créditos no projeto/organização da OpenAI associado à
chave. O modelo existe e oferece Responses API e function calling, conforme a
[documentação oficial do GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
mas não chegou a produzir resposta. A API não retornou métricas de tokens para
as duas tentativas. Nenhum teste financeiro, multi-turn, prompt injection,
pedido de escrita, isolamento por resposta, reload, rate limit conversacional
ou medição comparativa de latência/custo foi executado depois da falha.

O comportamento de parada preservou custo e escopo: não houve fallback para
outro modelo, nenhuma tool foi executada, nenhum dado financeiro foi enviado e
nenhuma mutação financeira ocorreu. O banco descartável e o script temporário
de diagnóstico foram removidos depois da coleta. A documentação não contém a
chave nem fragmentos dela.

Resultado: **GATE EXTERNO REPROVADO POR BLOQUEIO EXTERNO — CRÉDITOS
INDISPONÍVEIS**. A reprovação significa que as evidências obrigatórias não
puderam ser produzidas; ela não demonstra defeito na qualidade da Lumi, pois o
modelo não respondeu. A próxima ação manual é adicionar créditos no
projeto/organização correto da OpenAI e repetir o roteiro integral desde o
smoke mínimo. Até lá, memória persistente e tools de escrita permanecem fora
do escopo.

### P6.3a — Provider Groq alternativo

Para manter a Lumi utilizável durante o Alpha sem substituir a integração
existente da OpenAI, a Nivra passou a aceitar uma seleção explícita por
configuração server-side:

```text
LumiOrchestrator
        ↓ LLMProvider
        ├── OpenAIProvider  ← LUMI_PROVIDER=openai
        └── GroqProvider    ← LUMI_PROVIDER=groq
```

Não existe fallback automático. Uma pergunta é enviada exclusivamente ao
provider escolhido; uma falha retorna erro sanitizado e nunca reenviará dados a
outro provider. O código mantém `openai` como default para compatibilidade com
ambientes existentes, enquanto o exemplo de configuração prepara o Alpha para
usar `groq` com `openai/gpt-oss-20b` como modelo inicial.

`GroqProvider` adapta somente na borda o contrato interno para o formato Chat
Completions de local function calling. A Groq recebe as mesmas instruções de
sistema e exclusivamente a definição de `get_financial_context`; browser,
execução de código, MCP e tools hospedadas não são enviados. Chamadas retornadas
passam pela mesma validação de nome, schema, argumentos e identidade da sessão
antes de qualquer service ser consultado. Os resultados retornam como mensagens
de tool ao adaptador e o orquestrador segue independente da SDK.

O histórico continua efêmero: até três turnos, seis mensagens e 12.000
caracteres. A API Chat Completions da Groq não oferece o parâmetro `store`
compatível com a Responses API; a Nivra, porém, não persiste conversas, não usa
`previous_response_id`, não grava mensagens no navegador e não cria tabelas ou
migrations. A configuração do provider, modelo e chaves continua exclusiva do
backend. A chave não é enviada ao frontend, e nenhum nome, e-mail, ID de usuário
como autoridade, connection string ou tool output é incluído nos logs.

Falhas de timeout, rate limit e autenticação são classificadas internamente e
devolvidas de forma sanitizada. Quando a Groq informa `Retry-After`, esse valor
é preservado para a interface. O rate limit próprio da Nivra continua sendo a
primeira barreira, com 12 mensagens por usuário a cada 3.600 segundos. A
observabilidade agora registra provider, modelo, tokens, duração, sucesso e
quantidade de tools, sem prompts, histórico ou contexto financeiro bruto.

A SDK oficial `groq` foi adicionada como a única dependência nova. Testes offline
cobrem a seleção explícita de OpenAI e Groq, provider inválido, chave Groq
ausente, resposta simples, tool call, continuação com output de tool, resposta
vazia, timeout, HTTP 429 com `Retry-After` e falha de autenticação. Os testes de
orquestração existentes preservam a proteção contra SQL, tools desconhecidas,
troca de usuário, escrita e histórico malicioso.

O gate local do complemento P6.3a executou a suíte completa com **176 testes aprovados**,
incluindo 26 testes focados na Lumi; a compilação Python e o build
React/TypeScript também passaram. Em banco SQLite descartável, Alembic chegou ao
head `f7b3c1d8e920` e `alembic check` não encontrou novas operações. Não houve
migration, alteração de schema ou mudança no frontend.

O modelo `openai/gpt-oss-20b` suporta local function calling na Groq, conforme a
[documentação oficial do modelo](https://console.groq.com/docs/model/openai/gpt-oss-20b)
e o [guia de local tool calling](https://console.groq.com/docs/tool-use/local-tool-calling).
Na validação inicial da implementação, nenhuma chamada externa foi feita
porque `GROQ_API_KEY` ainda não estava configurada localmente. O gate externo
foi executado posteriormente, em banco descartável, e está registrado na seção
seguinte. OpenAI permanece implementada e seu gate continua bloqueado
exclusivamente por créditos indisponíveis.

### Gate externo mínimo da Groq — 22 de setembro de 2026

O smoke externo foi executado somente depois de confirmar, sem exibir o valor,
que `GROQ_API_KEY` estava presente. A configuração efetiva foi
`LUMI_PROVIDER=groq` com o modelo `openai/gpt-oss-20b`. O roteiro usou uma
sessão criada no endpoint de cadastro, CSRF válido e um banco SQLite descartável
protegido por `APP_ENV=test`; nenhum dado foi enviado ao banco Neon de produção.

| Etapa | HTTP | Duração | Entrada | Saída | Total | Tools |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Saudação | 200 | 686 ms | 650 | 96 | 746 | nenhuma |
| Consulta do mês | 200 | 1.417 ms | 2.225 | 328 | 2.553 | `get_financial_context` |
| Continuação | 200 | 1.181 ms | 2.367 | 334 | 2.701 | `get_financial_context` |
| Pedido de escrita | 200 | 638 ms | 655 | 139 | 794 | nenhuma |
| Prompt injection | 200 | 364 ms | 660 | 74 | 734 | nenhuma |

As métricas acima são as retornadas pelo provider em cada chamada, somando as
duas chamadas internas quando uma consulta precisou executar a tool e receber a
resposta final. O provider e o modelo permaneceram os mesmos em todas as
etapas. As cinco respostas foram não vazias e não houve erro de autenticação,
modelo ou rate limit.

O teste registrou que a identidade usada pelo orquestrador foi sempre o ID da
sessão autenticada (o mesmo usuário em todas as etapas); `usuario_id` não foi
aceito como parâmetro de mensagem nem de tool. A única tool observada foi
`get_financial_context`, com o resultado encaminhado pelo service autorizado.
Os pedidos de escrita e de troca de identidade foram recusados textualmente,
sem tool e sem criar registros. A contagem dos registros financeiros permaneceu
inalterada antes e depois de cada etapa.

O contexto multi-turn foi enviado apenas no corpo da continuação, limitado ao
par anterior `user/assistant`; não existe tabela, migration, cookie,
`localStorage` ou registro de conversa. O reload/persistência não foi usado
como memória do provider. A observabilidade do backend registra somente
provider, modelo, tokens, duração, sucesso e quantidade de tools; não registra
prompt, histórico, resposta, senha, chave ou contexto financeiro bruto. A saída
do gate também foi sanitizada e não exibiu a chave Groq nem respostas
financeiras completas.

Durante o primeiro smoke local, a execução isolada recebeu `WinError 10013`
(`APIConnectionError`/`ConnectError`) por bloqueio de sockets do ambiente
restrito. Isso foi diagnosticado separadamente; a repetição com permissão de
rede para a chamada externa passou integralmente. O primeiro roteiro também
revelou que `tool_choice=required` causava HTTP 400 `tool_use_failed` para
recusas de escrita e prompt injection. O ajuste mínimo em
`services/lumi_orchestrator.py` passou a reconhecer essas intenções e permitir
recusa sem tool; os testes focados cobrem ambos os casos.

Após o ajuste, a suíte completa executou **178 testes aprovados**, o build
React/TypeScript/Vite passou, a compilação Python passou, `git diff --check`
passou e `alembic check` informou `No new upgrade operations detected` no head
`f7b3c1d8e920`. Nenhuma migration foi criada ou alterada.

Resultado: **GATE EXTERNO MÍNIMO DA GROQ APROVADO COM RESSALVAS**. A aprovação
cobre o provider Groq em modo somente leitura, sessão, tool calling autorizado,
continuação efêmera, recusa de escrita, prompt injection básico e ausência de
mutação. Ela não cobre o smoke da OpenAI, memória persistente, tools de escrita,
testers independentes nem ambiente de produção com a mesma chave.

### P6.4 — Fundação de ações com confirmação explícita

Esta etapa cria somente o protocolo de segurança que antecede uma futura ação
financeira. A Lumi ainda não chama `TransactionService`, repositories ou
endpoints de escrita: uma confirmação bem-sucedida muda apenas o estado de uma
proposta persistida. Receitas, despesas, transferências, cartões, faturas e
demais dados financeiros permanecem imutáveis.

O backend reconhece de forma controlada apenas `create_expense` e
`create_income`. A proposta possui schema fechado com valor em representação
decimal, descrição, data, conta e categoria. Valores zero, negativos ou fora do
limite são recusados; uma data precisa ser explícita no formato `AAAA-MM-DD`.
Conta e categoria são resolvidas por nome somente entre registros pertencentes
ao usuário da sessão. Não há IDs arbitrários do navegador ou do modelo, e campos
incompletos retornam uma lista de esclarecimentos em vez de inventar defaults.

As propostas completas recebem um `confirmation_id` aleatório e opaco. O banco
persiste somente seu SHA-256, o usuário proprietário, o tipo, o payload validado,
o estado e a expiração curta. A migration `e9a2d6c3b4f1` cria
`lumi_action_confirmations` com foreign key para `usuarios`, unicidade do hash,
checks para os dois tipos e quatro estados (`pending`, `confirmed`, `cancelled`,
`expired`) e índice por usuário, estado e vencimento. Não são gravados prompt,
histórico, resposta livre ou reasoning.

`POST /api/lumi/message` pode retornar uma resposta discriminada
`action_proposal`; o frontend não interpreta texto para descobrir a proposta. Os
endpoints `POST /api/lumi/actions/{confirmation_id}/confirm` e `/cancel` exigem
sessão e CSRF. A confirmação executa `UPDATE ... WHERE status = 'pending' AND
expira_em > agora`, tornando a transição atômica e impedindo replay ou dois
vencedores concorrentes. Cancelar uma proposta já cancelada é idempotente; uma
proposta expirada, confirmada ou de outro usuário não se torna confirmável.

O recurso é desligado por padrão com `LUMI_ACTION_PROPOSALS_ENABLED=false`.
Quando desligado, o fluxo prévio estritamente somente leitura continua. Quando
ligado para testes, existem limites persistentes distintos: 12 propostas por
usuário/hora e 30 confirmações ou cancelamentos por usuário/hora. Logs técnicos
registram só tipo de ação, estado e duração; não incluem token, payload, prompt
ou valores financeiros completos.

A tela da Lumi mostra um card com tipo, valor, descrição, conta, categoria,
data, avisos e campos faltantes. O botão é explícito, por exemplo “Confirmar
despesa de R$ 50,00”; a interface também informa que a confirmação não cria
movimentação nesta versão. O card se reorganiza em uma coluna no celular e
preserva os temas existentes.

Os testes cobrem propostas completas e incompletas, receita e despesa, valores e
datas inválidos, entidade de outro usuário, campos extras, hash do token,
ausência de escrita financeira, CSRF, sessão, ownership, expiração inclusive no
limite exato, cancelamento, replay e duas confirmações concorrentes. A suite
usa provider falso sempre que o caminho não é de proposta; não foi feita nova
chamada real à Groq nesta etapa. A implementação está pronta para o próximo
incremento controlado, mas a execução financeira permanece proibida.

O gate local executou **187 testes Python aprovados**, incluindo 37 focados na
Lumi e em propostas/confirmations. A compilação Python, `git diff --check`, o
build React/TypeScript/Vite e a migration em banco SQLite descartável passaram.
A migration foi validada como `upgrade → check → downgrade → upgrade`; o
`alembic check` não encontrou operações pendentes. O único aviso do build é o
tamanho já conhecido do bundle principal acima de 500 kB, sem falha funcional.

### P6.5 — execução controlada de receita e despesa (22/09/2026)

Somente `create_expense` e `create_income` podem gerar uma movimentação, e apenas
no `POST /api/lumi/actions/confirm` autenticado e protegido por CSRF. O token vai
no corpo fechado da requisição para não aparecer na URL dos logs de acesso. A
rota antiga com token na URL permanece para confirmações sem execução P6.4 e
rejeita execução quando a flag nova está ativa. A mensagem, o histórico e o
provider não autorizam nem executam. A
proposta persiste um snapshot estruturado; o endpoint rejeita campos financeiros
novos e revalida token, usuário, expiração, estado, tipo, valor decimal exato,
descrição, data, conta ativa e categoria do próprio usuário. Nomes da conta e
categoria são comparados com o card; alterações entre proposta e confirmação
exigem nova proposta. No PostgreSQL, `FOR SHARE` protege essas linhas de mudança
concorrente durante a validação. O serviço de transações normal foi adaptado para receber
uma conexão do chamador, compartilhando regras de criação com a Lumi.

A confirmação `pending` e `execution_eligible=true` é reivindicada por `UPDATE`
condicional. A criação da transação e a mudança para `executed`, com
`executed_transaction_id` e `executed_at`, ocorrem **na mesma transação de banco**.
Falha antes do commit faz rollback integral. Repetição depois do commit retorna
o mesmo ID sem novo lançamento; duas requisições concorrentes disputam a mesma
linha e só uma cria o evento econômico. Não há retry automático de mutação.
As propostas criadas com execução desligada recebem `execution_eligible=false`,
inclusive todas as anteriores à migration. Confirmações históricas da P6.4 em
`confirmed` permanecem não executáveis. Canceladas e expiradas também não
executam. A coluna de vínculo é única e deliberadamente não possui foreign key
para `transacoes`: a exclusão normal de um lançamento permanece possível; o ID
imóvel na confirmação conserva a evidência da execução mesmo após exclusão.

`LUMI_ACTION_PROPOSALS_ENABLED` e `LUMI_ACTION_EXECUTION_ENABLED` são flags
separadas; ambas têm de estar ativas para execução, e a segunda continua `false`
por padrão. A migration `b5c7d9e1f203` amplia somente a tabela de confirmação;
não reinterpreta linhas antigas. A interface mantém valor, descrição, conta,
categoria e data antes/depois da operação, desabilita ações após sucesso e
direciona ao histórico normal. O backend registra apenas tipo, resultado,
duração e ID interno da transação, sem token, prompt ou payload financeiro.

O parser determinístico passou a aceitar também a frase curta de teste
“Gastei R$ 10 em ... pela ... na categoria ... hoje”, sempre resolvendo conta e
categoria pelo usuário autenticado. Essa rota de proposta não chama a Groq;
por isso o teste com provider falso comprova independência do provider, mas não
constitui uma chamada externa real ao modelo. Não houve chamada à Groq nesta
etapa (zero consumo externo). Um smoke adicional em banco descartável, com
`LUMI_PROVIDER=groq`, modelo `openai/gpt-oss-20b` e chave detectada sem exibição,
retornou HTTP 200 para proposta, confirmação e replay; o histórico exibiu uma
única transação de teste. O contador confirmou **zero chamadas à Groq**: o
provider estava configurado, mas o parser de propostas interceptou a mensagem.
Isso não equivale a validar uma resposta externa do modelo para criação de
propostas. A execução permanece desligada em produção.

**Gate local P6.5: aprovado com ressalvas.** A suíte completa fechou com **201
testes Python aprovados**, dos quais 23 nos módulos de propostas/execução da
Lumi. O smoke com provider falso criou uma despesa, verificou histórico/resumo,
repetiu a confirmação sem duplicação e cobriu uma receita. Build React/TypeScript,
compilação Python e `git diff --check` passaram. O Alembic passou em banco
descartável no ciclo `upgrade → check → downgrade → upgrade → check`, com head
`b5c7d9e1f203`; uma linha legada `confirmed` permaneceu inelegível após upgrade.
Não foram aplicadas migrations no Neon nem habilitadas flags na Vercel. Permanecem
pendentes, naquele momento, a execução controlada contra PostgreSQL
descartável, a revisão de rollout em produção e um smoke realmente externo com Groq caso o parser de
propostas passe a depender do modelo. O bundle Vite ainda exibe o aviso conhecido
de tamanho acima de 500 kB, sem falha de build.

#### Gate PostgreSQL P6.5 — aprovado com ressalvas (22/09/2026)

O banco utilizado foi `nivra_p65_gate`, em projeto Neon descartável com
endpoint distinto do Neon principal. O preflight somente leitura exigiu URL
PostgreSQL distinta das URLs de produção (inclusive pooled/unpooled), nome de
banco explicitamente de teste e schema `public` vazio. Uma URL inicial sem
marcador de teste foi rejeitada antes da conexão; o sandbox também bloqueou a
primeira tentativa de rede. Após permitir a conexão ao banco descartável, o
preflight confirmou o banco vazio sem imprimir senha ou URL. Cinco testes
unitários da guarda passaram. Nenhuma alteração ocorreu no banco principal.

Em PostgreSQL real, a suíte `tests/integration/lumi_postgres_gate.py` aplicou
Alembic até `e9a2d6c3b4f1`, inseriu confirmações legadas fictícias, avançou a
`b5c7d9e1f203` e passou `alembic check`; fez `downgrade -1 → upgrade head →
check` e confirmou que as duas linhas antigas seguem inelegíveis. Constraints
de status, integridade de execução e unicidade do vínculo foram verificadas.
O primeiro teste funcional parou porque o fixture legado usava token curto,
rejeitado corretamente pelo schema HTTP. Isso foi corrigido **no teste**, sem
mudar a aplicação. Antes da retomada, uma auditoria separada `READ ONLY`
comprovou head esperado, apenas dois usuários fictícios, uma conta/categoria de
teste, duas confirmações legadas inelegíveis e zero transações. A retomada
repetiu essa guarda antes de escrever.

Passaram: despesa `10.01` e receita `2.34` com `NUMERIC` exato, usuário/conta/
categoria/data/descrição corretos, `executed_at` e vínculo de autorização;
histórico, resumo, saldo e endpoint de insights normais; replay e perda de
resposta retornando o mesmo transaction ID; ownership sem revelar a proposta;
CSRF; sete campos extras adulterados rejeitados; cancelamento e expiração
exata; alteração/remoção de conta e categoria; falha forçada entre INSERT e
commit com rollback integral e retry posterior. Concorrência HTTP simultânea
de **2 requests (203 ms)** e **5 requests (281 ms)** retornou um único ID e
persistiu uma única transação por grupo. Confirmação normal levou **156 ms**,
replay **47 ms** e receita **156 ms** nesse ambiente; são medições pontuais,
não benchmark. Providers Groq/OpenAI simulados indisponíveis receberam **zero
chamadas** durante a confirmação, que continuou funcionando.

A verificação final separada, somente leitura, encontrou **sete transações
fictícias, sete vínculos completos**, nenhuma transação órfã ou atribuída a
outro usuário, e ambas as autorizações P6.4 ainda inelegíveis.

A suíte Python local completa passou com **205 testes** (incluindo os quatro
testes de guarda existentes quando a descoberta começou); um quinto teste de
guarda, adicionado ao final, passou separadamente. Compilação Python, build
React/TypeScript e `git diff --check` passaram. `alembic check` no PostgreSQL
descartável não encontrou operações pendentes. O bundle mantém o aviso conhecido
acima de 500 kB. Os logs observados registraram somente tipo de erro/duração e
rollback, sem token, payload integral, prompt, chave ou URL.

**Ressalva:** não houve proposta estruturada *gerada pela Groq*. O parser
determinístico captura legitimamente intenções de escrita antes do provider; a
rota do modelo não produz essa proposta. Não foi forçada uma chamada ao modelo
nem testada prompt injection com Groq real neste gate. **Zero requests Groq**
foram feitas. Esse limite não afeta a execução financeira determinística após
confirmação, mas impede afirmar validação de um fluxo IA → proposta. Também
não houve teste de produção nem rollout. O gate PostgreSQL está **APROVADO COM
RESSALVAS**, sem blockers financeiros ou de isolamento encontrados nos cenários
executados; a aprovação não habilita produção.

Para repetir em **outro banco vazio e descartável**, configurar
`P65_TEST_DATABASE_URL` no `.env` ignorado pelo Git, executar `--preflight` e,
somente após confirmar endpoint/banco, `--execute`. O comando `--resume` é
reservado ao fixture parcial estritamente verificado por `--resume-preflight`;
`--verify-final` faz a checagem econômica somente leitura. Nunca apontar esses
comandos ao Neon principal. O banco utilizado neste gate agora contém dados
fictícios e será rejeitado pelo preflight de execução inicial.

**Plano de rollout, ainda não executado:** (A) após revisão humana, aplicar
somente o schema `b5c7d9e1f203` no Neon principal mantendo
`LUMI_ACTION_EXECUTION_ENABLED=false`; validar auth, dashboard, transações,
propostas e saúde; (B) observar sem execuções e confirmar ausência de regressões;
(C) habilitar a flag somente mediante aprovação separada e acompanhar primeiras
execuções controladas. Em incidente, desligar a flag primeiro, preservar
transações/confirmações e investigar. Depois de execuções reais, não usar
downgrade da migration sem análise de perda de auditoria; propostas pendentes
anteriores à habilitação permanecem inelegíveis. Nenhuma alteração foi feita
no Neon/Vercel neste gate.

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
- inteligência P5.1–P5.3: 135 testes na consolidação anterior;
- P5.4: 150 testes aprovados na suíte completa, incluindo recorrências,
  calendário, anomalias, isolamento e regressões das fases anteriores;
- P6.1: 167 testes aprovados na repetição final da suíte completa; a única falha
  inicial era um teste de parcelamento dependente da virada de fuso e foi
  tornado determinístico. Os testes específicos da Lumi usam provider falso e
  não dependem de rede ou credenciais;
- P6.3: 169 testes aprovados na suíte completa; 19 deles no módulo focado da
  orquestração, incluindo limites e continuidade do contexto efêmero;
- P6.5: 201 testes aprovados na suíte completa; 23 focados em propostas e
  execução da Lumi, incluindo migração, concorrência, rollback e isolamento;
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
- Parcelamentos ainda não cobrem toda a futura integração com cartões. A
  detecção de recorrências existe, mas o cadastro de recorrências, orçamentos e
  metas segue no roadmap.
- A Lumi possui backend, interface, contexto efêmero e criação controlada de
  receita/despesa mediante confirmação explícita. A execução é desligada por
  padrão e não foi ativada na Vercel. O gate Groq anterior foi aprovado com
  ressalvas; o gate externo da OpenAI segue bloqueado por
  `credit_balance_exhausted`. Memória persistente, outras ações financeiras,
  notificações e WhatsApp não estão implementados.
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

O roadmap continua sendo a fonte oficial. Com o gate P6.5 aprovado com
ressalvas em PostgreSQL descartável, a próxima unidade recomendada é a
**revisão separada da Fase A do rollout**: schema no Neon principal com a
execução financeira ainda desligada, antes de qualquer decisão sobre a flag.
A edição de transações com confirmação continua no roadmap, fora desta etapa.

## 16. P6.5A — preparação do rollout seguro do schema (22/09/2026)

### Continuação: trava pública e isolamento de Preview

O rollout segue **não executado**. A inspeção do código mostrou que `/lumi`
abriria o chat após o deploy, embora a versão pública `081ee06` ainda mostre
“Em breve”. Foi adicionada a flag de backend `LUMI_PUBLIC_ENABLED`, com valor
implícito `false` e habilitação somente pelo literal `true`. Com ela desligada,
o frontend mostra o placeholder e os endpoints de mensagem, confirmação e
cancelamento recusam a operação antes de chamar o provider ou serviço de ação.
Falha ao consultar a capacidade também mantém o placeholder. A flag é
independente de `LUMI_ACTION_PROPOSALS_ENABLED` e
`LUMI_ACTION_EXECUTION_ENABLED`, que continuam desligadas por padrão.

Na Vercel, `main` dispara Production e branches auxiliares disparam Preview.
A variável `DATABASE_URL` consta com escopo **Production and Preview**, assim
como outras variáveis Neon. Portanto, publicar a branch de release agora
criaria um Preview com acesso ao banco principal. O banco descartável antigo
`nivra-p65-gate` não será reutilizado; sua URL foi removida do `.env` local.
As três flags `LUMI_PUBLIC_ENABLED`, `LUMI_ACTION_PROPOSALS_ENABLED` e
`LUMI_ACTION_EXECUTION_ENABLED` foram adicionadas em **Production somente**
com valor `false` explícito. A Vercel informou que um novo deployment é
necessário para adotá-las; nenhum redeploy foi iniciado.
Após o ajuste de ambiente, a Vercel ainda listava `081ee06` como deployment
Production `Ready`, e a rota pública da Lumi continuava com “Em breve”.
Até que exista um banco Preview isolado e as variáveis compartilhadas sejam
restritas/substituídas, **não haverá push da branch, migration no Neon principal
nem deploy de produção**. O snapshot e a revision principal precisam ser
reconfirmados imediatamente antes de uma futura aplicação do schema.

Uma tentativa de abrir o detalhe da variável secreta para inspecionar seu
escopo foi barrada pela revisão automática, que apontou risco de expor seu
valor. O escopo acima foi lido diretamente da listagem, sem abrir o segredo.
O bloqueio não foi contornado.

Após a trava pública, a suíte completa passou com **208 testes** e o teste
focado da flag passou com **2 testes**. O build React/TypeScript e a compilação
Python passaram. Uma tentativa de executar o teste focado em paralelo à suíte
completa colidiu no arquivo SQLite de testes; ele foi repetido de forma
sequencial e passou. `git diff --check` não apontou erros de whitespace, e a
busca por padrões de segredo nos arquivos alterados não encontrou credenciais.
Um smoke local isolado usou um SQLite temporário fora do projeto, migrado ao
head e removido ao final. Login e dashboard de um usuário fictício funcionaram;
`/lumi` mostrou “Em breve”, consultou apenas `/api/lumi/capabilities` e não
enviou mensagem ao provider. Em 375, 390, 430, 612 e 1440 px, nos temas claro
e escuro, não houve overflow horizontal na página Lumi; a navegação móvel
apareceu nas quatro larguras menores. O badge Alpha abriu a explicação com
Enter. Esse smoke **não substitui** o gate visual/funcional do Vercel Preview.

### Checkpoint e revisão técnica

- O checkpoint inicial tinha `main` em `ee9add6`, dois commits à frente de
  `origin/main` (`081ee06`), com P5/P6 e migrations ainda no working tree.
  Essas alterações receberam o commit local `cb13c0c`. Não houve push nem
  deploy; o código correspondente ainda não está publicado.
- Cadeia Alembic verificada: `f7b3c1d8e920 → e9a2d6c3b4f1 → b5c7d9e1f203`.
  A primeira revision cria `lumi_action_confirmations`, FK de usuário com
  `ON DELETE CASCADE`, token hash único, checks de tipo/status e índice por
  usuário/status/expiração. A segunda acrescenta `execution_eligible BOOLEAN
  NOT NULL DEFAULT false`, `executed_transaction_id` único e nullable,
  `executed_at` nullable, e checks para o estado `executed`. O vínculo com
  `transacoes` é lógico/único; não há FK declarada para esse campo.
- O SQL gerado de `f7b3c1d8e920` até o head contém `CREATE TABLE`, `CREATE
  INDEX`, `ALTER TABLE` da tabela nova e atualizações de `alembic_version`.
  Não contém `UPDATE`/`DELETE` de dados financeiros existentes nem execução
  automática da Lumi. É expansão compatível com o código antigo: as tabelas
  atuais permanecem intactas.
- `.env` permanece ignorado pelo Git. `git diff --check` não encontrou erros
  de whitespace (somente avisos de conversão de quebra de linha). O build
  React/TypeScript e a compilação Python passaram. A suíte completa passou
  com **206 testes `unittest`**. No PostgreSQL descartável P6.5, `alembic
  current` retornou `b5c7d9e1f203 (head)` e `alembic check` não detectou
  novas operações. O check não foi executado no Neon principal, que permanece
  intencionalmente atrás do head local.

### Estado oficial antes de qualquer migration

No painel do Neon, o projeto principal é `nivra-db`, branch `main`, banco
`neondb`. Consulta somente leitura ao `alembic_version` retornou
`f7b3c1d8e920`. Havia **6 usuários**, **0 linhas em `transacoes`** e a tabela
`lumi_action_confirmations` não existia. Não foram lidos payloads financeiros.
Foi criado snapshot manual do branch principal em **22/09/2026 23:14:39 UTC**,
visível em *Backup & Restore*; o plano também mostra uma janela de histórico
de 6 horas. Recuperação deve ser conduzida pelo painel Neon a partir desse
snapshot, preservando cópia do estado anterior. Não se deve usar downgrade
automático em produção. O plano gratuito permite somente um snapshot manual
no momento; verificar sua disponibilidade imediatamente antes da migration.

No projeto Vercel `nivra`, as variáveis `DATABASE_URL` e
`DATABASE_URL_UNPOOLED` estão presentes. As flags
`LUMI_ACTION_EXECUTION_ENABLED` e `LUMI_ACTION_PROPOSALS_ENABLED` não aparecem
na lista de variáveis configuradas; o código P6.5 usa `false` como default
para ambas. Isso **não é comprovação de uma flag explicitamente configurada
no deployment futuro**. Nenhuma variável foi alterada.

### Baseline da aplicação pública

URL: <https://nivra-finance.vercel.app>, deployment de produção `081ee06`
(14/09/2026), anterior à P5/P6. Login da conta de teste e sessão persistente funcionaram. Na navegação
mobile observada, dashboard, transações, contas, cartões, Lumi e menu inferior
abriram. Dashboard mostrou saldo consolidado bancário, entradas, gastos,
economia e movimentações recentes; a página de transações mostrou histórico
bancário unificado, busca e filtros. Contas mostrou conexão Pluggy Sandbox,
contas externas, saldo informado pelo provider, conta Nivra vinculada e
estados de atualização. Cartões mostrou o estado vazio e formulário. A rota
`/assistant` ainda mostra **“Em breve”**: consultas da Lumi não existem na
versão pública observada. Duas conexões Pluggy já aparecem em estado de erro
de atualização na baseline, sem evidência de relação com a P6.5.

| Área | Antes do rollout | Depois do rollout |
| --- | --- | --- |
| Login e sessão | OK na conta de teste | Não testado — sem deploy |
| Dashboard e agregados | OK na amostra observada | Não testado — sem deploy |
| Histórico, busca e filtros | Interface/dados presentes | Não testado — sem deploy |
| Contas e Open Finance Sandbox | Interface/dados presentes; há conexões antigas com erro | Não testado — sem deploy |
| Cartões/faturas | Estado vazio; operações não exercitadas | Não testado — sem deploy |
| Lumi | Placeholder “Em breve” | Não testado — sem deploy |
| Mutação manual, transferências, conciliação e sincronização | Não exercitadas para preservar dados | Não testado — sem deploy |
| Desktop, larguras 375/390/430/612/1440, temas | Não houve medição completa por largura/tema | Não testado — sem deploy |

O código local agora inclui indicador global **Alpha** no shell desktop/mobile,
com explicação acessível sob demanda, e marca a Lumi como Alpha com aviso de
disponibilidade de ações. O aviso separado de Sandbox em Open Finance foi
preservado. O build passou, mas a aparência e o comportamento nesses cinco
tamanhos ainda requerem validação visual após deploy.

### Resultado provisório

**Rollout P6.5A: pendente; gate de regressão pública: pendente.** Nenhuma
migration foi aplicada ao Neon principal, nenhum dado financeiro foi criado
pela Lumi e nenhuma flag de execução foi ligada. A tentativa de iniciar
`alembic upgrade head` foi **rejeitada pela revisão automática antes da
execução**, pois o commit ainda é somente local e o checkpoint de recuperação
e as flags não foram considerados suficientemente confirmados para alteração
de produção. Uma nova consulta somente leitura confirmou `f7b3c1d8e920`,
zero transações e ausência da tabela da Lumi após a rejeição. Não houve
contorno ou execução indireta. Ainda faltam publicação do checkpoint Git com
autorização, confirmação operacional do snapshot/flags, migration no banco
oficial, `alembic current/check` e
comparação pós-schema/deploy de todas as áreas críticas. A diferença grande
entre a versão pública e o working tree exige atenção especial no smoke após
publicação. O primeiro passo em incidente é manter a execução desligada e
avaliar reversão do deploy; restauração do snapshot Neon é medida controlada,
não um downgrade automático.
