from pathlib import Path
import yaml

def load_config(path: str) -> dict:
    p = Path(path)
    with p.open() as f:
        return yaml.safe_load(f)
