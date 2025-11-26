import boto3
import sys
import os
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()

# Configurações AWS S3
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'sa-east-1')
BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'aplis2')
IMAGE_PREFIX = 'lab/Arquivos/Foto/'

# Mapeamento de prefixos para busca otimizada
PREFIXOS_CONHECIDOS = {
    '0200': 'lab/Arquivos/Foto/0200/',
    '0031': 'lab/Arquivos/Foto/0031/',
    '0032': 'lab/Arquivos/Foto/0032/',
    '0040': 'lab/Arquivos/Foto/0040/',
    '0049': 'lab/Arquivos/Foto/0049/',
    '0085': 'lab/Arquivos/Foto/0085/',
    '0100': 'lab/Arquivos/Foto/0100/',
    '0101': 'lab/Arquivos/Foto/0101/',
    '0102': 'lab/Arquivos/Foto/0102/',
    '0103': 'lab/Arquivos/Foto/0103/',
    '0300': 'lab/Arquivos/Foto/0300/',
    '8511': 'lab/Arquivos/Foto/8511/',
}

def buscar_e_baixar(nome):
    """Busca e baixa uma imagem do S3"""
    print(f"\n[INFO] Buscando imagem: {nome}")

    # Conectar ao S3
    s3 = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION
    )

    # Detectar prefixo para busca otimizada
    prefixo_busca = IMAGE_PREFIX
    pasta_detectada = None

    # Verificar se o nome começa com algum dos prefixos conhecidos
    for codigo, caminho in PREFIXOS_CONHECIDOS.items():
        if nome.startswith(codigo):
            prefixo_busca = caminho
            pasta_detectada = codigo
            print(f"[OTIMIZADO] Detectado prefixo {codigo}, buscando direto na pasta correta")
            break

    if not pasta_detectada:
        print("[INFO] Buscando em todas as pastas...")

    print("[INFO] Conectando ao S3...")

    try:
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefixo_busca)

        encontradas = []

        for page in pages:
            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                key = obj['Key']
                file_name = key.split('/')[-1]

                # Buscar o nome na chave ou no nome do arquivo
                if nome.lower() in file_name.lower():
                    encontradas.append({
                        'key': key,
                        'nome': file_name,
                        'tamanho': round(obj['Size'] / 1024, 1)
                    })

        if not encontradas:
            print(f"[ERRO] Nenhuma imagem encontrada com '{nome}'")
            return

        print(f"\n[ENCONTRADO] {len(encontradas)} imagem(ns):\n")

        for i, img in enumerate(encontradas, 1):
            print(f"{i}. {img['nome']} ({img['tamanho']}KB)")
            print(f"   Key: {img['key']}")

        # Se encontrou apenas 1, baixa automaticamente
        if len(encontradas) == 1:
            img = encontradas[0]
            destino = img['nome']

            print(f"\n[INFO] Baixando {destino}...")
            s3.download_file(BUCKET_NAME, img['key'], destino)
            print(f"[OK] Salvo em: {destino}")
        else:
            # Se encontrou mais de 1, pede para escolher
            escolha = input(f"\nDigite o número da imagem (1-{len(encontradas)}) ou Enter para cancelar: ").strip()

            if escolha:
                try:
                    num = int(escolha)
                    if 1 <= num <= len(encontradas):
                        img = encontradas[num - 1]
                        destino = img['nome']

                        print(f"\n[INFO] Baixando {destino}...")
                        s3.download_file(BUCKET_NAME, img['key'], destino)
                        print(f"[OK] Salvo em: {destino}")
                    else:
                        print("[ERRO] Número inválido")
                except:
                    print("[ERRO] Entrada inválida")

    except Exception as e:
        print(f"[ERRO] {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python buscar_imagem.py <nome_da_imagem>")
        print("\nExemplo:")
        print("  python buscar_imagem.py 0031000008000_1")
        print("  python buscar_imagem.py foto123")
        sys.exit(1)

    nome_busca = sys.argv[1]
    buscar_e_baixar(nome_busca)
