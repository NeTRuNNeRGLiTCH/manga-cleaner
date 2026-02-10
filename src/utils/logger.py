import logging
import os
from datetime import datetime

#////////////////////////#
#  DIAGNOSTIC LOGGING    #
#////////////////////////#

def setup_logger():
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    log_file = os.path.join("logs", f"manga_cleaner_{datetime.now().strftime('%Y%m%d')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("TitanStudio")