from fastapi import FastAPI
from processador import processar_pedidos

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "API Online"}

@app.post("/rodar-pedidos")
def rodar():
    processar_pedidos()
    return {"mensagem": "Ingestão executada com sucesso"}
