import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from services.categoria_service import criar_categoria_service
from services.conta_service import criar_conta_service
from services.lumi_action_confirmation_service import (
    LumiActionConfirmationNotFoundError,
    LumiActionConfirmationStateError,
    criar_confirmacao_pendente,
    executar_acao_confirmada,
)
from services.lumi_action_proposal_service import criar_proposta_de_edicao
from services.transacao_service import criar_transacao_service
from database.connection import get_connection
from tests.db_support import remove_test_database, reset_test_database


class LumiTransactionUpdateTests(unittest.TestCase):
    def setUp(self):
        self.old = {key: os.environ.get(key) for key in ("LUMI_ACTION_PROPOSALS_ENABLED", "LUMI_ACTION_EXECUTION_ENABLED")}
        os.environ["LUMI_ACTION_PROPOSALS_ENABLED"] = "true"
        os.environ["LUMI_ACTION_EXECUTION_ENABLED"] = "true"
        reset_test_database()
        conn = get_connection()
        try:
            conn.execute("INSERT INTO usuarios (id, usuario, email, senha) VALUES (1, 'Ana', 'update@example.com', 'hash')")
            conn.execute("INSERT INTO usuarios (id, usuario, email, senha) VALUES (2, 'Beto', 'other-update@example.com', 'hash')")
            conn.commit()
        finally:
            conn.close()
        criar_conta_service("Nubank", "digital", 0, 1)
        criar_conta_service("Inter", "digital", 0, 1)
        criar_categoria_service("Mercado", 1)
        criar_categoria_service("Alimentação", 1)
        self.transaction = criar_transacao_service(80, "saida", 1, "Mercado", "2026-09-13", 1, 1)

    def tearDown(self):
        for key, value in self.old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        remove_test_database()

    def _payload(self, **changes):
        return criar_proposta_de_edicao(1, self.transaction["id"], changes).confirmation.confirmation_id

    def _count_and_row(self):
        conn = get_connection()
        try:
            return conn.execute("SELECT count(*), valor, comentario, data FROM transacoes WHERE id = ?", (self.transaction["id"],)).fetchone()
        finally:
            conn.close()

    def test_description_value_date_and_replay(self):
        token = self._payload(description="Supermercado", amount="85.00", date="2026-09-14")
        first = executar_acao_confirmada(token, 1)
        replay = executar_acao_confirmada(token, 1)
        self.assertEqual(first.transaction_id, replay.transaction_id)
        self.assertEqual(self._count_and_row(), (1, 85.0, "Supermercado", "2026-09-14"))

    def test_snapshot_conflict_and_other_user_are_blocked(self):
        proposal = criar_proposta_de_edicao(1, self.transaction["id"], {"description": "Novo"})
        conn = get_connection()
        try:
            conn.execute("UPDATE transacoes SET comentario = 'Mudança externa' WHERE id = ?", (self.transaction["id"],))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(ValueError):
            executar_acao_confirmada(proposal.confirmation.confirmation_id, 1)
        other = criar_confirmacao_pendente(1, "update_transaction", proposal.confirmation.payload)
        with self.assertRaises(LumiActionConfirmationNotFoundError):
            executar_acao_confirmada(other.confirmation_id, 2)

    def test_category_account_and_execution_flag_are_revalidated(self):
        proposal = criar_proposta_de_edicao(
            1, self.transaction["id"],
            {"category": {"id": 2, "name": "Alimentação"}, "account": {"id": 2, "name": "Inter"}},
        )
        os.environ["LUMI_ACTION_EXECUTION_ENABLED"] = "false"
        with self.assertRaises(LumiActionConfirmationStateError):
            executar_acao_confirmada(proposal.confirmation.confirmation_id, 1)
        os.environ["LUMI_ACTION_EXECUTION_ENABLED"] = "true"
        self.assertEqual(executar_acao_confirmada(proposal.confirmation.confirmation_id, 1).status, "executed")
        conn = get_connection()
        try:
            self.assertEqual(conn.execute("SELECT categoria_id, conta_id FROM transacoes WHERE id = ?", (self.transaction["id"],)).fetchone(), (2, 2))
        finally:
            conn.close()

    def test_concurrent_confirmation_applies_once(self):
        token = self._payload(description="Única")
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda _: executar_acao_confirmada(token, 1).transaction_id, range(5)))
        self.assertEqual(results, [self.transaction["id"]] * 5)
        self.assertEqual(self._count_and_row()[0], 1)

    def test_protected_transaction_is_rejected(self):
        payload = {
            "transaction_id": self.transaction["id"],
            "before": {"id": self.transaction["id"], "origem": "manual", "parcelamento_id": 9, "conciliada_com_banco": False},
            "after": {"amount": "80.00", "description": "Não", "date": "2026-09-13", "account": {"id": 1}, "category": {"id": 1}},
            "changes": ["description"],
        }
        token = criar_confirmacao_pendente(1, "update_transaction", payload).confirmation_id
        with self.assertRaises(LumiActionConfirmationStateError):
            executar_acao_confirmada(token, 1)


if __name__ == "__main__":
    unittest.main()
