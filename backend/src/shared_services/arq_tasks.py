import asyncio


async def test_task(ctx):
    print("ARQ worker executed test_task")

    await asyncio.sleep(1)

    return {
        "status": "completed",
        "message": "ARQ task executed successfully",
    }