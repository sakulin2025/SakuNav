"""启动入口：python -m sakunav"""

import uvicorn

from sakunav.config import Settings
from sakunav.main import create_app


def main() -> None:
    settings = Settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)


if __name__ == "__main__":
    main()
