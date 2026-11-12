import os
from dotenv import load_dotenv

load_dotenv()

environment = os.getenv("DJANGO_ENV", "dev").lower()

if environment == "prod":
    from .prod import *
elif environment == "test":
    from .test import *
else:
    from .dev import *
