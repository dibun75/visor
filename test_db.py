import time
import numpy as np
from visor.db.client import VectorDBClient, EMBEDDING_DIM

client = VectorDBClient(":memory:")
# Insert 10,000 dummy nodes
print("Inserting 10k nodes...")
for i in range(1000):
    vec = np.random.rand(EMBEDDING_DIM).tolist()
    client.upsert_node(f"src/file_{i}.py", "function", f"func_{i}", f"doc {i}", vec)

# Search
start = time.time()
q = np.random.rand(EMBEDDING_DIM).tolist()
res = client.search_similar(q)
end = time.time()
print(f"Search retrieved {len(res)} results in {(end-start)*1000:.2f}ms")
