import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.discounts import apply_discount

assert apply_discount(100, 20) == 80
assert apply_discount(19.99, 15) == 16.99
assert apply_discount(50, 0) == 50
assert apply_discount(50, 100) == 0
print("discount checks passed")
