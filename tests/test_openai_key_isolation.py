"""Keep Bench's OpenAI credential isolated from sibling projects."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (ROOT / "archolith_bench", ROOT / "scripts")
SOURCE_SUFFIXES = {".py", ".sh", ".ps1", ".cmd", ".bat"}

SIBLING_ENV_PATTERNS = (
    re.compile(
        r"(?:OPENAI_API_KEY|OPENAI_KEY)[^\n]{0,200}"
        r"(?:\$\{(?:MENHIR(?:_[A-Z]+)?|SRC)\}[\\/]\.env|"
        r"\$ARCH[\\/]menhir[\\/]\.env|menhir(?:-frontier)?[\\/]\.env)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:\$\{(?:MENHIR(?:_[A-Z]+)?|SRC)\}[\\/]\.env|"
        r"\$ARCH[\\/]menhir[\\/]\.env|menhir(?:-frontier)?[\\/]\.env)"
        r"[^\n]{0,200}(?:OPENAI_API_KEY|OPENAI_KEY)",
        re.IGNORECASE,
    ),
    re.compile(
        r"dotenv_values\([^\n]{0,200}(?:MENHIR(?:_[A-Z]+)?|menhir(?:-frontier)?)"
        r"[^\n]{0,100}[\\/]\.env",
        re.IGNORECASE,
    ),
)


def test_openai_keys_never_fall_back_to_sibling_project_env_files() -> None:
    violations: list[str] = []
    for source_root in SOURCE_ROOTS:
        for path in source_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "OPENAI_API_KEY" not in text and "OPENAI_KEY" not in text:
                continue
            for pattern in SIBLING_ENV_PATTERNS:
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    violations.append(f"{path.relative_to(ROOT)}:{line}")

    assert not violations, (
        "Bench OpenAI launch paths must use archolith-bench/.env, never a sibling "
        f"project's credential: {sorted(set(violations))}"
    )
