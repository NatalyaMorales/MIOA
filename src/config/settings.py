import os

from dotenv import load_dotenv


load_dotenv()


APP_NAME = os.getenv(
    "APP_NAME",
    "Media Optimization Agent"
)

DATA_PATH = os.getenv(
    "DATA_PATH",
    "data/input/response_curves.xlsx"
)

ENVIRONMENT = os.getenv(
    "ENVIRONMENT",
    "development"
)