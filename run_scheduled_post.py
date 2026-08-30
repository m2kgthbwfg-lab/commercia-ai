import json
import logging

from app import app
from instagram_publisher import run_due_publications

logging.basicConfig(level=logging.INFO)

with app.app_context():
    print(json.dumps(run_due_publications(), ensure_ascii=False))
