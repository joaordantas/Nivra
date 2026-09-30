import unittest

from backend.routers.lumi import _proposal_response
from services.lumi_action_proposal_service import ActionProposalDecision
from services.lumi_orchestrator import LUMI_SYSTEM_INSTRUCTIONS


class LumiUxTests(unittest.TestCase):
    def test_prompt_requires_direct_natural_brazilian_format_without_raw_dump(self):
        self.assertIn("Comece pela resposta direta", LUMI_SYSTEM_INSTRUCTIONS)
        self.assertIn("R$ 1.234,56", LUMI_SYSTEM_INSTRUCTIONS)
        self.assertIn("Não despeje o conteúdo bruto", LUMI_SYSTEM_INSTRUCTIONS)
        self.assertIn("no máximo uma sugestão", LUMI_SYSTEM_INSTRUCTIONS)

    def test_ambiguity_asks_only_for_the_first_missing_field(self):
        decision = ActionProposalDecision(
            action_type="create_expense",
            summary="Proposta incompleta",
            payload={},
            missing_fields=("conta", "categoria"),
            warnings=(),
            confirmation=None,
        )
        response = _proposal_response(decision)
        self.assertEqual(response.message, "Em qual conta devo registrar?")
        self.assertIsNone(response.confirmation)
        self.assertFalse(response.execution_enabled)


if __name__ == "__main__":
    unittest.main()
