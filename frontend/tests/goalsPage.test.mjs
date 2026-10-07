import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page=readFileSync(new URL("../src/pages/GoalsPage.tsx",import.meta.url),"utf8");
const styles=readFileSync(new URL("../src/styles.css",import.meta.url),"utf8");

test("tela cobre loading vazio erro e sucesso",()=>{assert.match(page,/aria-busy=\{loading\}/);assert.match(page,/Nenhuma meta criada/);assert.match(page,/<Feedback>\{error\}/);assert.match(page,/tone="success"/);});
test("formulário cria e edita metas",()=>{assert.match(page,/api\.createGoal/);assert.match(page,/api\.updateGoal/);assert.match(page,/Valor-alvo/);assert.match(page,/Data-limite opcional/);});
test("aportes e retiradas usam idempotência",()=>{assert.match(page,/contribution/);assert.match(page,/withdrawal/);assert.match(page,/crypto\.randomUUID\(\)/);});
test("histórico e movimentos futuros permanecem visíveis",()=>{assert.match(page,/api\.getGoalMovements/);assert.match(page,/· futura/);assert.match(page,/Reserva lógica/);});
test("progresso mostra percentual real e limita apenas barra",()=>{assert.match(page,/progress_percentage/);assert.match(page,/clampProgress\(percentage\)/);assert.match(page,/role="progressbar"/);});
test("ações destrutivas confirmam e preservam histórico",()=>{assert.match(page,/window\.confirm/);assert.match(page,/Metas com histórico serão arquivadas/);});
test("layout responde nos breakpoints mobile e tablet",()=>{assert.match(styles,/\.goal-grid \{ display: grid; grid-template-columns: repeat\(3/);assert.match(styles,/@media \(max-width: 1100px\)[\s\S]*\.goal-grid \{ grid-template-columns: repeat\(2/);assert.match(styles,/@media \(max-width: 700px\)[\s\S]*\.goal-grid \{ grid-template-columns: minmax\(0, 1fr\)/);});
test("tokens de tema e textos longos são seguros",()=>{assert.match(styles,/background: var\(--neutral-soft\)/);assert.match(styles,/overflow-wrap: anywhere/);assert.match(styles,/color: var\(--text-secondary\)/);});
