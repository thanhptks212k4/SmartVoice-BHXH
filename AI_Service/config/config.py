
from pydantic_settings import BaseSettings , SettingsConfigDict
import os 
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
class Settings(BaseSettings):
        REDIS_HOST : str = "REDIS_HOST"
        REDIS_PORT : str = "REDIS_PORT"
        REDIS_PASSWORD : str = "REDIS_PASSWORD"
        API_LLM : str = "API_LLM"
        MODEL_NAME : str = "MODEL_NAME"  
        QDRANT_HOST : str = "QDRANT_HOST"   
        QDRANT_PORT : int = "QDRANT_PORT"
        MODEL_QDRANT : str = "MODEL_QDRANT"
        model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),  
        env_file_encoding='utf-8',
        extra='ignore'
    )


settings = Settings()