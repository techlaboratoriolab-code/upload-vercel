from flask import Flask, request, jsonify, send_from_directory
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
SENHA = os.environ.get('ORIZON_SENHA', '91a2ab8fbdd7884f7e32fd19694712a0')
REGISTRO_ANS = os.environ.get('ORIZON_REGISTRO_ANS', '005711')

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

            logger.info(f"👥 Total de pacientes encontrados: {len(pacientes)}")

            for i, paciente in enumerate(pacientes, 1):
                guia_prestador = paciente.get('numeroGuiaPrestador', '')
                logger.info(f"\n--- Processando paciente {i}/{len(pacientes)} ---")
                logger.info(f"👤 Nome: {paciente.get('nome', 'N/A')}")
                logger.info(f"🔢 Guia Prestador: {guia_prestador}")
                
                # Busca PDF nos arquivos enviados
                pdf_base64 = None
                pdf_encontrado = False
                
                # Tentar encontrar PDF correspondente
                for pdf_name, pdf_data in pdfs.items():
                    if guia_prestador in pdf_name:
                        pdf_base64 = pdf_data
                        pdf_encontrado = True
                        logger.info(f"📎 PDF encontrado: {pdf_name}")
                        break
                
                if not pdf_encontrado:
                    logger.error(f"❌ PDF não encontrado para guia: {guia_prestador}")
                    resultados_finais.append({
                        'paciente': paciente,
                        'status': 'Erro',
                        'error': f'PDF não encontrado para guia {guia_prestador}',
                        'success': False
                    })
                    total_erros += 1
                    continue

                resultado_envio = cliente_orizon.enviar_documento(
                    numero_lote=paciente.get('numeroLote', ''),
                    numero_protocolo=paciente.get('numeroProtocolo', ''),
                    numero_guia_prestador=guia_prestador,
                    numero_guia_operadora=paciente.get('numeroGuiaOperadora', ''),
                    numero_documento=paciente.get('numeroDocumento', ''),
                    pdf_base64=pdf_base64
                )
                
                if resultado_envio.get('success'):
                    total_sucessos += 1
                    logger.info(f"✅ Sucesso no envio da guia {guia_prestador}")
                else:
                    total_erros += 1
                    logger.error(f"❌ Falha no envio da guia {guia_prestador}")
                
                resultados_finais.append({
                    'paciente': paciente,
                    'resultado_envio': resultado_envio,
                    'success': resultado_envio.get('success')
                })
                
                time.sleep(1)

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

if __name__ == '__main__':
    logger.info("🚀 Servidor Flask iniciado")
    app.run(debug=True)

