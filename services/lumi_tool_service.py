from collections.abc import Callable
from datetime import date
from decimal import Decimal

from services.insight_service import (
    obter_contexto_financeiro_lumi_service,
    obter_insights_financeiros_service,
)
from services.transacao_service import localizar_transacoes_lumi_service


LUMI_TOOL_CATALOG = {
    "get_financial_insights": {
        "description": "Retorna resumo, comparação, categorias e alertas financeiros do usuário autenticado.",
        "required": ["data_inicio", "data_fim"],
        "read_only": True,
        "model_enabled": False,
    },
    "get_financial_context": {
        "description": "Retorna o contexto financeiro consolidado e estruturado do usuário autenticado.",
        "required": ["data_inicio", "data_fim"],
        "read_only": True,
        "model_enabled": True,
    },
    "find_transactions": {
        "description": "Localiza transações manuais do usuário autenticado para possível edição, sem executar alterações.",
        "required": [],
        "read_only": True,
        "model_enabled": False,
    },
}


class LumiToolValidationError(ValueError):
    pass


def listar_definicoes_tools_lumi() -> list[dict]:
    """Expõe ao provider apenas tools explicitamente liberadas e somente leitura."""
    return [
        ({
            "type": "function",
            "name": tool_name,
            "description": definition["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "data_inicio": {
                        "type": "string",
                        "description": "Data inicial inclusiva no formato YYYY-MM-DD.",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$",
                    },
                    "data_fim": {
                        "type": "string",
                        "description": "Data final inclusiva no formato YYYY-MM-DD.",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$",
                    },
                },
                "required": ["data_inicio", "data_fim"],
                "additionalProperties": False,
            },
            "strict": True,
        } if tool_name != "find_transactions" else {
            "type": "function",
            "name": tool_name,
            "description": definition["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {"type": "string"},
                    "valor": {"type": "string", "pattern": r"^\d+(?:\.\d{2})?$"},
                    "data": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                    "tipo": {"type": "string", "enum": ["entrada", "saida"]},
                },
                "required": [],
                "additionalProperties": False,
            },
            "strict": True,
        })
        for tool_name, definition in LUMI_TOOL_CATALOG.items()
        if definition["read_only"] and definition["model_enabled"]
    ]


def validar_argumentos_lumi_tool(tool_name: str, arguments: object) -> dict[str, str]:
    definition = LUMI_TOOL_CATALOG.get(tool_name)
    if definition is None or not definition["read_only"]:
        raise LumiToolValidationError("Ferramenta da Lumi não permitida.")
    if not isinstance(arguments, dict):
        raise LumiToolValidationError("Argumentos da ferramenta devem ser um objeto JSON.")
    if tool_name == "find_transactions":
        allowed = {"descricao", "valor", "data", "tipo"}
        if set(arguments) - allowed:
            raise LumiToolValidationError("Argumentos da ferramenta inválidos.")
        result = {key: str(value).strip() for key, value in arguments.items() if value is not None}
        if "data" in result:
            try:
                result["data"] = date.fromisoformat(result["data"]).isoformat()
            except ValueError as exc:
                raise LumiToolValidationError("Data da ferramenta inválida.") from exc
        if "tipo" in result and result["tipo"] not in {"entrada", "saida"}:
            raise LumiToolValidationError("Tipo da ferramenta inválido.")
        if "valor" in result:
            try:
                result["valor"] = format(Decimal(result["valor"]).quantize(Decimal("0.01")), "f")
            except Exception as exc:
                raise LumiToolValidationError("Valor da ferramenta inválido.") from exc
        return result
    expected = set(definition["required"])
    received = set(arguments)
    if received != expected:
        raise LumiToolValidationError("Argumentos da ferramenta inválidos.")
    try:
        start = date.fromisoformat(str(arguments["data_inicio"]))
        end = date.fromisoformat(str(arguments["data_fim"]))
    except (TypeError, ValueError) as exc:
        raise LumiToolValidationError("Período da ferramenta inválido.") from exc
    if start > end:
        raise LumiToolValidationError("A data inicial deve ser anterior ou igual à data final.")
    return {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}


def executar_lumi_tool(
    tool_name: str,
    arguments: dict,
    usuario_id: int,
    *,
    handlers: dict[str, Callable[..., dict]] | None = None,
) -> dict:
    validated_arguments = validar_argumentos_lumi_tool(tool_name, arguments)
    allowed_handlers = handlers or {
        "get_financial_insights": obter_insights_financeiros_service,
        "get_financial_context": obter_contexto_financeiro_lumi_service,
        "find_transactions": localizar_transacoes_lumi_service,
    }
    handler = allowed_handlers.get(tool_name)
    if handler is None or tool_name not in LUMI_TOOL_CATALOG:
        raise ValueError("Ferramenta da Lumi não permitida.")
    if tool_name == "find_transactions":
        from decimal import Decimal
        return handler(
            usuario_id,
            descricao=validated_arguments.get("descricao"),
            valor=Decimal(validated_arguments["valor"]) if validated_arguments.get("valor") else None,
            data=validated_arguments.get("data"),
            tipo=validated_arguments.get("tipo"),
        )
    return handler(usuario_id, validated_arguments["data_inicio"], validated_arguments["data_fim"])
