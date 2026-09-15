import os

class Settings:
    PROJECT_NAME: str = "Vyra"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vyra")
    # Segredo fora do repo: vive na variavel de ambiente SECRET_KEY
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY nao definida (usa variavel de ambiente)")

settings = Settings()