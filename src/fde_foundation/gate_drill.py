"""Cambio defectuoso intencional para demostrar el bloqueo de CI; nunca debe fusionarse."""


def defective_return_type() -> int:
    return "ci-must-block-this"
