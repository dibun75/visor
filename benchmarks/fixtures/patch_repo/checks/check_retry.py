import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.retry import retry_delays

assert retry_delays(1, 0) == []
assert retry_delays(1, 4) == [1, 2, 4, 8]
assert retry_delays(0.5, 3) == [0.5, 1.0, 2.0]
print("retry checks passed")
