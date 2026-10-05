import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture(scope="session")
def samples(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("make_samples", os.path.join(ROOT, "scripts", "make_samples.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build(str(tmp_path_factory.mktemp("samples")))
