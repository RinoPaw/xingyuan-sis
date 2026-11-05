"""Run the submitted source directly, without installing the project."""
from pathlib import Path
import os
import sys


def main():
    if sys.version_info < (3, 14):
        print("星原 SiS 需要 Python 3.14 或更新版本。", file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parent
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root / "src"))
    os.chdir(root)
    from xingyuan_sis.entry import main as run
    return run(sys.argv[1:] or ["--gui"])


if __name__ == "__main__":
    raise SystemExit(main())
