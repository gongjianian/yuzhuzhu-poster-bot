from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_scaffold_exists() -> None:
    expected_paths = [
        ROOT / "requirements.txt",
        ROOT / ".env.example",
        ROOT / ".gitignore",
        ROOT / "tests" / "__init__.py",
        ROOT / "assets" / "products",
        ROOT / "logs",
        ROOT / "prompts",
    ]

    for path in expected_paths:
        assert path.exists()
