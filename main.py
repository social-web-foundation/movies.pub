from fastapi import FastAPI
from fastapi import status

app = FastAPI(title="movies.pub")

@app.get("/livez", status_code=status.HTTP_204_NO_CONTENT)
def livez() -> None:
    return None
