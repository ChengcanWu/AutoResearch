"""Run unchanged upstream tests with short byte-parameter IDs on Windows."""
from pathlib import Path
import pytest


class ShortByteIds:
    def pytest_make_parametrize_id(self, config, val, argname):
        if isinstance(val, bytes):
            return f'{argname}-{len(val)}-bytes'


root = Path(__file__).resolve().parents[2]   # tools/verify -> 仓库根
raise SystemExit(pytest.main([
    '-q', '-p', 'no:cacheprovider', '--tb=short',
    str(root / 'server/tests'),
], plugins=[ShortByteIds()]))
