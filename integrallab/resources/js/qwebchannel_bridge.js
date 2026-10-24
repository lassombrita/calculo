/**
 * Puente QWebChannel entre Python y JavaScript del WebView.
 * 
 * Este archivo expone funciones desde el puente Python (PythonBridge)
 * al JavaScript del WebView para comunicación bidireccional.
 * 
 * Uso con MathJax:
 *   1. Cargar este archivo en QWebEngineView antes de mostrar fórmulas.
 *   2. Python envía JSON del árbol a través de QWebChannel.
 *   3. WebView renderiza fórmulas con MathJax inline o imágenes offline.
 */

// Exponer funciones globales para el puente QWebChannel
window.PythonBridge = window.PythonBridge || {};


/**
 * Carga árbol de pasos en el contenedor principal.
 * @param {string} jsonStr - JSON del árbol de pasos (compacto).
 */
PythonBridge.loadTree = function(jsonStr) {
    console.log('[qwebchannel_bridge] Cargando árbol:', jsonStr.substring(0, 100));
    
    // Parsear JSON y construir DOM
    const tree = this.parseStepTree(JSON.parse(jsonStr));
    this.renderStepTree(tree, document.getElementById('photomath-root'));
};


/**
 * Parsea diccionario del árbol a estructura recursiva.
 * @param {object} treeDict - Diccionario del árbol desde Python.
 * @returns {object} Estructura recursiva renderizada.
 */
PythonBridge.parseStepTree = function(treeDict) {
    const result = {};
    
    if (treeDict.root) {
        result.root = this.nodeToElement(treeDict.root);
    } else {
        result.root = this.nodeToElement(treeDict);
    }
    
    return result;
};


/**
 * Convierte nodo del árbol a elemento DOM.
 * @param {object} node - Nodo del árbol (dict o objeto).
 * @returns {object|Element} Elemento DOM recursivo.
 */
PythonBridge.nodeToElement = function(node) {
    const stepType = node.step_type || node.type;
    
    if (!stepType) {
        // Default: tratar como fórmula
        return this.createFormulaNode(node);
    }
    
    switch (stepType) {
        case 'formula':
            return this.createFormulaNode(node);
        case 'text':
            return this.createTextNode(node);
        default:
            // Fallback a fórmula
            return this.createFormulaNode({ ...node, step_type: 'formula' });
    }
};


/**
 * Crea elemento DOM para paso de fórmula.
 * @param {object} node - Nodo del árbol.
 * @returns {Element} Elemento HTML con fórmula MathJax.
 */
PythonBridge.createFormulaNode = function(node) {
    const latex = node.formula_metadata?.latex || node.latex || '';
    const imageB64 = node.formula_metadata?.image_base64 || null;
    const title = node.title || 'Paso';
    
    let formulaHTML;
    
    if (imageB64) {
        // Usar imagen renderizada offline
        formulaHTML = `<div class="formula-step" data-step-id="${node.step_id}">
            <div class="step-label">${title}</div>
            <img src="data:image/png;base64,${imageB64}" class="formula-img" />
        </div>`;
    } else {
        // Usar MathJax inline (escape para evitar inyección)
        const latexEscaped = this.escapeLatex(latex);
        formulaHTML = `<div class="formula-step" data-step-id="${node.step_id}">
            <div class="step-label">${title}</div>
            $$
                \\${latexEscaped}
            $$
        </div>`;
    }
    
    // Agregar sub-pasos si existen y están expandidos
    if (node.children && node.children.length > 0) {
        const isExpanded = node.is_expanded || false;
        let subHTML = '';
        
        for (const child of node.children) {
            subHTML += this.nodeToElement(child);
        }
        
        // Envolver en div para control de visibilidad
        formulaHTML = `<div class="formula-step ${isExpanded ? 'expanded' : ''}" data-step-id="${node.step_id}">
            <div class="step-label">${title}</div>
            ${imageB64 ? 
                `<img src="data:image/png;base64,${imageB64}" class="formula-img" />` : 
                `$${latexEscaped}$`
            }
            
            <!-- Sub-pasos (ocultos por defecto) -->
            <div class="sub-steps ${isExpanded ? 'expanded' : ''}">
                ${subHTML}
            </div>
        </div>`;
    }
    
    return formulaHTML;
};


/**
 * Crea elemento DOM para paso de texto.
 * @param {object} node - Nodo del árbol.
 * @returns {Element} Elemento HTML con explicación.
 */
PythonBridge.createTextNode = function(node) {
    const content = node.description || node.content || '';
    
    // Renderizar texto con posibles fórmulas incrustadas
    let formattedContent = content
        .replace(/\n/g, '<br>')
        .replace(/\$\$([^$]+)\$\$/g, '$1') // Mantener display mode
        .replace(/\$([^$]+)\$$/g, '$_1$'); // Inline MathJax
    
    return `<div class="text-step" data-step-id="${node.step_id}">
        ${formattedContent}
    </div>`;
};


/**
 * Escapa cadena LaTeX para evitar inyección.
 * @param {string} latex - Fórmula en LaTeX (ya procesada por Python).
 * @returns {string} Cadena con escapes apropiados.
 */
PythonBridge.escapeLatex = function(latex) {
    return latex
        .replace(/\\/g, '\\\\') // Escape de barra invertida primero
        .replace(/\$/g, '$$');  // Mantener delimiters
};


/**
 * Renderiza árbol completo en contenedor.
 * @param {object} tree - Raíz del árbol (dict o objeto).
 * @param {HTMLElement} container - Elemento DOM objetivo.
 */
PythonBridge.renderStepTree = function(tree, container) {
    // Construir HTML desde raíz
    const root = tree.root || tree;
    
    if (root && typeof root === 'object') {
        const html = this.nodeToElement(root);
        
        // Insertar antes de contenido existente (mantener MathJax inicial)
        container.innerHTML = html;
        
        // Renderizar con MathJax después de insertar
        this.triggerMathjaxRender();
    }
};


/**
 * Expande paso específico por ID.
 * @param {string} stepId - ID del paso a expandir.
 */
PythonBridge.expandStep = function(stepId) {
    const container = document.getElementById('photomath-root');
    
    if (!container) {
        console.error('[qwebchannel_bridge] No encontrado elemento photomath-root');
        return false;
    }
    
    const stepElement = container.querySelector(`[data-step-id="${stepId}"]`);
    
    if (stepElement && !stepElement.classList.contains('collapsed')) {
        stepElement.classList.add('expanded');
        
        // Expandir automáticamente sub-pasos si los hay y están ocultos
        const subSteps = stepElement.querySelector('.sub-steps');
        if (subSteps && subSteps.style.display === 'none') {
            subSteps.style.display = 'block';
        }
        
        console.log(`[qwebchannel_bridge] Expandido paso: ${stepId}`);
        return true;
    }
    
    console.warn(`[qwebchannel_bridge] Paso no expandido o no encontrado: ${stepId}`);
    return false;
};


/**
 * Colapsa paso específico por ID.
 * @param {string} stepId - ID del paso a colapsar.
 */
PythonBridge.collapseStep = function(stepId) {
    const container = document.getElementById('photomath-root');
    
    if (!container) {
        console.error('[qwebchannel_bridge] No encontrado elemento photomath-root');
        return false;
    }
    
    const stepElement = container.querySelector(`[data-step-id="${stepId}"]`);
    
    if (stepElement && stepElement.classList.contains('expanded')) {
        stepElement.classList.remove('expanded');
        
        // Colapsar sub-pasos si existen
        const subSteps = stepElement.querySelector('.sub-steps');
        if (subSteps) {
            subSteps.style.display = 'none';
        }
        
        console.log(`[qwebchannel_bridge] Colapsado paso: ${stepId}`);
        return true;
    }
    
    console.warn(`[qwebchannel_bridge] Paso no expandido o no encontrado: ${stepId}`);
    return false;
};


/**
 * Expande todos los pasos.
 */
PythonBridge.expandAllSteps = function() {
    const container = document.getElementById('photomath-root');
    
    if (!container) return;
    
    const steps = container.querySelectorAll('.formula-step:not(.collapsed)');
    
    steps.forEach(step => {
        step.classList.add('expanded');
        
        const subSteps = step.querySelector('.sub-steps');
        if (subSteps && subSteps.style.display === 'none') {
            subSteps.style.display = 'block';
        }
    });
    
    console.log(`[qwebchannel_bridge] Expandidos ${steps.length} pasos`);
    return steps.length;
};


/**
 * Colapsa todos los pasos.
 */
PythonBridge.collapseAllSteps = function() {
    const container = document.getElementById('photomath-root');
    
    if (!container) return;
    
    const expandedSteps = container.querySelectorAll('.formula-step.expanded');
    
    expandedSteps.forEach(step => {
        step.classList.remove('expanded');
        
        const subSteps = step.querySelector('.sub-steps');
        if (subSteps) {
            subSteps.style.display = 'none';
        }
    });
    
    console.log(`[qwebchannel_bridge] Colapsados ${expandedSteps.length} pasos`);
    return true;
};


/**
 * Alterna entre expandir/colapsar paso.
 * @param {string} stepId - ID del paso a alternar.
 */
PythonBridge.toggleStep = function(stepId) {
    const container = document.getElementById('photomath-root');
    
    if (!container) return false;
    
    const stepElement = container.querySelector(`[data-step-id="${stepId}"]`);
    
    if (stepElement) {
        // Verificar si ya está expandido
        if (stepElement.classList.contains('expanded')) {
            stepElement.classList.remove('expanded');
            
            const subSteps = stepElement.querySelector('.sub-steps');
            if (subSteps && subSteps.style.display === 'block') {
                subSteps.style.display = 'none';
            }
            
            console.log(`[qwebchannel_bridge] Colapsado: ${stepId}`);
        } else {
            stepElement.classList.add('expanded');
            
            const subSteps = stepElement.querySelector('.sub-steps');
            if (subSteps && subSteps.style.display === 'none') {
                subSteps.style.display = 'block';
            }
            
            console.log(`[qwebchannel_bridge] Expandido: ${stepId}`);
        }
        
        return true;
    }
    
    console.warn(`[qwebchannel_bridge] Paso no encontrado: ${stepId}`);
    return false;
};


/**
 * Renderiza todas las fórmulas con MathJax.
 */
PythonBridge.triggerMathjaxRender = function() {
    if (typeof window.MathJax !== 'undefined') {
        window.MathJax.typesetPromise();
    } else {
        // Fallback: re-renderizar solo contenedores display math
        const displayMath = document.querySelectorAll('$$');
        
        displayMath.forEach(container => {
            const latex = container.textContent.trim();
            if (latex) {
                const processed = latex.replace(/\$$/, '');
                
                // Re-inyectar para re-renderizar MathJax
                container.innerHTML = `$${processed}$`;
            }
        });
        
        // Trigger tipográfico si es posible
        try {
            window.MathJax.startup.documentDDT();
        } catch (e) {
            // Silently ignore errors en fallback
        }
    }
};


/**
 * Notifica a Python que el usuario seleccionó un paso.
 * @param {string} stepId - ID del paso seleccionado.
 */
PythonBridge.notifyStepSelected = function(stepId) {
    console.log(`[qwebchannel_bridge] Paso seleccionado: ${stepId}`);
    
    // Emitir evento al puente Python (si está disponible)
    if (window.PythonBridge && window.PythonBridge.__webChannel_) {
        const channel = window.PythonBridge.__webChannel_.object('PythonBridge');
        if (channel && channel.notifyStepSelected) {
            channel.notifyStepSelected(stepId);
        }
    }
};


// Inicializar si ya está disponible el canal QWebChannel
if (typeof window.QWebChannel !== 'undefined') {
    const channel = new QWebChannel(window.PythonBridge.__webChannel_);
    console.log('[qwebchannel_bridge] QWebChannel inicializado');
}


// Exportar funciones globales para acceso directo desde JS del WebView
window.stepActions = {
    expandStep: PythonBridge.expandStep.bind(PythonBridge),
    collapseStep: PythonBridge.collapseStep.bind(PythonBridge),
    toggleStep: PythonBridge.toggleStep.bind(PythonBridge),
    expandAllSteps: PythonBridge.expandAllSteps.bind(PythonBridge),
    collapseAllSteps: PythonBridge.collapseAllSteps.bind(PythonBridge),
};


console.log('[qwebchannel_bridge] Puente inicializado correctamente');
