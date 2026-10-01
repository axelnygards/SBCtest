import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("DISABLE_SCHEDULER", "1")
os.environ.setdefault("CATALOGUE_REFRESH_S", "0")  # tests change prices and solve right away
