# Rollout controlado e rollback da Lumi

Este procedimento prepara a Lumi para liberação gradual. Ele não autoriza
ativação em Production nem substitui a decisão humana do gate.

## Controles server-side

O acesso efetivo exige duas condições no backend:

1. `LUMI_PUBLIC_ENABLED=true`;
2. `LUMI_ROLLOUT_MODE` autoriza o usuário da sessão autenticada.

Modos aceitos:

| Modo | Comportamento |
| --- | --- |
| `off` | ninguém acessa a Lumi |
| `internal` | somente IDs em `LUMI_ROLLOUT_USER_IDS` |
| `allowlist` | somente IDs em `LUMI_ROLLOUT_USER_IDS` |
| `all` | todos os usuários autenticados; reservado para decisão futura |

Modo ausente ou inválido equivale a `off`. Uma allowlist vazia ou com item
inválido não autoriza ninguém. O ID usado na decisão vem da sessão validada;
campos enviados pelo frontend não participam da autorização.

As flags financeiras continuam independentes:

- `LUMI_ACTION_PROPOSALS_ENABLED` controla a criação de propostas;
- `LUMI_ACTION_EXECUTION_ENABLED` controla a execução após confirmação;
- ambas precisam estar explicitamente `true` para executar uma ação.

## Sequência recomendada

1. manter `LUMI_PUBLIC_ENABLED=false` e `LUMI_ROLLOUT_MODE=off` por padrão;
2. validar migrations e concorrência em PostgreSQL descartável;
3. no Preview, usar `internal` com apenas a conta fictícia do smoke;
4. manter a execução financeira desligada até o smoke de leitura passar;
5. habilitar propostas e execução somente no Preview e somente para a conta
   fictícia, com confirmação explícita;
6. revisar logs estruturados e evidências;
7. submeter a decisão de qualquer ampliação a uma pessoa responsável.

## Rollback imediato

Em incidente, alterar apenas uma destas configurações no ambiente afetado:

- preferencial: `LUMI_PUBLIC_ENABLED=false`;
- alternativa: `LUMI_ROLLOUT_MODE=off`;
- para bloquear somente mutações: `LUMI_ACTION_EXECUTION_ENABLED=false`.

Depois da atualização de configuração/deployment correspondente, verificar:

- capability da conta anteriormente autorizada retorna indisponível;
- frontend mostra o estado “Em breve”;
- endpoints de conversa, memória, mensagem e ação recusam acesso;
- nenhuma confirmação pendente é executada;
- logs registram `access_denied` sem conteúdo financeiro.

O rollback operacional não depende de downgrade de migration. Em especial,
as migrations de execução e memória possuem downgrades destrutivos para seus
próprios dados e não devem ser usadas como kill switch após uso real.

## Observabilidade mínima

Os logs `nivra.lumi` registram eventos estruturados para requisição, provider,
tool, proposta, confirmação, execução, cancelamento e recusa de acesso. Os
eventos incluem resultado, duração e códigos de erro sanitizados. Eles não
incluem prompt, resposta, IDs de usuário, tokens, cookies, connection strings
ou valores financeiros.

## Evidência operacional P6.9B

Em 30 de setembro de 2026, o rollout foi exercitado somente no Preview do
branch `codex/p6-9b-preview` com duas contas fictícias. A conta autorizada
passou por consulta com provider e tool financeira, proposta sem execução,
cancelamento, criação de despesa, edição e replay idempotente. A conta fora da
allowlist recebeu capability negativa e recusa 503 na mensagem. Um identificador
de confirmação inexistente retornou 404 sanitizado.

Os logs confirmaram provider Groq com resposta 200, uma tool call por consulta,
execução de despesa e edição bem-sucedidas, replay apontando para a mesma
transação, cancelamento bem-sucedido e rollback de proposta expirada. A
interface foi inspecionada em desktop claro/escuro e nos viewports 375, 390 e
430 px, sem overflow horizontal.

Estado deixado após o smoke:

- Preview: `LUMI_PUBLIC_ENABLED=false`;
- Preview: `LUMI_ROLLOUT_MODE=off`;
- Preview: `LUMI_ACTION_PROPOSALS_ENABLED=false`;
- Preview: `LUMI_ACTION_EXECUTION_ENABLED=false`;
- Production: permaneceu desligada e não foi alterada.

## Gate Final Geral da P6

Em 30 de setembro de 2026, a implementação P6.1–P6.9 passou pela auditoria
final de arquitetura, segurança, integridade financeira, persistência, UX,
PostgreSQL e operação. Foram aprovados 238 testes na suíte completa e 82 testes
dirigidos, além de build/typecheck, compilação Python e `alembic check` no head
`d7e8f9a012b3`.

O encerramento é técnico e não autoriza rollout público. Production permanece
com `LUMI_PUBLIC_ENABLED=false`, `LUMI_ACTION_PROPOSALS_ENABLED=false` e
`LUMI_ACTION_EXECUTION_ENABLED=false`. Qualquer mudança desse estado exige uma
decisão humana posterior e deve seguir a sequência e o rollback deste documento.
