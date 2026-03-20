from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    REDIS_HOST: str = "REDIS_HOST"
    REDIS_PORT: int = "REDIS_PORT" 
    REDIS_PASSWORD: str = "REDIS_PASSWORD"
    EXTERNAL_HOST: str = "EXTERNAL_HOST" 
    EXTERNAL_PORT: int = "EXTERNAL_PORT" 
    QUEUE_MAXSIZE: int = "QUEUE_MAXSIZE" 
    STREAM_GET_TIMEOUT: float = "STREAM_GET_TIMEOUT" 
    QUEUE_PUT_TIMEOUT : float = "QUEUE_PUT_TIMEOUT"




    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()