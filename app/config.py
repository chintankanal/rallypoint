from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/rallypoint"
    jwt_secret: str = "tnud1zc6gad971g0irurptmie5yahlge"
    jwt_expiry_hours: int = 24
    frontend_url: str = "http://localhost:5173"
    webhook_secret: str = ""
    webhook_url: str = ""
    internal_job_secret: str = "u9dqoepr3hawymg2b3omaq82uar0qmid"
    resend_api_key: str = "re_69RLa5xi_FvBVq7ytu98QizFLjznt9Tc1"
    from_email: str = "onboarding@resend.dev"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
