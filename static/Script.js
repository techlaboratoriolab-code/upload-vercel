// Elementos do DOM
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const processBtn = document.getElementById('processBtn');
const statusSection = document.getElementById('statusSection');
const statusText = document.getElementById('statusText');
const resultsSection = document.getElementById('resultsSection');
const resultsContent = document.getElementById('resultsContent');
const logConsole = document.getElementById('logConsole');
const logContent = document.getElementById('logContent');

// Estado da aplicação
let selectedFiles = [];

// Funções de Log
function addLog(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString('pt-BR');
    const logLine = document.createElement('div');
    logLine.className = `log-line log-${type}`;
    logLine.innerHTML = `<span class="log-timestamp">[${timestamp}]</span>${message}`;
    logContent.appendChild(logLine);
    logContent.scrollTop = logContent.scrollHeight; // Auto-scroll
}

function clearLogs() {
    logContent.innerHTML = '';
    addLog('Console limpo', 'info');
}

window.clearLogs = clearLogs;

// Event Listeners
uploadArea.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleFileSelect);
processBtn.addEventListener('click', processFiles);

// Drag and Drop
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('drag-over');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
    
    const files = Array.from(e.dataTransfer.files);
    addFiles(files);
});

// Funções
function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    addFiles(files);
}

function addFiles(files) {
    const validFiles = files.filter(file => {
        const isXML = file.name.toLowerCase().endsWith('.xml');
        const isPDF = file.name.toLowerCase().endsWith('.pdf');
        
        if (!isXML && !isPDF) {
            alert(`❌ O arquivo "${file.name}" tem formato inválido.\n✅ Apenas arquivos XML e PDF são permitidos.`);
            addLog(`❌ Arquivo rejeitado: ${file.name} (formato inválido)`, 'error');
            return false;
        }
        
        // Verificar se o arquivo já foi adicionado
        const alreadyAdded = selectedFiles.some(f => f.name === file.name && f.size === file.size);
        if (alreadyAdded) {
            alert(`⚠️ O arquivo "${file.name}" já foi adicionado.`);
            addLog(`⚠️ Arquivo duplicado: ${file.name}`, 'warning');
            return false;
        }
        
        addLog(`✅ Arquivo adicionado: ${file.name} (${formatFileSize(file.size)})`, 'success');
        return true;
    });
    
    if (validFiles.length === 0) return;
    
    selectedFiles = [...selectedFiles, ...validFiles];
    renderFileList();
    updateProcessButton();
}

function removeFile(index) {
    const fileName = selectedFiles[index].name;
    selectedFiles.splice(index, 1);
    addLog(`🗑️ Arquivo removido: ${fileName}`, 'warning');
    renderFileList();
    updateProcessButton();
}

function updateProcessButton() {
    // Verificar se há pelo menos 1 XML e 1 PDF
    const hasXML = selectedFiles.some(f => f.name.toLowerCase().endsWith('.xml'));
    const hasPDF = selectedFiles.some(f => f.name.toLowerCase().endsWith('.pdf'));
    
    processBtn.disabled = !(hasXML && hasPDF);
    
    if (selectedFiles.length === 0) {
        processBtn.textContent = 'Processar e Enviar Anexos';
    } else if (!hasXML) {
        processBtn.textContent = '⚠️ Adicione pelo menos 1 arquivo XML';
    } else if (!hasPDF) {
        processBtn.textContent = '⚠️ Adicione pelo menos 1 arquivo PDF';
    } else {
        const xmlCount = selectedFiles.filter(f => f.name.toLowerCase().endsWith('.xml')).length;
        const pdfCount = selectedFiles.filter(f => f.name.toLowerCase().endsWith('.pdf')).length;
        processBtn.textContent = `✨ Processar ${xmlCount} XML + ${pdfCount} PDF`;
    }
}

function renderFileList() {
    if (selectedFiles.length === 0) {
        fileList.classList.remove('active');
        fileList.innerHTML = '';
        return;
    }

    fileList.classList.add('active');
    
    const xmlFiles = selectedFiles.filter(f => f.name.toLowerCase().endsWith('.xml'));
    const pdfFiles = selectedFiles.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    
    let html = '';
    
    if (xmlFiles.length > 0) {
        html += '<div style="margin-bottom: 15px;"><strong style="color: #1976d2;">📄 Arquivos XML (' + xmlFiles.length + ')</strong></div>';
        xmlFiles.forEach((file) => {
            const globalIndex = selectedFiles.indexOf(file);
            html += createFileItem(file, globalIndex, '#1976d2');
        });
    }
    
    if (pdfFiles.length > 0) {
        html += '<div style="margin: 20px 0 15px;"><strong style="color: #c62828;">📎 Arquivos PDF (' + pdfFiles.length + ')</strong></div>';
        pdfFiles.forEach((file) => {
            const globalIndex = selectedFiles.indexOf(file);
            html += createFileItem(file, globalIndex, '#c62828');
        });
    }
    
    fileList.innerHTML = html;
}

function createFileItem(file, index, color) {
    return `
        <div class="file-item">
            <div class="file-info">
                <svg class="file-icon" style="color: ${color}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
                    <polyline points="13 2 13 9 20 9"></polyline>
                </svg>
                <div class="file-details">
                    <h4>${file.name}</h4>
                    <p>${formatFileSize(file.size)}</p>
                </div>
            </div>
            <button class="remove-btn" title="Remover arquivo" onclick="removeFile(${index})">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        </div>
    `;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

async function processFiles() {
    if (selectedFiles.length === 0) return;

    // Mostrar console de logs e status
    logConsole.classList.add('active');
    statusSection.classList.add('active');
    resultsSection.classList.remove('active');
    processBtn.disabled = true;
    
    addLog('='.repeat(60), 'info');
    addLog('🚀 INICIANDO PROCESSAMENTO', 'info');
    addLog('='.repeat(60), 'info');
    
    const xmlFiles = selectedFiles.filter(f => f.name.toLowerCase().endsWith('.xml'));
    const pdfFiles = selectedFiles.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    
    addLog(`📂 Total de arquivos XML: ${xmlFiles.length}`, 'info');
    addLog(`📎 Total de arquivos PDF: ${pdfFiles.length}`, 'info');
    
    statusText.textContent = 'Preparando arquivos...';

    try {
        addLog('📖 Lendo arquivos XML...', 'info');
        statusText.textContent = 'Lendo arquivos XML...';
        
        // Ler todos os XMLs
        const xmlPromises = xmlFiles.map((file) => {
            addLog(`  📄 Lendo: ${file.name}`, 'info');
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    addLog(`  ✅ Lido: ${file.name} (${formatFileSize(e.target.result.length)})`, 'success');
                    resolve({
                        name: file.name,
                        content: e.target.result
                    });
                };
                reader.onerror = () => {
                    addLog(`  ❌ Erro ao ler: ${file.name}`, 'error');
                    resolve(null);
                };
                reader.readAsText(file);
            });
        });

        const xmlData = (await Promise.all(xmlPromises)).filter(f => f !== null);
        
        addLog(`✅ ${xmlData.length} arquivos XML lidos com sucesso`, 'success');
        addLog('', 'info');
        addLog('📎 Convertendo PDFs para Base64...', 'info');
        statusText.textContent = 'Convertendo PDFs...';
        
        // Ler e converter PDFs para Base64
        const pdfPromises = pdfFiles.map((file) => {
            addLog(`  📄 Convertendo: ${file.name}`, 'info');
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const base64 = e.target.result.split(',')[1]; // Remove data:application/pdf;base64,
                    addLog(`  ✅ Convertido: ${file.name}`, 'success');
                    resolve({
                        name: file.name,
                        data: base64
                    });
                };
                reader.onerror = () => {
                    addLog(`  ❌ Erro ao converter: ${file.name}`, 'error');
                    resolve(null);
                };
                reader.readAsDataURL(file);
            });
        });

        const pdfData = (await Promise.all(pdfPromises)).filter(f => f !== null);
        
        // Criar objeto de PDFs
        const pdfs = {};
        pdfData.forEach(pdf => {
            pdfs[pdf.name] = pdf.data;
        });
        
        addLog(`✅ ${pdfData.length} PDFs convertidos com sucesso`, 'success');
        addLog('', 'info');

        // Separar PDFs grandes (>800KB) e pequenos para evitar erro 413
        const MAX_PDF_SIZE = 800 * 1024; // 800KB em bytes (mais conservador)
        const largePdfs = [];
        const smallPdfs = [];

        pdfData.forEach(pdf => {
            // Estimar tamanho do Base64 (Base64 é ~33% maior que binário)
            const estimatedSize = (pdf.data.length * 3) / 4;
            if (estimatedSize > MAX_PDF_SIZE) {
                largePdfs.push(pdf);
            } else {
                smallPdfs.push(pdf);
            }
        });

        if (largePdfs.length > 0) {
            addLog(`⚠️ ${largePdfs.length} PDF(s) grande(s) detectado(s) - serão processados individualmente`, 'warning');
            largePdfs.forEach(pdf => {
                const sizeMB = ((pdf.data.length * 3) / 4 / 1024 / 1024).toFixed(2);
                addLog(`   📄 ${pdf.name} (~${sizeMB} MB)`, 'warning');
            });
        }

        // Criar lotes: PDFs grandes individualmente, PDFs pequenos em grupos de 3
        const batches = [];

        // Adicionar PDFs grandes (um por lote)
        largePdfs.forEach(pdf => {
            batches.push([pdf]);
        });

        // Adicionar PDFs pequenos (3 por lote)
        const BATCH_SIZE = 3;
        for (let i = 0; i < smallPdfs.length; i += BATCH_SIZE) {
            batches.push(smallPdfs.slice(i, i + BATCH_SIZE));
        }

        addLog(`📦 Dividindo em ${batches.length} lote(s)`, 'info');
        addLog('📡 Enviando para o servidor...', 'info');

        let allResults = [];
        let pacientesProcessados = 0;

        for (let i = 0; i < batches.length; i++) {
            const batch = batches[i];
            const batchPdfs = {};

            batch.forEach(pdf => {
                batchPdfs[pdf.name] = pdf.data;
            });
            
            addLog('', 'info');
            addLog(`📤 Enviando lote ${i + 1}/${batches.length} (${batch.length} PDFs)...`, 'warning');
            statusText.textContent = `Enviando lote ${i + 1}/${batches.length}...`;
            
            const startTime = Date.now();
            let tentativa = 0;
            const maxTentativas = 2;
            let sucesso = false;

            while (tentativa < maxTentativas && !sucesso) {
                tentativa++;

                try {
                    if (tentativa > 1) {
                        addLog(`   🔄 Tentativa ${tentativa}/${maxTentativas}...`, 'warning');
                        await new Promise(resolve => setTimeout(resolve, 2000)); // Aguarda 2s antes de retry
                    }

                    const response = await fetch('/api/enviar', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            xmlFiles: xmlData,
                            pdfs: batchPdfs
                        })
                    });

                    const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);

                    if (!response.ok) {
                        const errorText = await response.text().catch(() => response.statusText);
                        addLog(`❌ Erro no lote ${i + 1}: ${response.status} - ${errorText}`, 'error');

                        if (tentativa < maxTentativas) {
                            continue; // Tenta novamente
                        }
                        throw new Error(`Erro no lote ${i + 1}: ${response.status} - ${errorText}`);
                    }

                    const result = await response.json();
                    allResults.push(...result.resultados);

                    // Mostrar logs detalhados de cada PDF processado
                    if (result.resultados && result.resultados.length > 0) {
                        result.resultados.forEach((res) => {
                            const loteNum = pacientesProcessados + 1;
                            const totalPdfs = pdfFiles.length;

                            addLog('', 'info');
                            addLog(`📦 LOTE [${loteNum}/${totalPdfs}]`, 'info');
                            addLog(`📋 Carteirinha: ${res.paciente?.numeroCarteira || 'N/A'}`, 'info');
                            addLog(`📝 Guia: ${res.paciente?.numeroGuiaPrestador || 'N/A'}`, 'info');
                            addLog(`📄 PDF: ${res.pdf_name || 'N/A'}`, 'info');

                            if (res.success) {
                                addLog(`✅ Enviado com sucesso!`, 'success');
                            } else {
                                const erro = res.resultado_envio?.error || res.error || 'Erro desconhecido';
                                addLog(`❌ Falha: ${erro}`, 'error');
                            }

                            pacientesProcessados++;
                        });
                    }

                    const sucessos = result.resumo?.sucessos || 0;
                    const erros = result.resumo?.erros || 0;

                    addLog('', 'info');
                    addLog(`📊 Resumo do lote ${i + 1}: ✓ ${sucessos} sucesso(s) | ✗ ${erros} erro(s) | ⏱️ ${elapsed}s`, 'info');
                    sucesso = true;

                } catch (error) {
                    if (tentativa >= maxTentativas) {
                        addLog(`❌ Falha no lote ${i + 1} após ${maxTentativas} tentativas: ${error.message}`, 'error');
                        addLog(`⚠️ Continuando com próximo lote...`, 'warning');
                        // Não lança erro, continua com próximo lote
                        break;
                    }
                }
            }
        }
        
        addLog('', 'info');
        addLog('='.repeat(60), 'info');
        addLog('📊 PROCESSAMENTO CONCLUÍDO', 'success');
        addLog('='.repeat(60), 'info');

        // Consolidar resultados
        const finalResult = {
            sucesso: allResults.filter(r => r.status === 'sucesso').length,
            erros: allResults.filter(r => r.status === 'erro').length,
            resultados: allResults
        };
        
        // Mostrar resultados
        displayResults(finalResult);
        
    } catch (error) {
        console.error('Erro ao processar arquivos:', error);
        addLog('', 'info');
        addLog('='.repeat(60), 'error');
        addLog('❌ ERRO CRÍTICO', 'error');
        addLog('='.repeat(60), 'error');
        addLog(`Erro: ${error.message}`, 'error');
        displayError(error.message);
    } finally {
        statusSection.classList.remove('active');
        processBtn.disabled = false;
    }
}

function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(new Error('Erro ao ler arquivo: ' + e.target.error));
        reader.readAsText(file);
    });
}

function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(new Error('Erro ao ler arquivo: ' + e.target.error));
        reader.readAsDataURL(file);
    });
}

function displayResults(result) {
    resultsSection.classList.add('active');
    resultsSection.style.borderLeftColor = 'var(--success-green)';
    resultsSection.style.background = '#f0fff4';
    
    resultsContent.innerHTML = '';

    if (result.success && result.resultados) {
        const resumo = result.resumo || {};
        const sucessos = resumo.sucessos || 0;
        const erros = resumo.erros || 0;
        const total = resumo.total || result.resultados.length;

        let html = `
            <h3 style="margin-bottom: 20px;">📊 Resultados do Processamento</h3>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 8px; text-align: center; color: white;">
                    <div style="font-size: 32px; font-weight: bold;">${total}</div>
                    <div style="font-size: 14px; opacity: 0.9;">Total</div>
                </div>
                <div style="background: linear-gradient(135deg, #48bb78 0%, #38a169 100%); padding: 20px; border-radius: 8px; text-align: center; color: white;">
                    <div style="font-size: 32px; font-weight: bold;">✅ ${sucessos}</div>
                    <div style="font-size: 14px; opacity: 0.9;">Sucessos</div>
                </div>
                <div style="background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%); padding: 20px; border-radius: 8px; text-align: center; color: white;">
                    <div style="font-size: 32px; font-weight: bold;">❌ ${erros}</div>
                    <div style="font-size: 14px; opacity: 0.9;">Erros</div>
                </div>
            </div>
        `;

        html += '<ul>';
        
        result.resultados.forEach(res => {
            const pac = res.paciente || {};
            const resultado_envio = res.resultado_envio || {};
            const isSuccess = resultado_envio.success;
            const errorMsg = res.error || resultado_envio.error || '';

            if (isSuccess) {
                html += `
                    <li class="success">
                        ✅ <strong>Guia ${pac.numeroGuiaPrestador || 'N/A'}</strong><br>
                        <small>👤 ${pac.nome || 'N/A'} | 🎫 Carteirinha: ${pac.carteirinha || 'N/A'}</small><br>
                        <small style="color: #48bb78;">Status: ${resultado_envio.status_code} | Tentativas: ${resultado_envio.tentativas || 1}</small>
                    </li>
                `;
            } else {
                html += `
                    <li class="error">
                        ❌ <strong>Guia ${pac.numeroGuiaPrestador || 'N/A'}</strong><br>
                        <small>👤 ${pac.nome || 'N/A'} | 🎫 Carteirinha: ${pac.carteirinha || 'N/A'}</small><br>
                        <small style="color: #f56565;">Erro: ${errorMsg}</small>
                    </li>
                `;
            }
        });

        html += '</ul>';
        resultsContent.innerHTML = html;

    } else if (result.error) {
        displayError(result.error);
    } else {
        displayError('Resposta inesperada do servidor');
    }

    // Scroll suave até os resultados
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function displayError(errorMessage) {
    resultsSection.classList.add('active');
    resultsSection.style.borderLeftColor = 'var(--error-red)';
    resultsSection.style.background = '#fff5f5';
    
    resultsContent.innerHTML = `
        <h3 style="color: var(--error-red);">❌ Erro no Processamento</h3>
        <p style="margin-top: 10px;">${errorMessage}</p>
        <div style="margin-top: 15px; padding: 10px; background: white; border-radius: 5px;">
            <p style="font-size: 12px; color: #666;">
                💡 Dica: Verifique se o servidor está rodando e se os arquivos estão corretos.
            </p>
        </div>
    `;
    
    // Scroll suave até o erro
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Expor funções globalmente
window.removeFile = removeFile;

// Log de inicialização
console.log('✅ Sistema LAB - Envio Anexos TISS inicializado');
console.log('📌 Aguardando seleção de arquivos...');
addLog('🚀 Sistema LAB - Envio de Anexos TISS', 'success');
addLog('📌 Selecione os arquivos XML e PDF para processar', 'info');
addLog('', 'info');
logConsole.classList.add('active');
