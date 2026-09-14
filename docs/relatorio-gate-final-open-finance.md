# Gate Final — Open Finance MVP

Data da auditoria: 14 de setembro de 2026.

## Estado do código

- Branch auditada: `main`.
- SHA publicado e sincronizado no início da auditoria: `13ceb2fd7e6708f30d9f0d300320c605aee26eeb`.
- `HEAD` e `origin/main` apontavam para o mesmo commit e a árvore de trabalho estava limpa.
- As Etapas 2A, 2B, 2B.5, 2C, 2D, 2D.5, 2E, 2F, 2G e 2H estão presentes no código publicado.
- Nenhuma migration ou alteração funcional local estava esquecida.
- A auditoria não encontrou blocker que exigisse alteração de código, schema ou regra financeira.

## Banco e migrations

- Head Alembic do projeto: `d41e7b9a2c60` (`advanced reconciliation`).
- Neon principal, branch `main`, banco `neondb`: `d41e7b9a2c60`.
- `alembic heads`, `alembic current` e `alembic check` foram executados; o banco descartável chegou ao head e não existem operações de upgrade não versionadas.
- Todas as migrations foram aplicadas, em ordem, em um banco descartável durante o gate.
- Foram confirmadas no Neon as constraints de unicidade para categorias padrão, contas externas, vínculo com conta Nivra, transações externas, pares de conciliação e eventos de webhook.
- Foram confirmadas foreign keys nas tabelas de conexões, contas externas, transações bancárias, eventos de sincronização e inbox de webhook. Os índices parciais de conciliação impedem que uma transação bancária ou manual participe de mais de uma confirmação ativa.
- Nenhum downgrade ou reset foi executado.

## Segurança

- A busca no código versionado, documentação, histórico Git e bundle de produção não encontrou credencial real, URL PostgreSQL real, token ou secret Pluggy exposto.
- O frontend usa somente a URL pública da API. Sessão, credenciais Pluggy e conexão PostgreSQL permanecem no backend.
- `localStorage` é usado para preferência de tema e remoção da antiga chave de autenticação; não armazena usuário, sessão ou token. Não foi encontrado uso de `sessionStorage` para autenticação.
- Os logs públicos inspecionados na Vercel registram tipo, status e contagem de processamento, sem senha, cookie, API key, Client Secret, connection string ou payload financeiro completo.
- O Sandbox continua identificado como demonstração e avisa para nunca usar credenciais bancárias reais.

## Autenticação

- Sessão server-side, cookie HTTP-only, expiração, revogação, hash do token e CSRF permanecem ativos.
- `/api/auth/me` restaura a identidade pelo backend; `usuario_id` enviado pelo cliente não é autoridade.
- Em produção, login com a conta de teste, recarregamento da página e logout foram validados. A sessão permaneceu após F5 e foi encerrada pelo logout.
- Cadastro, verificação de e-mail, recuperação, alteração de senha, rate limiting e expiração foram validados pela suíte automatizada. Não foi criado outro usuário persistente em produção somente para repetir esses fluxos.
- Os testes de ownership/IDOR confirmam que um usuário não pode consultar ou alterar conexões, contas externas, transações bancárias, vínculos ou conciliações de outro usuário.

## Conexões

- O fluxo Pluggy Connect continua restrito ao Sandbox e o Item é validado no backend antes da persistência.
- A conexão persiste no PostgreSQL, sobrevive a F5 e a novo login e é restaurada pelo backend.
- A unicidade por provider e Item externo impede duplicação do mesmo vínculo lógico.
- A tela de produção exibiu conexão ativa, contas importadas, uma conta vinculada e estados de erro controlados para conexões antigas de teste.

## Sincronização

- Instituição, contas, saldos e transações são obtidos com paginação e persistidos de forma idempotente.
- Duas sincronizações equivalentes foram executadas em produção durante este gate. Ambas processaram 41 movimentações; o resultado permaneceu em 2 contas e 41 movimentações.
- Saldo e quantidade lógica não foram duplicados. A última sincronização foi atualizada e o frontend exibiu sucesso compreensível.
- Atualizações substituem os campos externos correspondentes. Transações removidas são arquivadas e decisões de conciliação economicamente afetadas são reabertas.
- Falhas do provider preservam o último snapshot válido e são exibidas sem JSON bruto ou identificadores técnicos.

## Idempotência

- Contas e transações externas possuem chaves únicas baseadas nos IDs do provider.
- Re-sync atualiza registros existentes e não cria novas contas ou movimentações equivalentes.
- A inbox de webhook possui `UNIQUE(provider, provider_event_id)` e a inserção usa `ON CONFLICT DO NOTHING`.
- O teste automatizado com o mesmo `eventId` confirmou uma única linha na inbox, nenhuma nova chamada ao provider e nenhum efeito econômico duplicado.
- A confirmação concorrente de conciliação é protegida por constraints e transação de banco.

## Categorias

- Cada usuário recebe seu próprio conjunto de categorias padrão com `chave_sistema` estável.
- Categorias personalizadas continuam privadas e editáveis; categorias padrão não podem ser excluídas.
- Renomear o texto de uma categoria padrão não altera sua chave nem quebra o mapeamento Open Finance.
- Categorias externas são resolvidas pela chave interna; valores desconhecidos usam `other` e não criam categorias arbitrárias.

## Integração com núcleo

- Uma conta externa pode criar uma conta Nivra ou ser vinculada a uma conta existente do mesmo usuário.
- Constraints impedem vínculos duplicados e associação da mesma conta Nivra a múltiplas contas externas.
- O saldo do provider é a fonte do saldo atual da conta vinculada e aparece uma única vez no consolidado.
- A associação, o saldo e o histórico permanecem após F5 e novo login.
- Cartões externos permanecem somente para consulta nesta versão.

## Histórico e dashboard

- O histórico combina lançamentos manuais, bancários e conciliados sem copiar cegamente registros externos para `transacoes`.
- Foram validados filtros por busca, período, categoria, conta e origem (`Manual`, `Banco` e `Manual + Banco`).
- Uma conciliação confirmada mantém os dois registros físicos e apresenta um único evento econômico.
- O dashboard considera saldos vinculados, receitas, despesas e conciliações. Transferências internas e pagamento de fatura permanecem neutros; compra no cartão continua sendo a despesa econômica.
- A suíte cobre os cenários somente manual, somente banco, combinação, conciliação, transferências e cartões/faturas, sem perda de lançamentos manuais ou dupla contabilização.

## Webhooks

- Foram confirmadas entregas reais Pluggy para a Vercel com HTTP 200.
- Há evidência real de `item/updated`, `transactions/created` e `transactions/updated` processados com sucesso.
- Eventos informativos não suportados, como `item/login_succeeded`, foram reconhecidos e ignorados com segurança.
- A inbox de produção possuía 15 eventos no momento da auditoria: 7 processados com sucesso e 8 ignorados de forma controlada.
- A consulta de duplicação por `provider, provider_event_id` retornou 0 linhas.
- Todos os eventos reais observados possuíam `tentativas = 1`. Não existe evidência externa de replay do mesmo `eventId`.
- Autenticação pelo secret, retry após falha, lease de processamento, concorrência, criação, atualização, remoção e evento repetido são cobertos pelos testes automatizados.

## Conciliação

- O motor avalia conta vinculada, direção, valor exato, janela de até dois dias e descrição normalizada.
- Foram cobertos match perfeito, datas próximas, valor, direção ou conta diferente, múltiplos candidatos, níveis de confiança, ambiguidade, confirmação, rejeição, lote seguro e ownership.
- Rejeições são preservadas no re-sync e o mesmo par não reaparece sem mudança relevante.
- Mudança de valor, data ou direção reabre a decisão; mudança irrelevante preserva a confirmação.
- Remoção bancária arquiva o registro externo e preserva o lançamento manual.
- Histórico e dashboard contabilizam uma conciliação confirmada uma única vez e preservam a categoria manual quando aplicável.

## UX

- Foram observados em produção os estados sem conexão, conectado, carregando, atualizando, sucesso, erro, conta vinculada, conta não vinculada e cartão externo somente leitura.
- A área de demonstração apresenta passos curtos, credenciais Sandbox fictícias e aviso para não usar dados reais.
- Erros são apresentados em linguagem compreensível, com nova tentativa quando aplicável, sem stack trace, JSON ou IDs técnicos.
- O vínculo abre um modal com escolha entre conta existente e criação de conta Nivra.

## Mobile/Desktop

- Login, Dashboard, Contas/Open Finance e Transações/conciliação foram inspecionados em 375, 390, 430, 612 e 1440 px.
- Não foi observado overflow relevante ou ação coberta pela navegação inferior.
- O modal de vínculo permaneceu utilizável e fechou por botão e tecla `Esc`.
- Temas claro e escuro foram conferidos nos estados principais, badges e mensagens.
- Labels, nomes acessíveis, foco, texto de status e indicação além de cor estão presentes nos fluxos auditados. Esta verificação foi mínima e não substitui uma auditoria ampla de acessibilidade.

## Testes automatizados

- Resultado total: **102 testes aprovados, 0 falhas, 0 ignorados**.
- Auth e hardening de conta: 19.
- Ownership/IDOR/BOLA abrangente: 1.
- Provider e persistência Open Finance: 15.
- Sincronização, vínculo e histórico: 12.
- Webhooks: 10.
- Conciliação avançada: 8.
- Categorias: 5.
- Dashboard: 3.
- Contas e transações: 7.
- Cartões e faturas: 13.
- Configuração de banco e migração SQLite: 9.
- A compilação Python passou.
- Único aviso não bloqueante: compatibilidade futura do `TestClient` da Starlette com httpx 2.

## Produção

- `GET /api/health`: HTTP 200, banco online.
- `GET /api/auth/csrf`: HTTP 200.
- `GET /openapi.json`: HTTP 200.
- O OpenAPI contém as rotas de Connect Token, conexões, sincronização, webhook e conciliação.
- Login, restauração por F5, logout, Dashboard, Contas, Open Finance, histórico unificado e sincronização foram exercitados em `https://nivra-finance.vercel.app`.
- Os logs Vercel observados não apresentaram erro ativo no intervalo inspecionado e registraram webhooks reais com HTTP 200.

## Evidências externas

Comprovado externamente:

- aplicação e API publicadas na Vercel;
- PostgreSQL principal no Neon no migration head;
- fluxo Sandbox, persistência, saldo, histórico e re-sync em produção;
- entregas reais de webhook com HTTP 200 e persistência na inbox;
- UX responsiva em navegador real nos tamanhos auditados.

Pendente por fator externo:

- replay real, feito pela Pluggy, do mesmo `eventId`;
- execução integral do roteiro por testers independentes em dispositivos e navegadores próprios.

Essas evidências não foram simuladas nem apresentadas como concluídas.

## Blockers

Nenhum blocker técnico foi encontrado.

## Pendências não bloqueantes

- Registrar uma entrega real repetida do mesmo `eventId`; o comportamento já está protegido por teste e constraint.
- Executar o checklist de aceitação com testers independentes.
- Fazer auditoria ampla de acessibilidade na etapa de preparação para produção.
- O snapshot de contas externas permanece autoritativo: uma conta que deixa de vir em uma sincronização completa é removida do cache externo, enquanto lançamentos removidos individualmente são arquivados. Esse comportamento deve ser reavaliado antes de habilitar bancos reais.
- Atualizar futuramente a compatibilidade de testes indicada pelo aviso Starlette/httpx, sem impacto atual.

## Resultado do Gate Técnico

**APROVADO.**

O código, banco, migrations, segurança, isolamento, sincronização, idempotência, integração financeira, dashboard, webhooks, conciliação, testes e build atendem ao Open Finance Sandbox MVP. Nenhum bug classificado como blocker foi encontrado.

## Resultado do Gate Externo

**PENDENTE.**

A aplicação possui evidência real de produção, mas ainda faltam o retry externo do mesmo evento e a aceitação por testers independentes.

## Conclusão

A Prioridade 2 está **tecnicamente concluída** no ambiente Sandbox. As duas validações externas complementares permanecem registradas e não impedem o encerramento do gate técnico. A Nivra continua em Alpha e não está autorizada, por este gate, a conectar bancos reais.

A próxima prioridade definida no roadmap é a **Prioridade 3 — Parcelamentos e Recorrências**. Ela não foi iniciada neste trabalho.
