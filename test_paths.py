import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
from zimage.paths import load_config, ensure_initial_setup

# Mock the config path to test writing
import zimage.paths
import tempfile
temp_dir = tempfile.mkdtemp()
zimage.paths.CONFIG_PATH = Path(temp_dir) / "config.json"
zimage.paths._CONFIG_CACHE = None

ensure_initial_setup()
config = load_config()
print("Config generated:")
print(config)
