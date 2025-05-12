import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import random
from motor.motor_asyncio import AsyncIOMotorClient # Driver assíncrono
from dotenv import load_dotenv
from pydantic import BaseModel # Para modelar os dados
from typing import List, Optional # Tipagem
from contextlib import asynccontextmanager # Importação necessária

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configuração do MongoDB ---
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("Variável de ambiente MONGO_URI não definida!")

DATABASE_NAME = "TCC" # Ou o nome que você definiu na URI ou quer usar
COLLECTION_NAME = "consumo_eletrico"

# --- Modelo Pydantic para os dados de consumo ---
class ConsumoItem(BaseModel):
    data: str
    hora: str
    aparelho: str
    consumo: float

# --- Lifespan para gerenciar conexão com MongoDB ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código que roda ANTES do app iniciar (startup)
    print("Iniciando conexão com MongoDB...")
    app.mongodb_client = AsyncIOMotorClient(MONGO_URI)
    app.mongodb = app.mongodb_client[DATABASE_NAME]
    print(f"Conectado ao banco de dados MongoDB: {DATABASE_NAME}")
    yield # O aplicativo roda aqui enquanto o lifespan está ativo
    # Código que roda DEPOIS do app parar (shutdown)
    print("Fechando conexão com MongoDB...")
    app.mongodb_client.close()
    print("Conexão com MongoDB fechada.")

# --- Aplicação FastAPI ---
app = FastAPI(lifespan=lifespan) # Passa a função lifespan

# --- Middleware CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Rota para gerar e salvar dados de consumo ---
@app.post("/consumo", response_model=List[ConsumoItem])
async def gerar_e_salvar_consumo(request: Request):
    try:
        req = await request.json()
        data_req = req.get("data")
        aparelho_req = req.get("aparelho")

        if not data_req or not aparelho_req:
            raise HTTPException(status_code=400, detail="Campos 'data' e 'aparelho' são obrigatórios.")

        base_time = datetime.strptime("00:00", "%H:%M")
        dados_gerados: List[ConsumoItem] = []

        for i in range(24):
            hora = (base_time + timedelta(hours=i)).strftime("%H:%M")
            consumo = round(random.uniform(0.05, 0.3), 3)

            item = ConsumoItem(
                data=data_req,
                hora=hora,
                aparelho=aparelho_req,
                consumo=consumo
            )
            dados_gerados.append(item)

        dados_para_inserir = [item.dict() for item in dados_gerados]

        collection = app.mongodb[COLLECTION_NAME]
        result = await collection.insert_many(dados_para_inserir)

        print(f"Inseridos {len(result.inserted_ids)} documentos na coleção '{COLLECTION_NAME}'.")

        return dados_gerados

    except Exception as e:
        print(f"Erro ao processar a requisição /consumo: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {e}")

# --- Rota de exemplo para buscar dados (opcional) ---
@app.get("/consumo/buscar", response_model=List[ConsumoItem])
async def buscar_consumo(data: Optional[str] = None, aparelho: Optional[str] = None):
    query = {}
    if data:
        query["data"] = data
    if aparelho:
        query["aparelho"] = aparelho

    collection = app.mongodb[COLLECTION_NAME]
    documentos = await collection.find(query).to_list(length=1000)

    resultados = []
    for doc in documentos:
        # Não precisa mais converter _id se o modelo Pydantic não o tiver
        try:
            resultados.append(ConsumoItem(**doc))
        except Exception as e:
            print(f"Erro ao converter documento do MongoDB: {doc} - Erro: {e}")

    return resultados

