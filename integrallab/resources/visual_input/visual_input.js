/*
 * Editor visual de fórmulas de IntegralLab.
 *
 * Cada casilla es un <math-field> de MathLive: la fracción dibuja su raya, la raíz su signo y
 * la potencia su exponente, como en GeoGebra o en una calculadora con «Natural Display».
 * La página solo envía el LaTeX de cada casilla a Python por QWebChannel; la traducción a la
 * sintaxis del parser y la validación ocurren en Python (integrallab/core/latex_input.py).
 */
(function () {
    "use strict";

    const FIELDS = ["f", "g", "a", "b"];
    const fields = {};
    let bridge = null;
    let active = null;          // última casilla con foco: destino de los botones
    let silent = false;         // true mientras Python escribe una casilla (no se reenvía)

    // Sin sonidos ni teclado virtual flotante: la barra propia hace ese papel.
    MathfieldElement.soundsDirectory = null;

    // Atajos en español (es-CO) y «log» sin subíndice automático (log = base 10).
    const SHORTCUTS = {
        sen: "\\sin", tg: "\\tan", ctg: "\\cot", cotg: "\\cot", cosec: "\\csc",
        arcsen: "\\arcsin", arctg: "\\arctan", senh: "\\sinh",
        log: "\\log", ln: "\\ln", pi: "\\pi",
    };

    function setup(mf) {
        const name = mf.dataset.field;
        fields[name] = mf;
        mf.mathVirtualKeyboardPolicy = "manual";
        mf.smartFence = true;
        mf.smartSuperscript = true;
        mf.inlineShortcuts = Object.assign({}, mf.inlineShortcuts, SHORTCUTS);
        try { mf.menuItems = []; } catch (e) { /* versiones sin menú */ }

        mf.addEventListener("focusin", () => { active = mf; });
        // Los avisos de «recuadro vacío» se muestran al salir de la casilla, no mientras se escribe.
        mf.addEventListener("focusout", () => { if (bridge) bridge.fieldCommitted(name); });
        mf.addEventListener("input", () => {
            if (!silent && bridge) bridge.fieldChanged(name, mf.getValue("latex"));
        });
        // Enter calcula (como el botón «Generar»); se intercepta antes que MathLive.
        mf.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter" && !ev.shiftKey) {
                ev.preventDefault();
                ev.stopPropagation();
                if (bridge) {
                    bridge.fieldChanged(name, mf.getValue("latex"));
                    bridge.submit();
                }
            }
        }, { capture: true });
    }

    function insertTemplate(button) {
        const mf = active || fields.f;
        if (!mf) return;
        mf.focus();
        if (button.dataset.command) {
            mf.executeCommand(button.dataset.command);
        } else {
            // #@ = lo seleccionado (o lo que está antes del cursor); #? = recuadro vacío.
            mf.executeCommand(["insert", button.dataset.insert, { selectionMode: "placeholder", focus: true }]);
        }
        if (bridge) bridge.fieldChanged(mf.dataset.field, mf.getValue("latex"));
    }

    function reportHeight() {
        if (bridge) bridge.contentHeight(Math.ceil(document.getElementById("editor").getBoundingClientRect().height) + 2);
    }

    // API que usa Python ------------------------------------------------------
    function setLatex(name, latex) {
        const mf = fields[name];
        if (!mf) return;
        silent = true;
        try { mf.setValue(latex || "", { silenceNotifications: true }); } finally { silent = false; }
    }

    function setStatus(name, message) {
        const box = document.getElementById("status-" + name);
        const mf = fields[name];
        if (box) box.textContent = message || "";
        if (mf) mf.classList.toggle("has-error", Boolean(message));
        reportHeight();
    }

    function focusField(name) {
        const mf = fields[name];
        if (mf) { mf.focus(); active = mf; }
    }

    window.IntegralLabInput = {
        setLatex, setStatus, focusField,
        getLatex: (name) => (fields[name] ? fields[name].getValue("latex") : ""),
    };

    // Arranque ----------------------------------------------------------------
    document.querySelectorAll("math-field").forEach(setup);
    document.querySelectorAll(".tool").forEach((button) => {
        // mousedown sin foco: la casilla activa conserva el cursor al pulsar un botón.
        button.addEventListener("mousedown", (ev) => ev.preventDefault());
        button.addEventListener("click", () => insertTemplate(button));
    });
    new ResizeObserver(reportHeight).observe(document.getElementById("editor"));

    if (typeof QWebChannel !== "undefined" && window.qt && qt.webChannelTransport) {
        new QWebChannel(qt.webChannelTransport, (channel) => {
            bridge = channel.objects.bridge;
            bridge.setLatexRequested.connect(setLatex);
            bridge.statusChanged.connect(setStatus);
            bridge.focusRequested.connect(focusField);
            reportHeight();
            bridge.ready(FIELDS.join(","));
        });
    }
})();
