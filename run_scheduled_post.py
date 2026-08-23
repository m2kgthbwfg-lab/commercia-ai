import json
import logging

from instagram_publisher import run_daily_publication

logging.basicConfig(level=logging.INFO)
print(json.dumps(run_daily_publication(), ensure_ascii=False))
