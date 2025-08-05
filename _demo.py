
# Python
from faststream.faststream import StreamBody,RequestBody
from fastapi import FastAPI


app = FastAPI()

@app.post("/items/")
async def create_item(body: RequestBody = StreamBody()):
    return {"message": "Item created", "content-type": body.content_type, "body": await body.body()}
# In this example, we define a route operation for POST operations to the path /items/. The function create_item takes as parameter a Request object. We can then use the body method of the Request object to get the raw stream of the request content. This method returns a bytes object that you can further process as needed.

# Remember to check the FastAPI documentation for more details. Happy coding! 🚀

app()
