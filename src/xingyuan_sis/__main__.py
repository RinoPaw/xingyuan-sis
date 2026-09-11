from .app import XingyuanSIS
from .database import initialize_database


def main() -> None:
    initialize_database()
    XingyuanSIS().run()


if __name__ == "__main__":
    main()
