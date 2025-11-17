// Elementos do DOM
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const processBtn = document.getElementById('processBtn');
const statusSection = document.getElementById('statusSection');
const statusText = document.getElementById('statusText');
const resultsSection = document.getElementById('resultsSection');
const resultsContent = document.getElementById('resultsContent');

// Estado da aplicação
let selectedFiles = [];

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
            alert(`❌ O arquivo "${file.name}" tem formato inválido.\n✅ Apenas XML e PDF são permitidos.`);
            return false;
        }
        
        // Verificar se o arquivo já foi adicionado
        const alreadyAdded = selectedFiles.some(f => f.name === file.name && f.size === file.size);
        if (alreadyAdded) {
            alert(`⚠️ O arquivo "${file.name}" já foi adicionado.`);
            return false;
        }
        
        return true;
    });
    
    if (validFiles.length === 0) return;
    
    selectedFiles = [...selectedFiles, ...validFiles];
    renderFileList();
    updateProcessButton();
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    renderFileList();
    updateProcessButton();
}

function updateProcessButton() {
    // Verificar se há pelo menos 1 XML e 1 PDF
    const hasXML = selectedFiles.some(f => f.name.toLowerCase().endsWith('.xml'));
    const hasPDF = selectedFiles.some(f => f.name.toLowerCase().endsWith('.pdf'));
    
    processBtn.disabled = !(hasXML && hasPDF);
    
    if (selectedFiles.length > 0 && !hasXML) {
        processBtn.textContent = '⚠️ Adicione pelo menos 1 arquivo XML';
    } else if (selectedFiles.length > 0 && !hasPDF) {
        processBtn.textContent = '⚠️ Adicione pelo menos 1 arquivo PDF';
    } else if (hasXML && hasPDF) {
        processBtn.textContent = '✨ Processar e Enviar Anexos';
    } else {
        processBtn.textContent = 'Processar e Enviar Anexos';
    }
}

function renderFileList() {
    if (selectedFiles.length === 0) {
        fileList.classList.remove('active');
        fileList.innerHTML = '';
        return;
    }

    fileList.classList.add('active');
    
    // Separar arquivos por tipo
    const xmlFiles = selectedFiles.filter(f => f.name.toLowerCase().endsWith('.xml'));
    const pdfFiles = selectedFiles.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    
    let html = '';
    
    if (xmlFiles.length > 0) {
        html += '<div style="margin-bottom: 15px;"><strong style="color: #1976d2;">📄 Arquivos XML (' + xmlFiles.length + ')</strong></div>';
        xmlFiles.forEach((file, index) => {
            const globalIndex = selectedFiles.indexOf(file);
            html += createFileItem(file, globalIndex, '#1976d2');
        });
    }
    
    if (pdfFiles.length > 0) {
        html += '<div style="margin: 20px 0 15px;"><strong style="color: #c62828;">📎 Arquivos PDF (' + pdfFiles.length + ')</strong></div>';
        pdfFiles.forEach((file, index) => {
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

    // Mostrar status de processamento
    statusSection.classList.add('active');
    resultsSection.classList.remove('active');
    processBtn.disabled = true;
    statusText.textContent = 'Preparando arquivos...';

    try {
        // Separar XML e PDFs
        const xmlFile = selectedFiles.find(f => f.name.toLowerCase().endsWith('.xml'));
        const pdfFiles = selectedFiles.filter(f => f.name.toLowerCase().endsWith('.pdf'));

        if (!xmlFile) {
            throw new Error('Nenhum arquivo XML encontrado');
        }

        statusText.textContent = 'Lendo arquivo XML...';
        const xmlContent = await readFileAsText(xmlFile);

        statusText.textContent = 'Convertendo PDFs para Base64...';
        const pdfsDict = {};
        for (let i = 0; i < pdfFiles.length; i++) {
            statusText.textContent = `Convertendo PDF ${i + 1} de ${pdfFiles.length}...`;
            const base64 = await readFileAsBase64(pdfFiles[i]);
            pdfsDict[pdfFiles[i].name] = base64.split(',')[1]; // Remove data:application/pdf;base64,
        }

        statusText.textContent = 'Enviando para processamento...';

        // Fazer requisição para o backend
        const response = await fetch('/api/enviar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                xml_content: xmlContent,
                pdfs: pdfsDict
            })
        });

        if (!response.ok) {
            throw new Error(`Erro na requisição: ${response.status} - ${response.statusText}`);
        }

        const result = await response.json();

        // Mostrar resultados
        displayResults(result);
        
    } catch (error) {
        console.error('Erro ao processar arquivos:', error);
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
        let html = '<h3>📊 Resultados do Processamento</h3>';
        
        const sucessos = result.sucessos || 0;
        const falhas = result.falhas || 0;
        const total = result.total || result.resultados.length;

        html += `
            <div style="background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <p><strong>Total de guias:</strong> ${total}</p>
                <p style="color: var(--success-green);"><strong>✅ Sucessos:</strong> ${sucessos}</p>
                <p style="color: var(--error-red);"><strong>❌ Falhas:</strong> ${falhas}</p>
            </div>
        `;

        html += '<ul>';
        
        result.resultados.forEach(res => {
            const pac = res.paciente || {};
            const status = res.status || '';
            const isSuccess = res.success;

            if (isSuccess) {
                html += `
                    <li class="success">
                        ✅ <strong>Guia ${pac.numeroGuiaPrestador || 'N/A'}</strong><br>
                        <small>Carteirinha: ${pac.carteirinha || 'N/A'} | ${status}</small>
                    </li>
                `;
            } else {
                const errorMsg = res.error || status || 'Erro desconhecido';
                html += `
                    <li class="error">
                        ❌ <strong>Guia ${pac.numeroGuiaPrestador || 'N/A'}</strong><br>
                        <small>Erro: ${errorMsg}</small>
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
console.log('📌 Aguardando seleção de arquivos XML e PDF...');
