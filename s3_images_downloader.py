from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import boto3
import time
import io
import os
from pathlib import Path
from datetime import datetime

app = FastAPI(title="S3 Image Downloader API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurações AWS S3
from dotenv import load_dotenv
load_dotenv()

AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'sa-east-1')
BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'aplis2')
IMAGE_PREFIX = 'lab/Arquivos/Foto/'
LOCAL_IMAGES_DIR = Path(__file__).parent / 'imagens_s3'

# Modelos Pydantic
class ImageInfo(BaseModel):
    key: str
    size: int
    last_modified: str
    file_name: str
    pasta: str
    size_kb: float

class DownloadRequest(BaseModel):
    keys: List[str]

class SearchRequest(BaseModel):
    query: str
    codigo_pasta: Optional[str] = None

class ListRequest(BaseModel):
    limit: Optional[int] = None
    offset: int = 0

class RecentRequest(BaseModel):
    count: int = 10

class ExtensionRequest(BaseModel):
    extension: str

def conectar_s3():
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
        return s3_client
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao conectar S3: {str(e)}")

def listar_imagens(s3_client, bucket, prefix):
    try:
        imagens = []
        extensoes_img = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', 'pdf')

        # Listar com paginação para pegar todos os arquivos
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

        for page in pages:
            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                key = obj['Key']
                if not key.endswith('/') and key.lower().endswith(extensoes_img):
                    imagens.append({
                        'key': key,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'file_name': key.split('/')[-1],
                        'pasta': '/'.join(key.split('/')[:-1]),
                        'size_kb': round(obj['Size'] / 1024, 1)
                    })

        imagens.sort(key=lambda x: x['last_modified'], reverse=True)
        return imagens

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao listar imagens: {str(e)}")

def baixar_imagem_memoria(s3_client, bucket, key):
    """Baixa imagem direto para memória e retorna como bytes"""
    try:
        buffer = io.BytesIO()
        s3_client.download_fileobj(bucket, key, buffer)
        buffer.seek(0)
        return buffer
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao baixar {key}: {str(e)}")

# ==================== ENDPOINTS API ====================

@app.get("/")
async def root():
    """Endpoint raiz com informações da API"""
    return {
        "message": "S3 Image Downloader API",
        "version": "1.0.0",
        "bucket": BUCKET_NAME,
        "prefix": IMAGE_PREFIX,
        "endpoints": {
            "GET /images": "Listar todas as imagens",
            "GET /images/recent": "Listar imagens mais recentes",
            "GET /images/search": "Buscar imagens por nome",
            "GET /images/extension/{ext}": "Listar por extensão",
            "GET /download/{key:path}": "Baixar imagem específica",
            "GET /stream/{key:path}": "Stream de imagem"
        }
    }

@app.get("/images", response_model=List[ImageInfo])
async def listar_todas_imagens(
    limit: Optional[int] = Query(None, description="Limitar número de resultados"),
    offset: int = Query(0, description="Offset para paginação")
):
    """Lista todas as imagens do S3"""
    s3 = conectar_s3()
    imagens = listar_imagens(s3, BUCKET_NAME, IMAGE_PREFIX)

    if not imagens:
        return []

    # Paginação
    if limit:
        return imagens[offset:offset + limit]
    return imagens[offset:]

@app.get("/images/recent", response_model=List[ImageInfo])
async def listar_recentes(
    count: int = Query(10, description="Quantidade de imagens recentes", ge=1, le=100)
):
    """Lista as N imagens mais recentes"""
    s3 = conectar_s3()
    imagens = listar_imagens(s3, BUCKET_NAME, IMAGE_PREFIX)

    if not imagens:
        return []

    return imagens[:count]

@app.get("/images/search", response_model=List[ImageInfo])
async def buscar_imagens(
    q: str = Query(..., description="Termo de busca no nome do arquivo"),
    codigo_pasta: Optional[str] = Query(None, description="Código da pasta para busca rápida")
):
    """Busca imagens por nome"""
    s3 = conectar_s3()

    # Determinar prefixo de busca
    if codigo_pasta:
        prefix_busca = f"{IMAGE_PREFIX}{codigo_pasta}/"
    else:
        prefix_busca = IMAGE_PREFIX

    imagens = listar_imagens(s3, BUCKET_NAME, prefix_busca)

    # Filtrar por termo de busca
    imagens_encontradas = [
        img for img in imagens
        if q.lower() in img['file_name'].lower()
    ]

    return imagens_encontradas

@app.get("/images/extension/{extension}", response_model=List[ImageInfo])
async def listar_por_extensao(extension: str):
    """Lista imagens por extensão (jpg, png, gif, bmp, tiff, webp, pdf)"""
    s3 = conectar_s3()
    imagens = listar_imagens(s3, BUCKET_NAME, IMAGE_PREFIX)

    # Normalizar extensão
    ext = extension.lower()
    if not ext.startswith('.'):
        ext = f'.{ext}'

    # Tratar JPEG como JPG também
    if ext == '.jpeg':
        imagens_filtradas = [
            img for img in imagens
            if img['file_name'].lower().endswith(('.jpg', '.jpeg'))
        ]
    else:
        imagens_filtradas = [
            img for img in imagens
            if img['file_name'].lower().endswith(ext)
        ]

    return imagens_filtradas

@app.get("/download/{key:path}")
async def download_imagem(key: str):
    """Baixa uma imagem específica pelo key"""
    s3 = conectar_s3()

    try:
        buffer = baixar_imagem_memoria(s3, BUCKET_NAME, key)
        file_name = key.split('/')[-1]

        # Determinar content type baseado na extensão
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.pdf': 'application/pdf'
        }

        ext = Path(file_name).suffix.lower()
        content_type = content_types.get(ext, 'application/octet-stream')

        return StreamingResponse(
            buffer,
            media_type=content_type,
            headers={
                'Content-Disposition': f'attachment; filename="{file_name}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Imagem não encontrada: {str(e)}")

@app.get("/stream/{key:path}")
async def stream_imagem(key: str):
    """Retorna stream da imagem para visualização inline"""
    s3 = conectar_s3()

    try:
        buffer = baixar_imagem_memoria(s3, BUCKET_NAME, key)
        file_name = key.split('/')[-1]

        # Determinar content type
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.pdf': 'application/pdf'
        }

        ext = Path(file_name).suffix.lower()
        content_type = content_types.get(ext, 'application/octet-stream')

        return StreamingResponse(
            buffer,
            media_type=content_type,
            headers={
                'Content-Disposition': f'inline; filename="{file_name}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Imagem não encontrada: {str(e)}")

@app.get("/info/{key:path}")
async def info_imagem(key: str):
    """Retorna informações detalhadas sobre uma imagem"""
    s3 = conectar_s3()

    try:
        response = s3.head_object(Bucket=BUCKET_NAME, Key=key)

        return {
            "key": key,
            "file_name": key.split('/')[-1],
            "size": response['ContentLength'],
            "size_kb": round(response['ContentLength'] / 1024, 1),
            "size_mb": round(response['ContentLength'] / (1024 * 1024), 2),
            "last_modified": response['LastModified'].isoformat(),
            "content_type": response.get('ContentType', 'unknown'),
            "metadata": response.get('Metadata', {})
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Imagem não encontrada: {str(e)}")

@app.get("/health")
async def health_check():
    """Verifica saúde da API e conexão com S3"""
    try:
        s3 = conectar_s3()
        # Tenta listar apenas 1 objeto para verificar conectividade
        s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=IMAGE_PREFIX, MaxKeys=1)
        return {
            "status": "healthy",
            "s3_connection": "ok",
            "bucket": BUCKET_NAME,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "s3_connection": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# ==================== ENDPOINTS POST (para uso via terminal/JSON) ====================

@app.post("/api/list", response_model=List[ImageInfo])
async def listar_imagens_post(request: ListRequest):
    """Lista imagens via POST (aceita JSON no body)"""
    s3 = conectar_s3()
    imagens = listar_imagens(s3, BUCKET_NAME, IMAGE_PREFIX)

    if not imagens:
        return []

    if request.limit:
        return imagens[request.offset:request.offset + request.limit]
    return imagens[request.offset:]

@app.post("/api/recent", response_model=List[ImageInfo])
async def listar_recentes_post(request: RecentRequest):
    """Lista imagens recentes via POST"""
    s3 = conectar_s3()
    imagens = listar_imagens(s3, BUCKET_NAME, IMAGE_PREFIX)

    if not imagens:
        return []

    return imagens[:request.count]

@app.post("/api/search", response_model=List[ImageInfo])
async def buscar_imagens_post(request: SearchRequest):
    """Busca imagens via POST (aceita JSON no body)"""
    s3 = conectar_s3()

    # Determinar prefixo de busca
    if request.codigo_pasta:
        prefix_busca = f"{IMAGE_PREFIX}{request.codigo_pasta}/"
    else:
        prefix_busca = IMAGE_PREFIX

    imagens = listar_imagens(s3, BUCKET_NAME, prefix_busca)

    # Filtrar por termo de busca
    imagens_encontradas = [
        img for img in imagens
        if request.query.lower() in img['file_name'].lower()
    ]

    return imagens_encontradas

@app.post("/api/extension", response_model=List[ImageInfo])
async def listar_por_extensao_post(request: ExtensionRequest):
    """Lista por extensão via POST"""
    s3 = conectar_s3()
    imagens = listar_imagens(s3, BUCKET_NAME, IMAGE_PREFIX)

    # Normalizar extensão
    ext = request.extension.lower()
    if not ext.startswith('.'):
        ext = f'.{ext}'

    # Tratar JPEG como JPG também
    if ext == '.jpeg':
        imagens_filtradas = [
            img for img in imagens
            if img['file_name'].lower().endswith(('.jpg', '.jpeg'))
        ]
    else:
        imagens_filtradas = [
            img for img in imagens
            if img['file_name'].lower().endswith(ext)
        ]

    return imagens_filtradas

@app.post("/api/download-info")
async def download_info_post(request: dict):
    """Retorna informações de download de uma imagem via POST"""
    key = request.get('key')
    if not key:
        raise HTTPException(status_code=400, detail="Campo 'key' é obrigatório")

    s3 = conectar_s3()

    try:
        response = s3.head_object(Bucket=BUCKET_NAME, Key=key)

        return {
            "key": key,
            "file_name": key.split('/')[-1],
            "size": response['ContentLength'],
            "size_kb": round(response['ContentLength'] / 1024, 1),
            "size_mb": round(response['ContentLength'] / (1024 * 1024), 2),
            "last_modified": response['LastModified'].isoformat(),
            "content_type": response.get('ContentType', 'unknown'),
            "download_url": f"/download/{key}",
            "stream_url": f"/stream/{key}"
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Imagem não encontrada: {str(e)}")

# ==================== MODO CLI (TERMINAL INTERATIVO) ====================

def menu_principal_cli():
    """Menu interativo de linha de comando"""
    while True:
        print("\n" + "="*60)
        print("S3 IMAGE DOWNLOADER - MODO CLI")
        print("="*60)
        print("1. Listar todas as imagens")
        print("2. Buscar imagem por nome")
        print("3. Listar imagens por extensão")
        print("4. Baixar últimas N imagens")
        print("5. Sair")
        print("="*60)

        opcao = input("Escolha uma opção: ").strip()

        if opcao == '1':
            listar_todas_cli()
        elif opcao == '2':
            buscar_por_nome_cli()
        elif opcao == '3':
            listar_por_extensao_cli()
        elif opcao == '4':
            baixar_ultimas_n_cli()
        elif opcao == '5':
            print("[INFO] Encerrando...")
            break
        else:
            print("[ERRO] Opção inválida!")

def listar_todas_cli():
    """Lista todas as imagens no terminal"""
    print("\n[INFO] Conectando ao S3...")
    s3 = conectar_s3()

    print(f"[INFO] Listando imagens em {BUCKET_NAME}/{IMAGE_PREFIX}...")
    imagens = listar_imagens(s3, BUCKET_NAME, IMAGE_PREFIX)

    if not imagens:
        print("[AVISO] Nenhuma imagem encontrada")
        return

    print(f"\n[INFO] {len(imagens)} imagens encontradas:\n")

    for i, img in enumerate(imagens[:50], 1):  # Limita a 50 para não poluir terminal
        print(f"{i:3}. {img['file_name']:<50} {img['size_kb']:>8.1f}KB  {img['last_modified'][:19]}")

    if len(imagens) > 50:
        print(f"\n... e mais {len(imagens) - 50} imagens")

def buscar_por_nome_cli():
    """Busca imagens por nome no terminal"""
    nome_busca = input("\nDigite o nome ou parte do nome da imagem: ").strip()

    if not nome_busca:
        print("[ERRO] Nome não pode estar vazio")
        return

    print("\n[OPÇÃO] Você sabe o código da pasta? (ex: 0200, 0031, 0032...)")
    codigo_pasta = input("Digite o código (ou deixe vazio para buscar em todas): ").strip()

    print("\n[INFO] Conectando ao S3...")
    s3 = conectar_s3()

    if codigo_pasta:
        prefix_busca = f"{IMAGE_PREFIX}{codigo_pasta}/"
        print(f"[INFO] Busca rápida em {prefix_busca}...")
    else:
        prefix_busca = IMAGE_PREFIX
        print(f"[INFO] Buscando em todas as pastas (pode demorar)...")

    imagens = listar_imagens(s3, BUCKET_NAME, prefix_busca)

    imagens_encontradas = [
        img for img in imagens
        if nome_busca.lower() in img['file_name'].lower()
    ]

    if not imagens_encontradas:
        print(f"[AVISO] Nenhuma imagem encontrada com '{nome_busca}'")
        return

    print(f"\n[INFO] {len(imagens_encontradas)} imagem(ns) encontrada(s):\n")

    for i, img in enumerate(imagens_encontradas, 1):
        pasta_nome = img['pasta'].split('/')[-1]
        print(f"{i}. [{pasta_nome}] {img['file_name']:<50} {img['size_kb']:>8.1f}KB  {img['last_modified'][:19]}")

    # Opção de baixar
    if imagens_encontradas:
        baixar = input("\nDeseja baixar alguma imagem? (s/n): ").strip().lower()
        if baixar == 's':
            if len(imagens_encontradas) == 1:
                num = 1
            else:
                try:
                    num = int(input(f"Digite o número da imagem (1-{len(imagens_encontradas)}): ").strip())
                except:
                    print("[ERRO] Número inválido")
                    return

            if 1 <= num <= len(imagens_encontradas):
                img_selecionada = imagens_encontradas[num - 1]
                LOCAL_IMAGES_DIR.mkdir(exist_ok=True)
                destino = LOCAL_IMAGES_DIR / img_selecionada['file_name']

                print(f"\n[INFO] Baixando {img_selecionada['file_name']}...")
                try:
                    s3.download_file(BUCKET_NAME, img_selecionada['key'], str(destino))
                    print(f"[OK] Salvo em: {destino}")
                except Exception as e:
                    print(f"[ERRO] Falha ao baixar: {e}")
            else:
                print("[ERRO] Número inválido")

def listar_por_extensao_cli():
    """Lista imagens por extensão no terminal"""
    print("\n[INFO] Extensões disponíveis:")
    print("1. JPG/JPEG")
    print("2. PNG")
    print("3. GIF")
    print("4. PDF")
    print("5. Todas")

    opcao = input("Escolha a extensão: ").strip()

    ext_map = {
        '1': ('.jpg', '.jpeg'),
        '2': ('.png',),
        '3': ('.gif',),
        '4': ('.pdf',),
        '5': None
    }

    if opcao not in ext_map:
        print("[ERRO] Opção inválida")
        return

    print("\n[INFO] Conectando ao S3...")
    s3 = conectar_s3()

    print(f"[INFO] Listando imagens...")
    imagens = listar_imagens(s3, BUCKET_NAME, IMAGE_PREFIX)

    if ext_map[opcao]:
        extensoes = ext_map[opcao]
        imagens_filtradas = [
            img for img in imagens
            if img['file_name'].lower().endswith(extensoes)
        ]
    else:
        imagens_filtradas = imagens

    if not imagens_filtradas:
        print("[AVISO] Nenhuma imagem encontrada")
        return

    print(f"\n[INFO] {len(imagens_filtradas)} imagens encontradas:\n")

    for i, img in enumerate(imagens_filtradas[:50], 1):
        print(f"{i:3}. {img['file_name']:<50} {img['size_kb']:>8.1f}KB")

    if len(imagens_filtradas) > 50:
        print(f"\n... e mais {len(imagens_filtradas) - 50} imagens")

def baixar_ultimas_n_cli():
    """Baixa as últimas N imagens"""
    quantidade = input("\nQuantas imagens baixar? ").strip()

    try:
        n = int(quantidade)
        if n <= 0:
            raise ValueError
    except:
        print("[ERRO] Quantidade inválida")
        return

    print("\n[INFO] Conectando ao S3...")
    s3 = conectar_s3()

    print(f"[INFO] Buscando últimas {n} imagens...")
    imagens = listar_imagens(s3, BUCKET_NAME, IMAGE_PREFIX)

    if not imagens:
        print("[AVISO] Nenhuma imagem encontrada")
        return

    imagens_selecionadas = imagens[:n]
    print(f"\n[INFO] {len(imagens_selecionadas)} imagens serão baixadas")

    confirma = input("Deseja continuar? (s/n): ").strip().lower()
    if confirma != 's':
        print("[INFO] Operação cancelada")
        return

    LOCAL_IMAGES_DIR.mkdir(exist_ok=True)

    sucesso = 0
    falha = 0

    for i, img in enumerate(imagens_selecionadas, 1):
        destino = LOCAL_IMAGES_DIR / img['file_name']
        print(f"[{i}/{len(imagens_selecionadas)}] Baixando {img['file_name']}...", end=' ')

        try:
            s3.download_file(BUCKET_NAME, img['key'], str(destino))
            print(f"OK ({img['size_kb']:.1f}KB)")
            sucesso += 1
        except Exception as e:
            print(f"ERRO: {e}")
            falha += 1

    print(f"\n[RESUMO] Sucesso: {sucesso} | Falha: {falha}")
    print(f"[INFO] Arquivos salvos em: {LOCAL_IMAGES_DIR}")

if __name__ == '__main__':
    import sys

    print("="*60)
    print("S3 IMAGE DOWNLOADER")
    print(f"Bucket: {BUCKET_NAME}")
    print(f"Pasta: {IMAGE_PREFIX}")
    print("="*60)

    # Verificar se tem argumentos de linha de comando
    if len(sys.argv) > 1:
        if sys.argv[1] == '--api':
            # Modo API
            import uvicorn
            print("\n[MODO API] Iniciando servidor FastAPI...")
            print("API disponível em: http://localhost:8000")
            print("Documentação em: http://localhost:8000/docs")
            print("="*60)
            uvicorn.run(app, host="0.0.0.0", port=8000)
        else:
            print("\nUso:")
            print("  python s3_images_downloader.py       # Modo CLI interativo")
            print("  python s3_images_downloader.py --api # Modo API REST")
    else:
        # Modo CLI por padrão
        print("\n[MODO CLI] Modo interativo de terminal")
        print("Para iniciar o modo API, use: python s3_images_downloader.py --api")
        print("="*60)
        menu_principal_cli()
