import unittest
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.main import app
from database.connection import get_connection
from repositories.parcelamento_repo import criar_parcelamento_atomico
from services.categoria_service import criar_categoria_service
from services.conta_service import criar_conta_service, listar_contas_formatadas
from services.parcelamento_service import (
    atualizar_parcelamento_service,
    calcular_data_parcela,
    criar_parcelamento_service,
    dividir_valor_em_parcelas,
    excluir_parcelamento_service,
    listar_parcelamentos_service,
    obter_parcelamento_service,
)
from services.transacao_service import (
    atualizar_transacao_service,
    criar_transacao_service,
    deletar_transacao_service,
    listar_transacoes_formatadas,
    obter_resumo_financeiro,
)
from tests.auth_support import authenticate_existing_user
from tests.db_support import remove_test_database, reset_test_database


class InstallmentFoundationTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        conn = get_connection()
        conn.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) "
            "VALUES (1, 'Usuario A', 'a@example.com', 'hash')"
        )
        conn.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) "
            "VALUES (2, 'Usuario B', 'b@example.com', 'hash')"
        )
        conn.commit()
        conn.close()
        self.conta_a = criar_conta_service("Conta A", "digital", 1000, 1)
        self.conta_b = criar_conta_service("Conta B", "digital", 500, 2)
        self.categoria_a = criar_categoria_service("Compras A", 1)
        self.categoria_b = criar_categoria_service("Compras B", 2)

    def tearDown(self):
        remove_test_database()

    def criar_plano(
        self,
        quantidade: int = 3,
        valor: str = "100.00",
        inicio: date = date(2026, 1, 31),
    ) -> dict:
        return criar_parcelamento_service(
            1,
            "Notebook",
            Decimal(valor),
            quantidade,
            inicio,
            "saida",
            self.categoria_a["id"],
            self.conta_a["id"],
        )

    def test_cria_parcelamento_em_duas_parcelas(self):
        plano = self.criar_plano(2, "1200.00", date(2026, 9, 10))

        self.assertEqual(plano["quantidade_parcelas"], 2)
        self.assertEqual(plano["parcelas_persistidas"], 2)
        self.assertEqual([item["numero_parcela"] for item in plano["parcelas"]], [1, 2])
        self.assertEqual([item["data"].isoformat() if isinstance(item["data"], date) else item["data"] for item in plano["parcelas"]], ["2026-09-10", "2026-10-10"])

    def test_cria_parcelamento_em_tres_parcelas_com_soma_exata(self):
        plano = self.criar_plano(3, "100.00")

        valores = [Decimal(str(item["valor"])) for item in plano["parcelas"]]
        self.assertEqual(valores, [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")])
        self.assertEqual(sum(valores), Decimal("100.00"))
        self.assertEqual(Decimal(str(plano["valor_persistido"])), Decimal("100.00"))

    def test_cria_parcelamento_em_doze_parcelas(self):
        plano = self.criar_plano(12, "1200.00", date(2026, 9, 10))

        self.assertEqual(len(plano["parcelas"]), 12)
        self.assertEqual(plano["parcelas"][-1]["numero_parcela"], 12)
        self.assertEqual(str(plano["parcelas"][-1]["data"]), "2027-08-10")

    def test_divisao_monetaria_com_centavos_e_valor_pequeno(self):
        self.assertEqual(
            dividir_valor_em_parcelas("10.01", 3),
            [Decimal("3.34"), Decimal("3.34"), Decimal("3.33")],
        )
        self.assertEqual(
            dividir_valor_em_parcelas("0.05", 3),
            [Decimal("0.02"), Decimal("0.02"), Decimal("0.01")],
        )
        with self.assertRaisesRegex(ValueError, "um centavo por parcela"):
            dividir_valor_em_parcelas("0.01", 2)

    def test_datas_usam_dia_original_e_ultimo_dia_valido(self):
        inicio = date(2026, 1, 31)
        self.assertEqual(calcular_data_parcela(inicio, 1), date(2026, 2, 28))
        self.assertEqual(calcular_data_parcela(inicio, 2), date(2026, 3, 31))
        self.assertEqual(calcular_data_parcela(date(2028, 1, 31), 1), date(2028, 2, 29))
        self.assertEqual(calcular_data_parcela(date(2026, 8, 31), 1), date(2026, 9, 30))
        self.assertEqual(calcular_data_parcela(date(2026, 12, 31), 1), date(2027, 1, 31))

    def test_lista_e_detalhe_respeitam_isolamento(self):
        plano = self.criar_plano()

        self.assertEqual([item["id"] for item in listar_parcelamentos_service(1)], [plano["id"]])
        self.assertEqual(listar_parcelamentos_service(2), [])
        with self.assertRaisesRegex(ValueError, "nao encontrado"):
            obter_parcelamento_service(plano["id"], 2)

    def test_exclusao_do_grupo_remove_parcelas_sem_orfaos(self):
        plano = self.criar_plano()

        self.assertFalse(excluir_parcelamento_service(plano["id"], 2))
        self.assertTrue(excluir_parcelamento_service(plano["id"], 1))
        conn = get_connection()
        try:
            plano_count = conn.execute(
                "SELECT COUNT(*) FROM parcelamentos WHERE id = ?", (plano["id"],)
            ).fetchone()[0]
            parcelas_count = conn.execute(
                "SELECT COUNT(*) FROM transacoes WHERE parcelamento_id = ?",
                (plano["id"],),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(plano_count, 0)
        self.assertEqual(parcelas_count, 0)

    def test_rollback_remove_plano_e_primeira_parcela_apos_falha(self):
        with self.assertRaises(IntegrityError):
            criar_parcelamento_atomico(
                1,
                "Duplicado",
                Decimal("20.00"),
                2,
                date(2026, 9, 10),
                "saida",
                self.categoria_a["id"],
                self.conta_a["id"],
                [
                    (1, Decimal("10.00"), date(2026, 9, 10)),
                    (1, Decimal("10.00"), date(2026, 10, 10)),
                ],
            )
        conn = get_connection()
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM parcelamentos").fetchone()[0], 0)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM transacoes WHERE parcelamento_id IS NOT NULL").fetchone()[0],
                0,
            )
        finally:
            conn.close()

    def test_parcela_nao_pode_ser_editada_ou_excluida_isoladamente(self):
        plano = self.criar_plano()
        parcela = plano["parcelas"][0]

        with self.assertRaisesRegex(ValueError, "parcelamento completo"):
            atualizar_transacao_service(
                parcela["id"],
                99,
                "saida",
                self.categoria_a["id"],
                "Alterada",
                "2026-01-31",
                1,
                self.conta_a["id"],
            )
        with self.assertRaisesRegex(ValueError, "parcelamento completo"):
            deletar_transacao_service(parcela["id"], 1)

    def test_transacao_normal_mantem_campos_de_parcelamento_nulos(self):
        transacao = criar_transacao_service(
            25,
            "saida",
            self.categoria_a["id"],
            "Compra avulsa",
            "2026-09-10",
            1,
            self.conta_a["id"],
        )

        self.assertIsNone(transacao["parcelamento_id"])
        self.assertIsNone(transacao["numero_parcela"])
        self.assertIsNone(transacao["quantidade_parcelas"])
        self.assertTrue(transacao["editavel"])

    def test_api_cria_lista_consulta_e_exclui_com_csrf_e_ownership(self):
        client_a = TestClient(app)
        client_b = TestClient(app)
        try:
            headers_a = authenticate_existing_user(client_a, 1)
            headers_b = authenticate_existing_user(client_b, 2)
            response = client_a.post(
                "/api/installment-plans",
                headers=headers_a,
                json={
                    "descricao": "Curso",
                    "valor_total": 300,
                    "quantidade_parcelas": 3,
                    "data_inicial": "2026-09-15",
                    "tipo": "saida",
                    "categoria_id": self.categoria_a["id"],
                    "conta_id": self.conta_a["id"],
                },
            )
            self.assertEqual(response.status_code, 201, response.text)
            plano = response.json()
            self.assertEqual(len(plano["parcelas"]), 3)
            self.assertEqual(client_a.get("/api/installment-plans").status_code, 200)
            self.assertEqual(
                client_b.get(f"/api/installment-plans/{plano['id']}").status_code,
                404,
            )
            self.assertEqual(
                client_b.patch(
                    f"/api/installment-plans/{plano['id']}",
                    headers=headers_b,
                    json={
                        "descricao": "Tentativa",
                        "categoria_id": self.categoria_b["id"],
                        "conta_id": self.conta_b["id"],
                    },
                ).status_code,
                404,
            )
            update_response = client_a.patch(
                f"/api/installment-plans/{plano['id']}",
                headers=headers_a,
                json={
                    "descricao": "Curso atualizado",
                    "categoria_id": self.categoria_a["id"],
                    "conta_id": self.conta_a["id"],
                },
            )
            self.assertEqual(update_response.status_code, 200, update_response.text)
            self.assertTrue(
                all(
                    item["comentario"] == "Curso atualizado"
                    for item in update_response.json()["parcelas"]
                )
            )
            self.assertEqual(
                client_b.delete(
                    f"/api/installment-plans/{plano['id']}", headers=headers_b
                ).status_code,
                404,
            )
            self.assertEqual(
                client_a.delete(
                    f"/api/installment-plans/{plano['id']}", headers=headers_a
                ).status_code,
                204,
            )
        finally:
            client_a.close()
            client_b.close()

    def test_historico_identifica_numero_e_total_de_parcelas(self):
        plano = self.criar_plano(3, "90.00")

        itens = [
            item
            for item in listar_transacoes_formatadas(1)
            if item["parcelamento_id"] == plano["id"]
        ]
        self.assertEqual(len(itens), 3)
        self.assertEqual({item["numero_parcela"] for item in itens}, {1, 2, 3})
        self.assertTrue(all(item["quantidade_parcelas"] == 3 for item in itens))
        self.assertTrue(all(not item["editavel"] for item in itens))

    def test_progresso_temporal_nao_inventa_status_de_pagamento(self):
        plano = self.criar_plano(3, "90.00", date.today())

        self.assertEqual(plano["parcelas_com_data_atingida"], 1)
        self.assertEqual(plano["parcelas_futuras"], 2)
        self.assertIsNotNone(plano["proxima_parcela_data"])
        self.assertEqual(
            [item["status_temporal"] for item in plano["parcelas"]],
            ["data_atingida", "futura", "futura"],
        )

    def test_edicao_segura_propaga_campos_nao_estruturais(self):
        plano = self.criar_plano(3, "90.00", date.today())
        nova_conta = criar_conta_service("Conta nova", "corrente", 0, 1)
        nova_categoria = criar_categoria_service("Educação", 1)

        atualizado = atualizar_parcelamento_service(
            plano["id"],
            1,
            "Curso atualizado",
            nova_categoria["id"],
            nova_conta["id"],
        )

        self.assertIsNotNone(atualizado)
        assert atualizado is not None
        self.assertEqual(atualizado["descricao"], "Curso atualizado")
        self.assertEqual(atualizado["valor_total"], plano["valor_total"])
        self.assertEqual(atualizado["quantidade_parcelas"], 3)
        self.assertTrue(all(item["comentario"] == "Curso atualizado" for item in atualizado["parcelas"]))
        self.assertTrue(all(item["categoria_id"] == nova_categoria["id"] for item in atualizado["parcelas"]))
        self.assertTrue(all(item["conta_id"] == nova_conta["id"] for item in atualizado["parcelas"]))
        self.assertIsNone(
            atualizar_parcelamento_service(
                plano["id"], 2, "Tentativa", self.categoria_b["id"], self.conta_b["id"]
            )
        )
        with self.assertRaisesRegex(ValueError, "Categoria nao encontrada"):
            atualizar_parcelamento_service(
                plano["id"], 1, "Tentativa", self.categoria_b["id"], self.conta_a["id"]
            )

    def test_parcelas_futuras_nao_alteram_saldo_atual_ou_resumo(self):
        # Mantém a data inequivocamente futura mesmo quando o teste cruza a
        # meia-noite entre o fuso local do Python e CURRENT_DATE do banco.
        inicio_futuro = date.today() + timedelta(days=7)
        plano = self.criar_plano(2, "200.00", inicio_futuro)

        conta = next(item for item in listar_contas_formatadas(1) if item["id"] == self.conta_a["id"])
        resumo = obter_resumo_financeiro(1)
        historico = [
            item for item in listar_transacoes_formatadas(1)
            if item["parcelamento_id"] == plano["id"]
        ]
        self.assertEqual(conta["saldo_atual"], 1000.0)
        self.assertEqual(resumo, {"entradas": 0.0, "saidas": 0.0, "saldo": 0.0})
        self.assertEqual(len(historico), 2)

    def test_saldo_e_resumo_consideram_somente_parcelas_com_data_atingida(self):
        plano = self.criar_plano(2, "200.00", date.today())

        conta = next(item for item in listar_contas_formatadas(1) if item["id"] == self.conta_a["id"])
        resumo = obter_resumo_financeiro(1)
        historico = [
            item for item in listar_transacoes_formatadas(1)
            if item["parcelamento_id"] == plano["id"]
        ]

        self.assertEqual(conta["saldo_atual"], 900.0)
        self.assertEqual(resumo, {"entradas": 0.0, "saidas": 100.0, "saldo": -100.0})
        self.assertEqual(len(historico), 2)


if __name__ == "__main__":
    unittest.main()
