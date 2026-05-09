from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_expiry_hours: int = 24
    frontend_url: str = "http://localhost:5173"
    webhook_secret: str = ""
    webhook_url: str = ""
    internal_job_secret: str
    resend_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
