from flask import Flask, request, jsonify, send_file
import boto3
import os
from datetime import datetime
from pathlib import Path
import time

app = Flask(__name__)

# Configurações AWS S3
from dotenv import load_dotenv
load_dotenv()

AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'sa-east-1')
BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'aplis2')
BUCKET_PREFIX = 'lab/DB/Diario/'
LOCAL_BACKUP_DIR = Path(__file__).parent / 'backups_aws'

# CORS
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

def conectar_s3():
    """Conecta ao S3 usando as credenciais"""
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
        return s3_client
    except Exception as e:
        print(f"❌ Erro ao conectar ao S3: {e}")
        return None

def listar_arquivos_s3(s3_client, bucket_name, prefix):
    """Lista todos os arquivos de uma pasta específica do S3"""
    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix
        )

        if 'Contents' not in response:
            return []

        arquivos = []
        for obj in response['Contents']:
            if not obj['Key'].endswith('/'):
                arquivos.append({
                    'Key': obj['Key'],
                    'Size': obj['Size'],
                    'LastModified': obj['LastModified'].isoformat(),
                    'FileName': obj['Key'].split('/')[-1]
                })

        # Ordenar por data de modificação (mais recente primeiro)
        arquivos.sort(key=lambda x: x['LastModified'], reverse=True)
        return arquivos

    except Exception as e:
        print(f"❌ Erro ao listar arquivos S3: {e}")
        return []

@app.route('/')
def home():
    """Página inicial com interface HTML"""
    html_file = Path(__file__).parent / 's3_interface.html'
    if html_file.exists():
        return send_file(html_file)
    else:
        # Fallback para JSON se o arquivo HTML não existir
        return jsonify({
            'service': 'S3 Backup Web Service',
            'version': '1.0',
            'endpoints': {
                'GET /status': 'Status do serviço',
                'GET /backups': 'Lista todos os backups',
                'GET /backup/latest': 'Retorna o backup mais recente',
                'POST /backup/download': 'Baixa um backup específico'
            },
            'bucket': BUCKET_NAME,
            'prefix': BUCKET_PREFIX
        })

@app.route('/status')
def status():
    """Status do serviço"""
    s3_client = conectar_s3()
    if s3_client:
        return jsonify({
            'status': 'online',
            'message': 'Serviço S3 funcionando',
            'bucket': BUCKET_NAME,
            'region': AWS_REGION
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Erro ao conectar com S3'
        }), 500

@app.route('/backups', methods=['GET'])
def listar_backups():
    """Lista todos os backups disponíveis"""
    try:
        print("📦 Listando backups do S3")

        s3_client = conectar_s3()
        if not s3_client:
            return jsonify({'error': 'Não foi possível conectar ao S3'}), 500

        arquivos = listar_arquivos_s3(s3_client, BUCKET_NAME, BUCKET_PREFIX)

        # Filtrar apenas arquivos .7z
        backups = [arq for arq in arquivos if arq['FileName'].endswith('.7z')]

        print(f"✅ {len(backups)} backups encontrados")

        return jsonify({
            'success': True,
            'total': len(backups),
            'backups': backups,
            'bucket': BUCKET_NAME,
            'prefix': BUCKET_PREFIX
        })

    except Exception as e:
        print(f"❌ Erro ao listar backups: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/backup/latest', methods=['GET'])
def backup_mais_recente():
    """Retorna informações do backup mais recente"""
    try:
        print("🔍 Buscando backup mais recente")

        s3_client = conectar_s3()
        if not s3_client:
            return jsonify({'error': 'Não foi possível conectar ao S3'}), 500

        arquivos = listar_arquivos_s3(s3_client, BUCKET_NAME, BUCKET_PREFIX)

        # Filtrar arquivos que começam com 'lab_' e terminam com '.7z'
        backups = [
            arq for arq in arquivos
            if arq['FileName'].startswith('lab_') and arq['FileName'].endswith('.7z')
        ]

        if not backups:
            return jsonify({'error': 'Nenhum backup encontrado'}), 404

        # O primeiro é o mais recente (já está ordenado)
        backup = backups[0]

        print(f"✅ Backup mais recente: {backup['FileName']}")

        return jsonify({
            'success': True,
            'backup': backup
        })

    except Exception as e:
        print(f"❌ Erro ao buscar backup mais recente: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/backup/download', methods=['POST', 'OPTIONS'])
def baixar_backup():
    """Baixa um backup específico do S3"""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        arquivo_key = data.get('arquivoKey')

        if not arquivo_key:
            return jsonify({'error': 'Chave do arquivo não fornecida'}), 400

        print(f"📥 Iniciando download: {arquivo_key}")

        s3_client = conectar_s3()
        if not s3_client:
            return jsonify({'error': 'Não foi possível conectar ao S3'}), 500

        # Criar pasta local para salvar
        LOCAL_BACKUP_DIR.mkdir(exist_ok=True)

        # Nome do arquivo local
        nome_arquivo = arquivo_key.split('/')[-1]
        arquivo_local = LOCAL_BACKUP_DIR / nome_arquivo

        # Obter tamanho do arquivo
        response = s3_client.head_object(Bucket=BUCKET_NAME, Key=arquivo_key)
        tamanho_total = response['ContentLength']
        tamanho_mb = tamanho_total / (1024 * 1024)

        print(f"📊 Tamanho do arquivo: {tamanho_mb:.2f} MB")

        # Download do arquivo
        inicio = time.time()
        s3_client.download_file(
            BUCKET_NAME,
            arquivo_key,
            str(arquivo_local)
        )
        fim = time.time()

        tempo_decorrido = fim - inicio
        velocidade_mb = tamanho_mb / tempo_decorrido if tempo_decorrido > 0 else 0

        print(f"✅ Download concluído em {tempo_decorrido:.1f}s ({velocidade_mb:.2f} MB/s)")

        return jsonify({
            'success': True,
            'arquivo': nome_arquivo,
            'tamanho_mb': round(tamanho_mb, 2),
            'tempo_segundos': round(tempo_decorrido, 1),
            'velocidade_mb_s': round(velocidade_mb, 2),
            'caminho_local': str(arquivo_local)
        })

    except Exception as e:
        print(f"❌ Erro ao baixar backup: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/backup/download/latest', methods=['POST', 'OPTIONS'])
def baixar_backup_mais_recente():
    """Baixa automaticamente o backup mais recente"""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        print("🚀 Baixando backup mais recente automaticamente")

        # Buscar backup mais recente
        s3_client = conectar_s3()
        if not s3_client:
            return jsonify({'error': 'Não foi possível conectar ao S3'}), 500

        arquivos = listar_arquivos_s3(s3_client, BUCKET_NAME, BUCKET_PREFIX)

        backups = [
            arq for arq in arquivos
            if arq['FileName'].startswith('lab_') and arq['FileName'].endswith('.7z')
        ]

        if not backups:
            return jsonify({'error': 'Nenhum backup encontrado'}), 404

        backup = backups[0]
        arquivo_key = backup['Key']

        print(f"📥 Iniciando download do mais recente: {backup['FileName']}")

        # Criar pasta local
        LOCAL_BACKUP_DIR.mkdir(exist_ok=True)

        # Nome do arquivo local
        nome_arquivo = arquivo_key.split('/')[-1]
        arquivo_local = LOCAL_BACKUP_DIR / nome_arquivo

        # Obter tamanho
        response = s3_client.head_object(Bucket=BUCKET_NAME, Key=arquivo_key)
        tamanho_total = response['ContentLength']
        tamanho_mb = tamanho_total / (1024 * 1024)

        # Download
        inicio = time.time()
        s3_client.download_file(BUCKET_NAME, arquivo_key, str(arquivo_local))
        fim = time.time()

        tempo_decorrido = fim - inicio
        velocidade_mb = tamanho_mb / tempo_decorrido if tempo_decorrido > 0 else 0

        print(f"✅ Download concluído!")

        return jsonify({
            'success': True,
            'arquivo': nome_arquivo,
            'tamanho_mb': round(tamanho_mb, 2),
            'tempo_segundos': round(tempo_decorrido, 1),
            'velocidade_mb_s': round(velocidade_mb, 2),
            'caminho_local': str(arquivo_local),
            'data_modificacao': backup['LastModified']
        })

    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 S3 BACKUP WEB SERVICE")
    print("="*70)
    print(f"📦 Bucket: {BUCKET_NAME}")
    print(f"📂 Pasta: {BUCKET_PREFIX}")
    print(f"🌍 Região: {AWS_REGION}")
    print(f"💾 Destino: {LOCAL_BACKUP_DIR}")
    print("="*70)
    print("📡 Servidor rodando em: http://localhost:8080")
    print("="*70)
    print("\n🔗 Endpoints disponíveis:")
    print("   GET  /status                  - Status do serviço")
    print("   GET  /backups                 - Lista todos os backups")
    print("   GET  /backup/latest           - Info do backup mais recente")
    print("   POST /backup/download         - Baixa um backup específico")
    print("   POST /backup/download/latest  - Baixa o mais recente (automático)")
    print("="*70)
    print("\n✅ Pronto para receber requisições!\n")

    app.run(host='0.0.0.0', port=8080, debug=True)
