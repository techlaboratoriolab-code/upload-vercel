import boto3
import csv
import os
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()

# Configurações AWS S3
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'sa-east-1')
BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'aplis2')
IMAGE_PREFIX = 'lab/Arquivos/Foto/'

# Caminhos
CSV_PATH = r"C:\Users\Windows 11\Downloads\requisicaoimagem_filtrada_final.csv"
DESTINO_IMAGENS = Path(r"C:\Users\Windows 11\Desktop\automação lotes Orizon\imagens s3")
DESTINO_LAUDOS = Path(r"C:\Users\Windows 11\Desktop\automação lotes Orizon\laudos s3")

# ETAPA 1: Mapeamento de prefixos para IMAGENS
PREFIXOS_IMAGENS = {
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

# ETAPA 2: Mapeamento de prefixos para LAUDOS
PREFIXOS_LAUDOS = {
    '0040': 'lab/Arquivos/Historico/0040/',
    '0085': 'lab/Arquivos/Historico/0085/',
    '0100': 'lab/Arquivos/Historico/0100/',
    '0101': 'lab/Arquivos/Historico/0101/',
    '0200': 'lab/Arquivos/Historico/0200/',
    '0031': 'lab/Arquivos/Historico/0031/',
    '0049': 'lab/Arquivos/Historico/0049/',
    '0102': 'lab/Arquivos/Historico/0102/',
    '0103': 'lab/Arquivos/Historico/0103/',
    '0300': 'lab/Arquivos/Historico/0300/',
    '8511': 'lab/Arquivos/Historico/8511/',
    '0032': 'lab/Arquivos/Historico/0032/',
}

def conectar_s3():
    """Conecta ao S3 com configurações otimizadas"""
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION,
        config=boto3.session.Config(
            max_pool_connections=50,  # Aumenta pool de conexões
            retries={'max_attempts': 2}  # Reduz tentativas de retry
        )
    )

def detectar_prefixo(nome_arquivo, prefixos_dict, default_prefix):
    """Detecta o prefixo da pasta baseado no nome do arquivo"""
    for codigo, caminho in prefixos_dict.items():
        if nome_arquivo.startswith(codigo):
            return caminho
    return default_prefix

def buscar_arquivo_s3(s3_client, nome_arquivo, extensao, prefixos_dict, default_prefix):
    """Busca arquivo no S3 pelo nome - OTIMIZADO (funciona para imagens e laudos)"""
    # Detectar pasta
    prefixo_busca = detectar_prefixo(nome_arquivo, prefixos_dict, default_prefix)

    # Nome completo do arquivo
    nome_completo = f"{nome_arquivo}.{extensao.lower()}"

    # OTIMIZAÇÃO 1: Tentar buscar diretamente o arquivo primeiro (mais rápido)
    caminho_direto = f"{prefixo_busca}{nome_completo}"

    try:
        # Tentar HEAD request primeiro (muito mais rápido que listar)
        s3_client.head_object(Bucket=BUCKET_NAME, Key=caminho_direto)
        return caminho_direto
    except:
        # Se não encontrar com o nome exato, tentar case-insensitive
        pass

    # OTIMIZAÇÃO 2: Se não encontrou direto, listar pasta (mas só até encontrar)
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=BUCKET_NAME,
            Prefix=prefixo_busca,
            PaginationConfig={'PageSize': 1000}  # Aumenta tamanho da página
        )

        for page in pages:
            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                key = obj['Key']
                file_name = key.split('/')[-1]

                # Comparar nome (case insensitive)
                if file_name.lower() == nome_completo.lower():
                    return key

        return None
    except Exception as e:
        return None

def baixar_arquivo(s3_client, key, destino):
    """Baixa arquivo do S3"""
    try:
        s3_client.download_file(BUCKET_NAME, key, str(destino))
        return True
    except Exception as e:
        return False

def processar_imagem(linha, s3, total, contadores, lock, erros):
    """Processa uma imagem individualmente (usado em paralelo)"""
    nome_arquivo = linha['NomArquivo'].strip()
    extensao = linha['ExtArquivo'].strip()

    nome_completo = f"{nome_arquivo}.{extensao.lower()}"
    destino = DESTINO_IMAGENS / nome_completo

    # Verificar se já existe
    if destino.exists():
        with lock:
            contadores['ja_existe'] += 1
            contadores['processados'] += 1
            print(f"[IMAGEM {contadores['processados']}/{total}] {nome_completo:<40} JÁ EXISTE")
        return

    # Buscar no S3
    key = buscar_arquivo_s3(s3, nome_arquivo, extensao, PREFIXOS_IMAGENS, IMAGE_PREFIX)

    if not key:
        with lock:
            contadores['nao_encontrado'] += 1
            contadores['processados'] += 1
            erros.append(f"IMAGEM: {nome_completo} - Não encontrado no S3")
            print(f"[IMAGEM {contadores['processados']}/{total}] {nome_completo:<40} NÃO ENCONTRADO")
        return

    # Baixar
    if baixar_arquivo(s3, key, destino):
        tamanho_kb = destino.stat().st_size / 1024
        with lock:
            contadores['sucesso'] += 1
            contadores['processados'] += 1
            print(f"[IMAGEM {contadores['processados']}/{total}] {nome_completo:<40} OK ({tamanho_kb:.1f}KB)")
    else:
        with lock:
            contadores['falha'] += 1
            contadores['processados'] += 1
            erros.append(f"IMAGEM: {nome_completo} - Erro ao baixar")
            print(f"[IMAGEM {contadores['processados']}/{total}] {nome_completo:<40} ERRO AO BAIXAR")

def processar_laudo(linha, s3, total, contadores, lock, erros):
    """Processa um laudo individualmente (usado em paralelo)"""
    nome_arquivo = linha['CodRequisicao_extraido'].strip()

    # Se CodRequisicao_extraido está vazio, pular
    if not nome_arquivo:
        with lock:
            contadores['sem_laudo'] += 1
            contadores['processados'] += 1
            print(f"[LAUDO {contadores['processados']}/{total}] {'(vazio)':<40} PULADO - SEM LAUDO")
        return

    # Pegar o código da empresa (primeiros 4 dígitos do CodRequisicao_extraido)
    # Ex: "0200045916001" -> código é "0200"
    codigo_empresa = nome_arquivo[:4] if len(nome_arquivo) >= 4 else ""

    # Arquivos no S3 TÊM extensão .pdf
    # Ex: buscar "0200045916001.pdf"
    nome_completo = f"{nome_arquivo}.pdf"
    destino = DESTINO_LAUDOS / nome_completo

    # Verificar se já existe
    if destino.exists():
        with lock:
            contadores['ja_existe'] += 1
            contadores['processados'] += 1
            print(f"[LAUDO {contadores['processados']}/{total}] {nome_completo:<40} JÁ EXISTE")
        return

    # Buscar no S3 - usar código da empresa, não o nome do arquivo
    # Construir o prefixo correto baseado no código
    if codigo_empresa in PREFIXOS_LAUDOS:
        prefixo_laudo = PREFIXOS_LAUDOS[codigo_empresa]
    else:
        prefixo_laudo = 'lab/Arquivos/Historico/'

    # Buscar diretamente (já temos o correto)
    caminho_direto = f"{prefixo_laudo}{nome_completo}"

    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=caminho_direto)
        key = caminho_direto
    except:
        # Se não encontrou direto, tentar buscar na pasta
        key = None
        try:
            paginator = s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=BUCKET_NAME,
                Prefix=prefixo_laudo,
                PaginationConfig={'PageSize': 1000}
            )

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    obj_key = obj['Key']
                    file_name = obj_key.split('/')[-1]

                    if file_name.lower() == nome_completo.lower():
                        key = obj_key
                        break

                if key:
                    break
        except:
            key = None

    if not key:
        with lock:
            contadores['nao_encontrado'] += 1
            contadores['processados'] += 1
            erros.append(f"LAUDO: {nome_completo} - Não encontrado no S3")
            print(f"[LAUDO {contadores['processados']}/{total}] {nome_completo:<40} NÃO ENCONTRADO")
        return

    # Baixar
    if baixar_arquivo(s3, key, destino):
        tamanho_kb = destino.stat().st_size / 1024
        with lock:
            contadores['sucesso'] += 1
            contadores['processados'] += 1
            print(f"[LAUDO {contadores['processados']}/{total}] {nome_completo:<40} OK ({tamanho_kb:.1f}KB)")
    else:
        with lock:
            contadores['falha'] += 1
            contadores['processados'] += 1
            erros.append(f"LAUDO: {nome_completo} - Erro ao baixar")
            print(f"[LAUDO {contadores['processados']}/{total}] {nome_completo:<40} ERRO AO BAIXAR")

def processar_csv():
    """Processa o CSV e baixa IMAGENS e LAUDOS em 2 etapas"""
    print("="*80)
    print("DOWNLOAD AUTOMÁTICO - IMAGENS E LAUDOS DO S3")
    print("="*80)
    print(f"CSV: {CSV_PATH}")
    print(f"Destino Imagens: {DESTINO_IMAGENS}")
    print(f"Destino Laudos: {DESTINO_LAUDOS}")
    print("="*80)

    # Criar pastas de destino
    DESTINO_IMAGENS.mkdir(exist_ok=True)
    DESTINO_LAUDOS.mkdir(exist_ok=True)

    # Ler CSV
    print(f"\n[INFO] Lendo CSV...")
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        linhas = list(reader)

    total = len(linhas)
    print(f"[INFO] Total de registros: {total}")
    print(f"[INFO] Usando 20 threads paralelas para download ultra-rápido")

    inicio_geral = datetime.now()
    erros = []

    # ============================================================
    # ETAPA 1: BAIXAR IMAGENS
    # ============================================================
    print("\n" + "="*80)
    print("ETAPA 1/2: BAIXANDO IMAGENS")
    print("="*80)

    contadores_imagens = {
        'sucesso': 0,
        'falha': 0,
        'nao_encontrado': 0,
        'ja_existe': 0,
        'processados': 0
    }
    lock = Lock()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for linha in linhas:
            s3 = conectar_s3()
            future = executor.submit(processar_imagem, linha, s3, total, contadores_imagens, lock, erros)
            futures.append(future)

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                with lock:
                    contadores_imagens['falha'] += 1
                    erros.append(f"IMAGEM - Erro inesperado: {str(e)}")

    tempo_imagens = (datetime.now() - inicio_geral).total_seconds()

    print("\n" + "="*80)
    print("RESUMO ETAPA 1 - IMAGENS")
    print("="*80)
    print(f"Sucesso:          {contadores_imagens['sucesso']}")
    print(f"Já existiam:      {contadores_imagens['ja_existe']}")
    print(f"Não encontrados:  {contadores_imagens['nao_encontrado']}")
    print(f"Falhas:           {contadores_imagens['falha']}")
    print(f"Tempo:            {tempo_imagens:.1f}s")
    print("="*80)

    # ============================================================
    # ETAPA 2: BAIXAR LAUDOS
    # ============================================================
    print("\n" + "="*80)
    print("ETAPA 2/2: BAIXANDO LAUDOS")
    print("="*80)

    contadores_laudos = {
        'sucesso': 0,
        'falha': 0,
        'nao_encontrado': 0,
        'ja_existe': 0,
        'processados': 0,
        'sem_laudo': 0
    }

    inicio_laudos = datetime.now()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for linha in linhas:
            s3 = conectar_s3()
            future = executor.submit(processar_laudo, linha, s3, total, contadores_laudos, lock, erros)
            futures.append(future)

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                with lock:
                    contadores_laudos['falha'] += 1
                    erros.append(f"LAUDO - Erro inesperado: {str(e)}")

    tempo_laudos = (datetime.now() - inicio_laudos).total_seconds()

    print("\n" + "="*80)
    print("RESUMO ETAPA 2 - LAUDOS")
    print("="*80)
    print(f"Sucesso:          {contadores_laudos['sucesso']}")
    print(f"Já existiam:      {contadores_laudos['ja_existe']}")
    print(f"Sem laudo:        {contadores_laudos['sem_laudo']}")
    print(f"Não encontrados:  {contadores_laudos['nao_encontrado']}")
    print(f"Falhas:           {contadores_laudos['falha']}")
    print(f"Tempo:            {tempo_laudos:.1f}s")
    print("="*80)

    # ============================================================
    # RESUMO FINAL
    # ============================================================
    tempo_total = (datetime.now() - inicio_geral).total_seconds()

    print("\n" + "="*80)
    print("RESUMO FINAL - IMAGENS + LAUDOS")
    print("="*80)
    print(f"Total registros:     {total}")
    print(f"")
    print(f"IMAGENS:")
    print(f"  ✓ Sucesso:         {contadores_imagens['sucesso']}")
    print(f"  ⊙ Já existiam:     {contadores_imagens['ja_existe']}")
    print(f"  ✗ Não encontrados: {contadores_imagens['nao_encontrado']}")
    print(f"  ✗ Falhas:          {contadores_imagens['falha']}")
    print(f"")
    print(f"LAUDOS:")
    print(f"  ✓ Sucesso:         {contadores_laudos['sucesso']}")
    print(f"  ⊙ Já existiam:     {contadores_laudos['ja_existe']}")
    print(f"  - Sem laudo:       {contadores_laudos['sem_laudo']}")
    print(f"  ✗ Não encontrados: {contadores_laudos['nao_encontrado']}")
    print(f"  ✗ Falhas:          {contadores_laudos['falha']}")
    print(f"")
    print(f"Tempo total:         {tempo_total:.1f}s")
    print(f"Velocidade média:    {(total * 2) / tempo_total:.1f} arquivos/segundo")
    print("="*80)

    # Salvar log de erros
    if erros:
        log_path = DESTINO_IMAGENS.parent / 'erros_download.txt'
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"LOG DE ERROS - {datetime.now()}\n")
            f.write("="*80 + "\n\n")
            for erro in erros:
                f.write(f"{erro}\n")
        print(f"\n[INFO] Log de erros salvo em: {log_path}")

    print(f"\n[INFO] Imagens salvas em: {DESTINO_IMAGENS}")
    print(f"[INFO] Laudos salvos em:  {DESTINO_LAUDOS}")

if __name__ == '__main__':
    try:
        processar_csv()
    except KeyboardInterrupt:
        print("\n\n[INFO] Operação cancelada pelo usuário")
    except Exception as e:
        print(f"\n[ERRO CRÍTICO] {e}")
        import traceback
        traceback.print_exc()
