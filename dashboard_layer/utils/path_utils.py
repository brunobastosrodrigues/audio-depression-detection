import os

def get_config_path():
    """
    Dynamically resolve the path to the analysis layer config.json.
    Prioritizes env var, then searches common locations.
    """
    # 1. Environment Variable
    if os.getenv("CONFIG_PATH"):
        return os.getenv("CONFIG_PATH")

    # 2. Potential paths to check
    candidates = [
        # Relative from dashboard_layer (cwd) to analysis_layer
        "../analysis_layer/core/mapping/config.json",
        # Relative from repo root
        "analysis_layer/core/mapping/config.json",
        # Docker mount locations
        "/app/analysis_layer/core/mapping/config.json",
        "/app/core/mapping/config.json",
    ]

    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)

    # 3. Fallback
    return "/app/core/mapping/config.json"
