"""Isolated test-environment bootstrap and destructive-reset guard (MD-01)."""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.test_guard import validate_test_database_url  # noqa: E402

_BOOTSTRAPPED = False
_RUN_TEMP_DIR: Path | None = None


def configure_isolated_test_env() -> Path:
    """Configure a safe per-run isolated DB/storage before importing ``app.db``."""
    global _BOOTSTRAPPED, _RUN_TEMP_DIR
    if _BOOTSTRAPPED and _RUN_TEMP_DIR is not None:
        return _RUN_TEMP_DIR

    original_db_url = os.environ.get('DATABASE_URL')
    explicit_app_url = os.environ.get('APP_DATABASE_URL')
    app_urls = [u for u in (original_db_url, explicit_app_url) if u]

    run_dir = Path(tempfile.mkdtemp(prefix='agrosphere-pytest-')).resolve()
    _RUN_TEMP_DIR = run_dir
    atexit.register(lambda: shutil.rmtree(run_dir, ignore_errors=True))

    default_sqlite = 'sqlite:///' + str(run_dir / 'test.db').replace('\\', '/')
    requested_test_url = os.environ.get('TEST_DATABASE_URL')

    if requested_test_url is not None:
        safe_url = validate_test_database_url(
            requested_test_url,
            app_urls=app_urls,
            api_dir=API_DIR,
        )
    else:
        safe_url = validate_test_database_url(
            default_sqlite,
            app_urls=app_urls,
            api_dir=API_DIR,
        )

    os.environ['DATABASE_URL'] = safe_url
    os.environ['IMAGE_STORAGE_PATH'] = str(run_dir / 'images')
    os.environ['MODEL_DIR'] = str(run_dir / 'no-model-default')
    os.environ['MULTICROP_MODEL_DIR'] = str(run_dir / 'no-multicrop-default')
    _BOOTSTRAPPED = True
    return run_dir


configure_isolated_test_env()
