"""固定项目角色的名称和标准化规则。"""

PROJECT_ROLE_NAMES = ("SE", "TPM", "TL/FO", "CodeReview")
SINGLE_PROJECT_ROLES = frozenset({"SE", "TPM"})

_ROLE_ALIASES = {
    "se": "SE",
    "tpm": "TPM",
    "tl/fo": "TL/FO",
    "tl／fo": "TL/FO",
    "codereview": "CodeReview",
    "code_review": "CodeReview",
    "code review": "CodeReview",
}


def canonical_project_role(value: object) -> str | None:
    """把用户输入的角色标签转换为系统固定名称。"""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    compact = raw.replace("／", "/").replace(" ", "")
    return _ROLE_ALIASES.get(compact.casefold())


def empty_role_assignments() -> dict[str, list[int]]:
    return {role: [] for role in PROJECT_ROLE_NAMES}
