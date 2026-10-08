import os
import shutil
import tempfile
from pathlib import Path
import pytest
import matplotlib

# Redirect matplotlib config directory to temp folder to prevent permission locks on Windows
os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib_config")
matplotlib.use("Agg")


@pytest.fixture
def tmp_path(request):
    """Custom tmp_path fixture creating isolated directory inside scratch/ to avoid Windows AppData lock issues."""
    test_name = request.node.name.replace("[", "_").replace("]", "_").replace("/", "_")
    scratch_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scratch", "test_runs", test_name)
    if os.path.exists(scratch_dir):
        shutil.rmtree(scratch_dir, ignore_errors=True)
    os.makedirs(scratch_dir, exist_ok=True)
    yield Path(scratch_dir)
    try:
        shutil.rmtree(scratch_dir, ignore_errors=True)
    except Exception:
        pass

