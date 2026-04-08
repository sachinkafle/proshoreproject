from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class AppSettings(BaseSettings):
    """
    Pydantic handles our Environment Validations.
    If 'AZURE_OPENAI_API_KEY' is missing from your local.settings.json,
    the app instantly crashes with a detailed error during startup.
    """
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4o"
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "text-embedding-ada-002"
    
    # Redis configuration for Semantic Cache
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_USE_SSL: bool = False
    REDIS_USE_ENTRA_ID: bool = False
    REDIS_INDEX_NAME: str = "support_tickets_idx"
    
    model_config = SettingsConfigDict(extra="ignore")

@lru_cache()
def get_settings() -> AppSettings:
    """Returns a globally cached instance of the settings."""
    return AppSettings()
