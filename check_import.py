try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    print("Found in langgraph.checkpoint.postgres.aio")
except ImportError:
    print("Not found in langgraph.checkpoint.postgres.aio")
    
try:
    from langgraph.checkpoint.postgres import AsyncPostgresSaver
    print("Found in langgraph.checkpoint.postgres")
except ImportError:
    print("Not found in langgraph.checkpoint.postgres")

import langgraph.checkpoint.postgres
print(f"Module contents: {dir(langgraph.checkpoint.postgres)}")
