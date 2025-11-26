from flask import Flask, request, jsonify, send_from_directory, send_file
import os
import io
import base64
import hashlib
import re
from datetime import datetime
from xml.etree import ElementTree as ET
import requests
import time
import logging
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()

app = Flask(__name__)

# Configuração de logs simplificada para Vercel
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORS headers
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

class OrizonTISSEnvio:
    def __init__(self, codigo_prestador, login, senha, registro_ans="005711"):
        self.url = "https://tiss-documentos.orizon.com.br/Service.asmx"
        self.codigo_prestador = codigo_prestador
        self.login = login
        
        # Validação da senha (MD5)
        senha_str = (senha or "").strip()
        if re.fullmatch(r"[A-Fa-f0-9]{32}", senha_str):
            self.senha_md5 = senha_str.lower()
        else:
            self.senha_md5 = hashlib.md5(senha_str.encode("utf-8")).hexdigest().lower()
        
        self.registro_ans = registro_ans
        logger.info(f"OrizonTISSEnvio inicializado - Prestador: {codigo_prestador}, Login: {login}")
        
    def criar_xml_envio(self, numero_lote, numero_protocolo, numero_guia_prestador, 
                        numero_guia_operadora, numero_documento, pdf_base64, 
                        natureza_guia="2", tipo_documento="01", observacao=""):
        agora = datetime.now()
        data_registro = agora.strftime("%Y-%m-%d")
        hora_registro = agora.strftime("%H:%M:%S")
        
        logger.info(f"Criando XML de envio - Lote: {numero_lote}, Guia Prestador: {numero_guia_prestador}")
        
        xml_str = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:ans="http://www.ans.gov.br/padroes/tiss/schemas"
xmlns:xd="http://www.w3.org/2000/09/xmldsig#">
<soapenv:Header/>
<soapenv:Body>
<ans:envioDocumentoWS>
<ans:cabecalho>
<ans:identificacaoTransacao>
<ans:tipoTransacao>ENVIO_DOCUMENTO</ans:tipoTransacao>
<ans:sequencialTransacao>1</ans:sequencialTransacao>
<ans:dataRegistroTransacao>{data_registro}</ans:dataRegistroTransacao>
<ans:horaRegistroTransacao>{hora_registro}</ans:horaRegistroTransacao>
</ans:identificacaoTransacao>
<ans:origem>
<ans:identificacaoPrestador>
<ans:codigoPrestadorNaOperadora>{self.codigo_prestador}</ans:codigoPrestadorNaOperadora>
</ans:identificacaoPrestador>
</ans:origem>
<ans:destino>
<ans:registroANS>{self.registro_ans}</ans:registroANS>
</ans:destino>
<ans:Padrao>4.01.00</ans:Padrao>
<ans:loginSenhaPrestador>
<ans:loginPrestador>{self.login}</ans:loginPrestador>
<ans:senhaPrestador>{self.senha_md5}</ans:senhaPrestador>
</ans:loginSenhaPrestador>
</ans:cabecalho>
<ans:envioDOcumento>
<ans:numeroLote>{numero_lote}</ans:numeroLote>
<ans:numeroProtocolo>{numero_protocolo}</ans:numeroProtocolo>
<ans:numeroGuiaPrestador>{numero_guia_prestador}</ans:numeroGuiaPrestador>
<ans:numeroGuiaOperadora>{numero_guia_operadora}</ans:numeroGuiaOperadora>
<ans:numeroDocumento>{numero_documento}</ans:numeroDocumento>
<ans:naturezaGuia>{natureza_guia}</ans:naturezaGuia>
<ans:formatoDocumento>02</ans:formatoDocumento>
<ans:documento>{pdf_base64}</ans:documento>
<ans:tipoDocumento>{tipo_documento}</ans:tipoDocumento>
<ans:observacao>{observacao}</ans:observacao>
</ans:envioDOcumento>
<ans:hash>2</ans:hash>
</ans:envioDocumentoWS>
</soapenv:Body>
</soapenv:Envelope>"""
        
        return xml_str
    
    def enviar_documento(self, numero_lote, numero_protocolo, numero_guia_prestador,
                        numero_guia_operadora, numero_documento, pdf_base64,
                        natureza_guia="2", tipo_documento="01", observacao="", max_tentativas=3):
        
        logger.info(f"Iniciando envio - Guia: {numero_guia_prestador}, Documento: {numero_documento}")
        
        xml_string = self.criar_xml_envio(
            numero_lote=numero_lote,
            numero_protocolo=numero_protocolo,
            numero_guia_prestador=numero_guia_prestador,
            numero_guia_operadora=numero_guia_operadora,
            numero_documento=numero_documento,
            pdf_base64=pdf_base64,
            natureza_guia=natureza_guia,
            tipo_documento=tipo_documento,
            observacao=observacao
        )

        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'http://www.ans.gov.br/padroes/tiss/schemas/envioDocumentoWS'
        }

        ultimo_erro = None
        for tentativa in range(1, max_tentativas + 1):
            try:
                if tentativa > 1:
                    logger.warning(f"Tentativa {tentativa} de {max_tentativas} - Guia: {numero_guia_prestador}")
                    time.sleep(2)

                response = requests.post(
                    self.url,
                    data=xml_string.encode('utf-8'),
                    headers=headers,
                    timeout=120
                )

                if response.status_code == 200:
                    logger.info(f"✅ Envio bem-sucedido - Guia: {numero_guia_prestador}, Status: {response.status_code}")
                else:
                    logger.error(f"❌ Erro no envio - Guia: {numero_guia_prestador}, Status: {response.status_code}")

                return {
                    'success': response.status_code == 200,
                    'status_code': response.status_code,
                    'response': response.text,
                    'tentativas': tentativa
                }

            except Exception as e:
                ultimo_erro = str(e)[:100]
                logger.error(f"Erro na tentativa {tentativa} - Guia: {numero_guia_prestador} - {ultimo_erro}")
                continue

        logger.error(f"❌ Falha após {max_tentativas} tentativas - Guia: {numero_guia_prestador}")
        return {
            'success': False,
            'error': f'Falhou após {max_tentativas} tentativas. Último erro: {ultimo_erro}',
            'tentativas': max_tentativas
        }


class ProcessadorXMLTISS:
    def __init__(self, xml_content):
        self.xml_content = xml_content
        self.pacientes = []
        
    def extrair_pacientes(self):
        try:
            root = ET.fromstring(self.xml_content)
            logger.info("XML parseado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao parsear XML: {str(e)}")
            return {'error': f'Erro ao processar XML: {str(e)}'}
        
        numero_lote = self._extrair_texto(root, './/numeroLote')
        logger.info(f"Número do lote extraído: {numero_lote}")
        
        guias_encontradas = []
        elementos_processados = set()
        
        for elem in root.iter():
            tag_limpa = elem.tag.split('}')[1] if '}' in elem.tag else elem.tag
            tag_lower = tag_limpa.lower()
            
            if 'guia' in tag_lower and id(elem) not in elementos_processados:
                tem_dados = False
                for child in elem.iter():
                    child_tag = (child.tag.split('}')[1] if '}' in child.tag else child.tag).lower()
                    if any(x in child_tag for x in ['numeroguia', 'numerocarteira', 'carteirinha']) and child.text and child.text.strip():
                        tem_dados = True
                        break
                
                if tem_dados:
                    guias_encontradas.append(elem)
                    elementos_processados.add(id(elem))
        
        logger.info(f"Total de guias encontradas: {len(guias_encontradas)}")
        
        for i, guia in enumerate(guias_encontradas, 1):
            paciente = self._extrair_dados_guia(guia, numero_lote)
            if paciente:
                logger.info(f"Paciente {i} extraído - Guia: {paciente.get('numeroGuiaPrestador', 'N/A')}, Nome: {paciente.get('nome', 'N/A')}")
                self.pacientes.append(paciente)
        
        return self.pacientes
    
    def _extrair_texto(self, elemento, xpath):
        def remover_namespace(tag):
            if '}' in tag:
                return tag.split('}')[1]
            return tag
        
        for elem in elemento.iter():
            tag = remover_namespace(elem.tag).lower()
            xpath_limpo = xpath.replace('.//', '').replace('./', '').lower()
            if tag == xpath_limpo and elem.text:
                return elem.text.strip()
        return None
    
    def _extrair_dados_guia(self, guia, numero_lote):
        def remover_namespace(tag):
            if '}' in tag:
                return tag.split('}')[1]
            return tag
        
        paciente = {'numeroLote': numero_lote}
        
        for elem in guia.iter():
            tag = remover_namespace(elem.tag).lower()
            texto = elem.text.strip() if elem.text and elem.text.strip() else None
            
            if not texto:
                continue
            
            if 'numeroguiaprestador' in tag:
                paciente['numeroGuiaPrestador'] = texto
            elif 'numeroguiaoperadora' in tag:
                paciente['numeroGuiaOperadora'] = texto
            elif 'numeroguia' in tag and 'numeroGuiaPrestador' not in paciente:
                paciente['numeroGuiaPrestador'] = texto
            elif 'numerocarteira' in tag or 'carteirinha' in tag:
                paciente['carteirinha'] = texto
                paciente['numeroCarteira'] = texto
            elif 'numeroprotocolo' in tag or 'protocolo' in tag:
                paciente['numeroProtocolo'] = texto
            elif 'nomebeneficiario' in tag:
                paciente['nome'] = texto
            elif 'numerodocumento' in tag:
                paciente['numeroDocumento'] = texto
        
        if not paciente.get('numeroDocumento'):
            if paciente.get('numeroGuiaPrestador'):
                paciente['numeroDocumento'] = f"{paciente['numeroGuiaPrestador']}001"
        
        if paciente.get('numeroGuiaPrestador') or paciente.get('numeroGuiaOperadora'):
            return paciente
        
        return None


CODIGO_PRESTADOR = os.environ.get('ORIZON_CODIGO_PRESTADOR', '0000263036')
LOGIN = os.environ.get('ORIZON_LOGIN', 'LAB0186')
SENHA = os.getenv('ORIZON_SENHA')
REGISTRO_ANS = os.getenv('ORIZON_REGISTRO_ANS')

# Configurações AWS S3
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'sa-east-1')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'aplis2')
S3_BUCKET_PREFIX = os.environ.get('S3_BUCKET_PREFIX', 'lab/DB/Diario/')

def conectar_s3():
    """Conecta ao S3 usando as credenciais configuradas"""
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
        return s3_client
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao S3: {e}")
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
        logger.error(f"❌ Erro ao listar arquivos S3: {e}")
        return []

@app.route('/', methods=['GET'])
def home():
    # Para Vercel, servir o index.html da raiz
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>', methods=['GET'])
def serve_static(path):
    # Servir arquivos estáticos (Script.js, etc)
    if os.path.exists(path):
        return send_from_directory('.', path)
    return "File not found", 404

@app.route('/api/analisar-xml', methods=['POST', 'OPTIONS'])
def analisar_xml():
    """Analisa o XML e retorna todos os pacientes encontrados sem processar"""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        logger.info("🔍 ANALISANDO XML PARA EXTRAIR PACIENTES")

        data = request.get_json()
        xml_content = data.get('xmlContent', '')

        if not xml_content:
            return jsonify({'error': 'Nenhum conteúdo XML enviado'}), 400

        processador = ProcessadorXMLTISS(xml_content)
        pacientes = processador.extrair_pacientes()

        if isinstance(pacientes, dict) and 'error' in pacientes:
            logger.error(f"❌ Erro ao analisar XML: {pacientes['error']}")
            return jsonify(pacientes), 400

        logger.info(f"✅ {len(pacientes)} pacientes encontrados no XML")

        return jsonify({
            'success': True,
            'total': len(pacientes),
            'pacientes': pacientes
        })

    except Exception as e:
        logger.error(f"❌ ERRO ao analisar XML: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/enviar', methods=['POST', 'OPTIONS'])
def enviar_xml():
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        logger.info("🚀 INICIANDO NOVO PROCESSAMENTO")
        
        data = request.get_json()
        xml_files = data.get('xmlFiles', [])
        pdfs = data.get('pdfs', {})
        
        if not xml_files:
            logger.error("❌ Nenhum arquivo XML enviado")
            return jsonify({'error': 'Nenhum arquivo XML enviado'}), 400

        logger.info(f"📂 Total de XMLs recebidos: {len(xml_files)}")
        logger.info(f"📎 Total de PDFs recebidos: {len(pdfs)}")

        cliente_orizon = OrizonTISSEnvio(CODIGO_PRESTADOR, LOGIN, SENHA, REGISTRO_ANS)
        resultados_finais = []
        total_sucessos = 0
        total_erros = 0

        for idx, xml_data in enumerate(xml_files, 1):
            logger.info(f"\n📄 Processando XML {idx}/{len(xml_files)}: {xml_data.get('name', 'sem nome')}")
            
            xml_content = xml_data.get('content', '')
            processador = ProcessadorXMLTISS(xml_content)
            pacientes = processador.extrair_pacientes()

            if isinstance(pacientes, dict) and 'error' in pacientes:
                logger.error(f"❌ Erro no XML: {pacientes['error']}")
                resultados_finais.append({
                    'arquivo_xml': xml_data.get('name', 'desconhecido'),
                    'error': pacientes['error']
                })
                total_erros += 1
                continue

            logger.info(f"👥 Total de pacientes no XML: {len(pacientes)}")
            logger.info(f"📎 Total de PDFs neste lote: {len(pdfs)}")
            logger.info("")

            # Processar apenas pacientes que têm PDF no lote atual
            pacientes_processados = 0
            for pdf_name, pdf_data in pdfs.items():
                # Extrair número da guia do nome do PDF (ex: 357609997_GUIA_doc1.pdf -> 357609997)
                numero_guia_pdf = pdf_name.split('_')[0].strip()

                logger.info("=" * 70)
                logger.info(f"📦 LOTE [{pacientes_processados + 1}/{len(pdfs)}]")
                logger.info(f"   📄 PDF: {pdf_name}")
                logger.info("")

                # Buscar paciente correspondente
                paciente_encontrado = None
                for paciente in pacientes:
                    guia_prestador = str(paciente.get('numeroGuiaPrestador', '')).strip()
                    guia_operadora = str(paciente.get('numeroGuiaOperadora', '')).strip()

                    # Tentar match com número da guia do prestador ou operadora
                    if (numero_guia_pdf == guia_prestador or
                        numero_guia_pdf == guia_operadora or
                        numero_guia_pdf in guia_prestador or
                        numero_guia_pdf in guia_operadora or
                        guia_prestador.endswith(numero_guia_pdf) or
                        guia_operadora.endswith(numero_guia_pdf)):
                        paciente_encontrado = paciente
                        break

                if not paciente_encontrado:
                    logger.error(f"❌ ERRO: Paciente NÃO encontrado no XML")
                    logger.error(f"   PDF: {pdf_name}")
                    logger.error(f"   Número procurado: {numero_guia_pdf}")
                    logger.error(f"   Motivo: Não existe guia com esse número no XML")
                    resultados_finais.append({
                        'pdf': pdf_name,
                        'status': 'Erro',
                        'error': f'Paciente não encontrado no XML para PDF {pdf_name}',
                        'success': False
                    })
                    total_erros += 1
                    continue

                pacientes_processados += 1
                guia_prestador = paciente_encontrado.get('numeroGuiaPrestador', '')

                logger.info(f"📋 Carteirinha: {paciente_encontrado.get('numeroCarteira', 'N/A')}")
                logger.info(f"📝 Guia: {guia_prestador}")
                logger.info(f"📄 PDF: {pdf_name}")
                logger.info(f"📤 Enviando...")

                resultado_envio = cliente_orizon.enviar_documento(
                    numero_lote=paciente_encontrado.get('numeroLote', ''),
                    numero_protocolo=paciente_encontrado.get('numeroProtocolo', ''),
                    numero_guia_prestador=guia_prestador,
                    numero_guia_operadora=paciente_encontrado.get('numeroGuiaOperadora', ''),
                    numero_documento=paciente_encontrado.get('numeroDocumento', ''),
                    pdf_base64=pdf_data
                )

                if resultado_envio.get('success'):
                    total_sucessos += 1
                    logger.info(f"✅ Enviado com sucesso!")
                else:
                    total_erros += 1
                    logger.error(f"❌ Falha: {resultado_envio.get('error', 'Erro desconhecido')}")

                logger.info("=" * 70)
                logger.info("")

                resultados_finais.append({
                    'paciente': paciente_encontrado,
                    'pdf_name': pdf_name,
                    'resultado_envio': resultado_envio,
                    'success': resultado_envio.get('success')
                })

        logger.info(f"📊 RESUMO FINAL - ✅ Sucessos: {total_sucessos} | ❌ Erros: {total_erros}")

        return jsonify({
            'success': True,
            'resultados': resultados_finais,
            'resumo': {
                'total': len(resultados_finais),
                'sucessos': total_sucessos,
                'erros': total_erros
            }
        })
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/s3/listar-backups', methods=['GET', 'OPTIONS'])
def listar_backups_s3():
    """Lista todos os backups disponíveis no S3"""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        logger.info("📦 Listando backups do S3")

        s3_client = conectar_s3()
        if not s3_client:
            return jsonify({'error': 'Não foi possível conectar ao S3'}), 500

        arquivos = listar_arquivos_s3(s3_client, S3_BUCKET_NAME, S3_BUCKET_PREFIX)

        # Filtrar apenas arquivos .7z
        backups = [arq for arq in arquivos if arq['FileName'].endswith('.7z')]

        logger.info(f"✅ {len(backups)} backups encontrados")

        return jsonify({
            'success': True,
            'total': len(backups),
            'backups': backups,
            'bucket': S3_BUCKET_NAME,
            'prefix': S3_BUCKET_PREFIX
        })

    except Exception as e:
        logger.error(f"❌ Erro ao listar backups: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/s3/baixar-backup', methods=['POST', 'OPTIONS'])
def baixar_backup_s3():
    """Baixa um backup específico do S3"""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        arquivo_key = data.get('arquivoKey')

        if not arquivo_key:
            return jsonify({'error': 'Chave do arquivo não fornecida'}), 400

        logger.info(f"📥 Iniciando download: {arquivo_key}")

        s3_client = conectar_s3()
        if not s3_client:
            return jsonify({'error': 'Não foi possível conectar ao S3'}), 500

        # Criar pasta local para salvar
        backup_dir = Path(__file__).parent / 'backups_aws'
        backup_dir.mkdir(exist_ok=True)

        # Nome do arquivo local
        nome_arquivo = arquivo_key.split('/')[-1]
        arquivo_local = backup_dir / nome_arquivo

        # Obter tamanho do arquivo
        response = s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=arquivo_key)
        tamanho_total = response['ContentLength']
        tamanho_mb = tamanho_total / (1024 * 1024)

        logger.info(f"📊 Tamanho do arquivo: {tamanho_mb:.2f} MB")

        # Download do arquivo
        inicio = time.time()
        s3_client.download_file(
            S3_BUCKET_NAME,
            arquivo_key,
            str(arquivo_local)
        )
        fim = time.time()

        tempo_decorrido = fim - inicio
        velocidade_mb = tamanho_mb / tempo_decorrido if tempo_decorrido > 0 else 0

        logger.info(f"✅ Download concluído em {tempo_decorrido:.1f}s ({velocidade_mb:.2f} MB/s)")

        return jsonify({
            'success': True,
            'arquivo': nome_arquivo,
            'tamanho_mb': round(tamanho_mb, 2),
            'tempo_segundos': round(tempo_decorrido, 1),
            'velocidade_mb_s': round(velocidade_mb, 2),
            'caminho_local': str(arquivo_local)
        })

    except Exception as e:
        logger.error(f"❌ Erro ao baixar backup: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/s3/backup-mais-recente', methods=['GET', 'OPTIONS'])
def backup_mais_recente():
    """Retorna informações do backup mais recente"""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        logger.info("🔍 Buscando backup mais recente")

        s3_client = conectar_s3()
        if not s3_client:
            return jsonify({'error': 'Não foi possível conectar ao S3'}), 500

        arquivos = listar_arquivos_s3(s3_client, S3_BUCKET_NAME, S3_BUCKET_PREFIX)

        # Filtrar arquivos que começam com 'lab_' e terminam com '.7z'
        backups = [
            arq for arq in arquivos
            if arq['FileName'].startswith('lab_') and arq['FileName'].endswith('.7z')
        ]

        if not backups:
            return jsonify({'error': 'Nenhum backup encontrado'}), 404

        # O primeiro é o mais recente (já está ordenado)
        backup_mais_recente = backups[0]

        logger.info(f"✅ Backup mais recente: {backup_mais_recente['FileName']}")

        return jsonify({
            'success': True,
            'backup': backup_mais_recente
        })

    except Exception as e:
        logger.error(f"❌ Erro ao buscar backup mais recente: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 Servidor Flask iniciado")
    app.run(debug=True)

