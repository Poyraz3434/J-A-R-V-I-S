"""Deterministic commands that remain available without an AI connection."""
from __future__ import annotations

import ast
import datetime
import math
import operator
import re

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_MAX_EXPRESSION_LENGTH = 120
_MAX_EXPRESSION_NODES = 32
_MAX_RESULT_MAGNITUDE = 1e100


def _evaluate_expression(expression: str) -> int | float:
    if not expression or len(expression) > _MAX_EXPRESSION_LENGTH:
        raise ValueError("İfade boş veya izin verilen uzunluktan büyük.")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > _MAX_EXPRESSION_NODES:
        raise ValueError("İfade çok karmaşık.")

    def evaluate(node: ast.AST) -> int | float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(
                node.value, (int, float)
            ):
                raise ValueError("Yalnızca sayılar kullanılabilir.")
            result = node.value
        elif isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            result = _UNARY_OPERATORS[type(node.op)](evaluate(node.operand))
        elif isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 8:
                raise ValueError("Üs değeri en fazla 8 olabilir.")
            result = _BINARY_OPERATORS[type(node.op)](left, right)
        else:
            raise ValueError("Bu ifade türüne izin verilmiyor.")

        if not math.isfinite(result) or abs(result) > _MAX_RESULT_MAGNITUDE:
            raise ValueError("Sonuç izin verilen aralığın dışında.")
        return result

    return evaluate(tree)


def _format_number(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return format(value, ".12g")


def handle_offline_command(
    text: str,
    now: datetime.datetime | None = None,
) -> str | None:
    """Handle explicit local-only requests; return None for other messages."""
    normalized = " ".join((text or "").casefold().split()).rstrip("?.!")
    now = now or datetime.datetime.now()

    if normalized in {"saat kaç", "saat kac", "şu an saat kaç", "su an saat kac"}:
        return f"Yerel saat: {now.strftime('%H:%M:%S')}."

    if normalized in {
        "bugünün tarihi ne",
        "bugunun tarihi ne",
        "bugün tarih ne",
        "bugun tarih ne",
        "bugün günlerden ne",
        "bugun gunlerden ne",
    }:
        return f"Yerel tarih: {now.strftime('%d.%m.%Y')}."

    if normalized in {"çevrimdışı komutlar", "cevrimdisi komutlar"}:
        return (
            "İnternet olmadan kullanılabilenler: 'saat kaç', "
            "'bugünün tarihi ne', 'hesapla: 12 * (3 + 4)', "
            "'sistem durumu', 'sohbet geçmişinde ara <ifade>' ve "
            "'hafızada ara <ifade>'. Genel AI yanıtları için internet gerekir."
        )

    calculation = re.fullmatch(
        r"(?:hesapla|hesap)\s*[:：]?\s*(.+)", normalized
    )
    if calculation is None:
        calculation = re.fullmatch(
            r"(.+?)\s+(?:kaç eder|kac eder|sonucu nedir)",
            normalized,
        )
    if calculation is None:
        return None

    try:
        result = _evaluate_expression(calculation.group(1).strip())
    except (ArithmeticError, SyntaxError, ValueError, TypeError) as exc:
        return f"Hesaplama yapılamadı: {exc}"
    return f"Sonuç: {_format_number(result)}"
