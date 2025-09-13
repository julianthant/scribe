import os
from enum import Enum

from pydantic_settings import BaseSettings
from starlette.config import Config

current_file_dir = os.path.dirname(os.path.realpath(__file__))
env_path = os.path.join(current_file_dir, "..", "..", ".env")
config = Config(env_path)


class AppSettings(BaseSettings):
    APP_NAME: str = config("APP_NAME", default="FastAPI app")
    APP_DESCRIPTION: str | None = config("APP_DESCRIPTION", default=None)
    APP_VERSION: str | None = config("APP_VERSION", default=None)
    LICENSE_NAME: str | None = config("LICENSE", default=None)
    CONTACT_NAME: str | None = config("CONTACT_NAME", default=None)
    CONTACT_EMAIL: str | None = config("CONTACT_EMAIL", default=None)

class TestSettings(BaseSettings): ...

class EnvironmentOption(Enum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"

class EnvironmentSettings(BaseSettings):
    ENVIRONMENT: EnvironmentOption = config("ENVIRONMENT", default=EnvironmentOption.LOCAL)

class MicrosoftGraphSettings(BaseSettings):
    CLIENT_ID: str = config("MS_CLIENT_ID", default="")
    TENANT_ID: str = config("MS_TENANT_ID", default="")
    CLIENT_SECRET: str = config("MS_CLIENT_SECRET", default="")
    
    GRAPH_API_URL: str = config("GRAPH_API_URL", default="https://graph.microsoft.com/v1.0/users")

class Settings(
    AppSettings,
    TestSettings,
    EnvironmentSettings,
    MicrosoftGraphSettings,
):
    pass

settings = Settings()
