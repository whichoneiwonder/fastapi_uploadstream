
# Python
from faststream.faststream import StreamBody, RequestBody
from fastapi import FastAPI, UploadFile



app = FastAPI()

@app.post("/items/")
async def create_item(field: UploadFile = StreamBody(title="body content")) -> dict[str , str]:
    return {
        "message": "Item created",
        "content-type": field.content_type,
        "body": (await field.body()).decode("utf-8")
    }

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app,
        # reload=True,
        # reload_delay=1,
    )
