from fastapi import FastAPI

app = FastAPI(
    title="Grid Risk MVP",
    description="Interconnection Queue Risk Analysis Platform",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "product": "Grid Risk MVP",
        "status": "running"
    }
