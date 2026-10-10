# Backup, recuperação e continuidade da Nivra

## Escopo e princípios

Este runbook cobre PostgreSQL no Neon, deployments Vercel e evidências
operacionais. Preview e Production são ambientes independentes: banco,
connection strings, flags, segredos e deployments nunca devem ser reutilizados
entre eles. Nenhuma restauração deve começar sem identificar projeto, branch,
endpoint, migration atual e fingerprint sanitizado do destino.

## Objetivos operacionais

- dados financeiros e de autenticação: alvo de RPO de até 24 horas e RTO de até
  4 horas enquanto o produto estiver em Alpha;
- código e configuração versionada: RPO próximo de zero pelo Git e RTO de até
  1 hora por rollback do deployment;
- logs sanitizados: retenção de 30 dias; não são fonte de restauração financeira;
- revisar os alvos antes do piloto público e após qualquer mudança de plano do
  provedor, volume ou requisito jurídico.

Os valores são objetivos de operação, não garantia contratual do Neon ou da
Vercel.

## Antes de migration ou piloto

1. confirmar o ambiente por nome, project/branch ID e fingerprint, sem exibir
   connection string;
2. registrar SHA, deployment e `alembic current`;
3. confirmar backup contínuo/restore point disponível no painel Neon ou criar
   branch de segurança quando o plano e o procedimento permitirem;
4. registrar contagens e checksums sanitizados das entidades críticas;
5. revisar a migration como expand-only e executar `alembic check`;
6. manter produtores, Cron, Lumi pública e manutenção desligados até o gate.

## Ordem de recuperação

1. conter: desligar flags e gatilhos, sem apagar evidência;
2. aplicação: promover novamente o último deployment saudável quando o schema
   continuar compatível;
3. banco: usar restore point ou branch do Neon somente após confirmar o instante
   e o projeto; restaurar primeiro em branch isolada;
4. validar: migration, health, login, isolamento, contagens, saldos e logs;
5. promover a recuperação apenas após comparação e aprovação humana;
6. registrar incidente, janela perdida, causa, ações e testes pós-restauração.

Downgrade destrutivo de migration e edição direta de dados financeiros não são
procedimentos automáticos de rollback.

## Exercício periódico

Executar trimestralmente, ou antes de cada piloto relevante, um exercício em
Preview: criar uma branch restaurada isolada, validar schema e amostra
sanitizada, medir RPO/RTO, e remover a branch de exercício somente após guardar
a evidência. Nunca usar Production como destino do ensaio. O gate da Prioridade
9 validou a existência do mecanismo e o isolamento; uma restauração completa de
Production não foi realizada.

## Evidência mínima

- ambiente, projeto, branch e endpoint sanitizados;
- SHA, deployment e migration;
- instante escolhido, início/fim e resultado do restore;
- contagens agregadas antes/depois;
- smoke de health, autenticação e leitura financeira;
- responsável pela aprovação e decisão de promover ou abortar.
