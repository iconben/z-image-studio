import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
import asyncio
from zimage.server import get_info

async def test():
    info = await get_info()
    print("API Info returned keys:", info.keys())
    print("Constraints:", info['constraints'])

asyncio.run(test())
