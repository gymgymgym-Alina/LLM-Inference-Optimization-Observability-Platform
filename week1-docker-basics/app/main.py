from fastapi import FastAPI

app = FastAPI(title="week1-hello-world")


@app.get("/")
def root():
    return {"message": "hello world"}


@app.get("/health")
def health():
    return {"status": "ok"}
