from __future__ import annotations

import subprocess
from pathlib import Path

from common import REPO_ROOT


def install_git_hooks() -> Path:
    try:
        repo_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Git hooks can only be installed from within a Git repository.") from exc

    repo_root_path = Path(repo_root)
    hooks_path = repo_root_path / ".githooks"
    subprocess.run(
        ["git", "config", "core.hooksPath", str(hooks_path)],
        check=True,
        cwd=repo_root_path,
    )
    return hooks_path


def main() -> None:
    hooks_path = install_git_hooks()
    print(f"Configured git core.hooksPath -> {hooks_path}")


if __name__ == "__main__":
    main()
