from fastapi import FastAPI

app = FastAPI(title="Mis Finanzas", version="0.1.0")


@app.get("/salud")
def salud():
    return {"estado": "ok"}
