import os
from pathlib import Path
import sys


def data_dir():
    override = os.environ.get("LAMBDA_DATA_HOME")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home()/"AppData/Local"))/"LambdaAI"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home()/".local/share"))/"lambda-ai"
