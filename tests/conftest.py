import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from tools.generate_examples import FILES


@pytest.fixture
def examples():
    return {name: factory() for name, factory in FILES.items()}

