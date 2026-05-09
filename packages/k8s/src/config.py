from pydantic_settings import BaseSettings, SettingsConfigDict
from os import getenv

class Settings(BaseSettings):
    # model_config = SettingsConfigDict(
    #     env_prefix="SHKCTRL_",
    #     env_file=".env",
    #     extra="ignore",
    # )

    namespace: str = "marshal"
    job_image: str = getenv("JOB_IMAGE", None)
    kube_context: str | None = None
    in_cluster: bool = getenv("IN_CLUSTER", "false").lower() == "true"
