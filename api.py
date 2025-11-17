from flask import Flask, request, jsonify
import os
import io
import base64
import hashlib
import re
from datetime import datetime
from xml.etree import ElementTree as ET
import requests
import time

app = Flask(__name__, static_folder='static', static_url_path='')

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
        
    def criar_xml_envio(self, numero_lote, numero_protocolo, numero_guia_prestador, 
                        numero_guia_operadora, numero_documento, pdf_base64, 
                        natureza_guia="2", tipo_documento="01", observacao=""):
        agora = datetime.now()
        data_registro = agora.strftime("%Y-%m-%d")
        hora_registro = agora.strftime("%H:%M:%S")
        
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
                    time.sleep(2)

                response = requests.post(
                    self.url,
                    data=xml_string.encode('utf-8'),
                    headers=headers,
                    timeout=120
                )

                return {
                    'success': response.status_code == 200,
                    'status_code': response.status_code,
                    'response': response.text,
                    'tentativas': tentativa
                }

            except Exception as e:
                ultimo_erro = str(e)[:100]
                continue

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
        except Exception as e:
            return {'error': f'Erro ao processar XML: {str(e)}'}
        
        numero_lote = self._extrair_texto(root, './/numeroLote')
        
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
        
        for guia in guias_encontradas:
            paciente = self._extrair_dados_guia(guia, numero_lote)
            if paciente:
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
    return app.send_static_file('index.html') # Busca em 'static/index.html'

@app.route('/api/process', methods=['POST', 'OPTIONS'])
def process_xml():
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        files = request.files.getlist('files')
        xml_files = [f for f in files if f.filename.lower().endswith('.xml')]
        pdf_files = {f.filename: f for f in files if f.filename.lower().endswith('.pdf')}

        if not xml_files:
            return jsonify({'error': 'Nenhum arquivo XML enviado'}), 400

        cliente_orizon = OrizonTISSEnvio(CODIGO_PRESTADOR, LOGIN, SENHA, REGISTRO_ANS)
        resultados_finais = []

        for xml_file in xml_files:
            xml_content = xml_file.read().decode('utf-8')
            processador = ProcessadorXMLTISS(xml_content)
            pacientes = processador.extrair_pacientes()

            if isinstance(pacientes, dict) and 'error' in pacientes:
                resultados_finais.append({'arquivo_xml': xml_file.filename, 'error': pacientes['error']})
                continue

            for paciente in pacientes:
                guia_prestador = paciente.get('numeroGuiaPrestador', '')
                pdf_encontrado = None
                
                # Busca o PDF correspondente
                pdf_filename_esperado = f"{guia_prestador}_GUIA_doc1.pdf"
                if pdf_filename_esperado in pdf_files:
                    pdf_encontrado = pdf_files[pdf_filename_esperado]
                else: # Busca alternativa
                    for fname, fobj in pdf_files.items():
                        if guia_prestador in fname:
                            pdf_encontrado = fobj
                            break
                
                if not pdf_encontrado:
                    resultados_finais.append({'paciente': paciente, 'status': 'Erro', 'error': 'PDF não encontrado'})
                    continue

                pdf_content = pdf_encontrado.read()
                pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
                pdf_encontrado.seek(0) # Reseta o ponteiro do arquivo

                resultado_envio = cliente_orizon.enviar_documento(
                    numero_lote=paciente.get('numeroLote', ''),
                    numero_protocolo=paciente.get('numeroProtocolo', ''),
                    numero_guia_prestador=guia_prestador,
                    numero_guia_operadora=paciente.get('numeroGuiaOperadora', ''),
                    numero_documento=paciente.get('numeroDocumento', ''),
                    pdf_base64=pdf_base64
                )
                resultados_finais.append({'paciente': paciente, 'resultado_envio': resultado_envio})
                time.sleep(1) # Pausa para não sobrecarregar o serviço

        return jsonify({'success': True, 'resultados': resultados_finais})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)