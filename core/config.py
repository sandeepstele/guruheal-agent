from enum import Enum
from typing import Optional

from pydantic import Field, BaseModel
from pydantic_settings import BaseSettings


class EnvironmentType(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    STAGING = "staging"


class SASHeader(BaseModel):
    OCP_APIM_SUBSCRIPTION_KEY: str = Field(serialization_alias="ocp-apim-subscription-key", alias="ocp-apim-subscription-key")


class SASConfig(BaseModel):
    BASE_URL: str
    HEADER: SASHeader


class DocserverConfig(BaseModel):
    ES_URL: str = Field(serialization_alias="es_url")
    ES_PASSWORD: str = Field(serialization_alias="es_password")
    ES_USER: str = Field(serialization_alias="es_user")
    NEO_4J_URL: str = Field(serialization_alias="neo4j_url")
    NEO_4J_PASSWORD: str = Field(serialization_alias="neo4j_password")
    NEO_4J_USERNAME: str = Field(serialization_alias="neo4j_user")
    MINIO_ACCESS_KEY: str = Field(serialization_alias="minio_access_key")
    MINIO_SECURE: str = Field(serialization_alias="minio_secure")
    MINIO_SECRET_KEY: str = Field(serialization_alias="minio_secret_key")
    MINIO_URL: str = Field(serialization_alias="minio_url")
    ETCD_HOST: str = Field(serialization_alias="etcd_host")
    ETCD_PORT: int = Field(serialization_alias="etcd_port")


class MongoDBConfig(BaseModel):
    MONGO_URI: str = Field(default="mongodb://localhost:27017")
    MONGO_DB_NAME: str = Field(default="chat_app")


class Settings(BaseSettings):
    APP_NAME: str = "FastAPI Boilerplate"
    APP_DESCRIPTION: str = "FastAPI Boilerplate for Microservices"
    APP_VERSION: str = "0.1.0"

    ENVIRONMENT: str = EnvironmentType.DEVELOPMENT
    APP_PORT: int = 8000

    # MongoDB Configuration
    MONGO_URI: str = Field(default="mongodb://localhost:27017")
    MONGO_DB_NAME: str = Field(default="chat_app")

    # OpenAI Configuration
    API_KEY: str = Field(default="")
    OPENAI_BASE_URL: str = Field(default="https://api.dosashop1.com/openai/v1")

    FASTSTREAM_PROVIDER: Optional[str] = None
    FASTSTREAM_ENABLE: bool = False

    CELERY_ENABLE: bool = False
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_BACKEND_URL: Optional[str] = None
    CELERY_DEFAULT_QUEUE: Optional[str] = "Celery"

    # SAQ Configuration
    SAQ_ENABLE: bool = Field(default=False)
    REDIS_URL: str | None = Field(default=None)
    SAQ_WEB_PORT: int = Field(default=8081)
    SAQ_WORKERS: int = Field(default=1)

    PG_HOST: str = Field(default='aws-0-ap-south-1.pooler.supabase.com')
    PG_PORT: int = Field(default=5432)
    PG_USER: str = Field(default='postgres.foartimacvkfjphhgjxm')
    PG_PASSWORD: str = Field(default='5QmEDEeirDVWKXxj')
    PG_DATABASE: str = Field(default='postgres')

    # SAS Configuration
    SAS: Optional[SASConfig] = None

    # Docserver Config
    DOCSERVER: Optional[DocserverConfig] = None

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        extra = "allow"


settings = Settings()
