/* Desglose paso a paso «estilo Photomath» para IntegralLab.
 *
 * Python (integrallab/ui/views/steps_view.py) envía un árbol de pasos en JSON:
 *     { id, rule, title, explanation, latex, children: [...] }
 * Dentro del LaTeX de un paso, cada subexpresión que tiene su propio desarrollo va envuelta en
 * \class{step-<id>}{...}. MathJax (extensión html) la convierte en un <g class="step-<id>"> del
 * SVG; aquí esos grupos se vuelven botones: al tocarlos se despliega el paso <id> justo debajo de
 * la fórmula, con su explicación y su propia fórmula (que a su vez puede tener partes clicables).
 *
 * Reglas de seguridad: todo texto se inserta con textContent (nunca innerHTML con datos); el
 * LaTeX lo genera el dominio con SymPy, no el usuario; MathJax corre sin menú ni red.
 */
(function () {
    "use strict";

    var state = {
        tree: null,
        byId: {},          // id → nodo
        parentOf: {},      // id → id del padre
        panels: {},        // id → <section> ya construido
        mathReady: false,
        pending: null,     // árbol recibido antes de que MathJax terminara de cargar
        bridge: null
    };

    function notify(method) {
        var args = Array.prototype.slice.call(arguments, 1);
        if (state.bridge && typeof state.bridge[method] === "function") {
            state.bridge[method].apply(state.bridge, args);
        }
    }

    function index(node, parentId) {
        state.byId[node.id] = node;
        if (parentId) { state.parentOf[node.id] = parentId; }
        (node.children || []).forEach(function (child) { index(child, node.id); });
    }

    function stepIdOf(element) {
        var cls = element.getAttribute && element.getAttribute("class");
        if (!cls) { return null; }
        var m = /(?:^|\s)step-([A-Za-z0-9_-]+)(?:\s|$)/.exec(cls);
        return m ? m[1] : null;
    }

    // ── Fórmulas ────────────────────────────────────────────────────────────

    function typeset(container, latex, ownerId) {
        container.textContent = "";
        if (!latex) { return Promise.resolve(); }
        if (!state.mathReady || !window.MathJax || !MathJax.tex2svgPromise) {
            var raw = document.createElement("code");
            raw.className = "raw";
            raw.textContent = latex;
            container.appendChild(raw);
            return Promise.resolve();
        }
        return MathJax.tex2svgPromise(latex, { display: true }).then(function (node) {
            container.appendChild(node);
            decorateAnchors(container, ownerId);
        }).catch(function () {
            var raw = document.createElement("code");
            raw.className = "raw";
            raw.textContent = latex;
            container.appendChild(raw);
        });
    }

    function decorateAnchors(container, ownerId) {
        var anchors = container.querySelectorAll('[class*="step-"]');
        Array.prototype.forEach.call(anchors, function (el) {
            var target = stepIdOf(el);
            if (!target || !state.byId[target]) { return; }
            el.classList.add("step-anchor");
            el.setAttribute("tabindex", "0");
            el.setAttribute("role", "button");
            el.setAttribute("data-target", target);
            el.setAttribute("data-owner", ownerId);
            el.setAttribute("aria-label", "Ver cómo se obtiene: " + state.byId[target].title);
            var title = document.createElementNS("http://www.w3.org/2000/svg", "title");
            title.textContent = state.byId[target].title;
            el.insertBefore(title, el.firstChild);
        });
    }

    // ── Tarjetas ────────────────────────────────────────────────────────────

    function buildPanel(node, number) {
        if (state.panels[node.id]) { return state.panels[node.id]; }
        var section = document.createElement("section");
        section.className = "step";
        section.setAttribute("data-id", node.id);
        section.setAttribute("data-rule", node.rule || "");

        var h = document.createElement("h3");
        h.className = "step-title";
        h.textContent = (number ? number + ". " : "") + node.title;
        section.appendChild(h);

        if (node.explanation) {
            var p = document.createElement("p");
            p.className = "step-expl";
            p.textContent = node.explanation;
            section.appendChild(p);
        }

        var formula = document.createElement("div");
        formula.className = "formula";
        section.appendChild(formula);
        typeset(formula, node.latex, node.id);

        var kids = node.children || [];
        if (kids.length) {
            var how = document.createElement("button");
            how.type = "button";
            how.className = "how";
            how.setAttribute("aria-expanded", "false");
            how.textContent = howLabel(kids.length, false);
            how.addEventListener("click", function () { toggleAll(node.id); });
            section.appendChild(how);

            var box = document.createElement("div");
            box.className = "children";
            box.hidden = true;
            section.appendChild(box);
        }
        state.panels[node.id] = section;
        return section;
    }

    function howLabel(n, open) {
        if (open) { return "Ocultar el desarrollo"; }
        return n === 1 ? "¿Cómo se obtiene? (1 paso)" : "¿Cómo se obtiene? (" + n + " pasos)";
    }

    function childBox(parentId) {
        var panel = state.panels[parentId];
        return panel ? panel.querySelector(":scope > .children") : null;
    }

    function ensureChild(parentId, childId) {
        var box = childBox(parentId);
        if (!box) { return null; }
        var panel = state.panels[childId];
        if (!panel) {
            panel = buildPanel(state.byId[childId], "");
            panel.hidden = true;
            // Conserva el orden del árbol aunque los hijos se construyan en otro orden.
            var order = state.byId[parentId].children.map(function (c) { return c.id; });
            var pos = order.indexOf(childId);
            var before = null;
            for (var i = pos + 1; i < order.length && !before; i++) {
                if (state.panels[order[i]] && state.panels[order[i]].parentNode === box) {
                    before = state.panels[order[i]];
                }
            }
            box.insertBefore(panel, before);
        }
        return panel;
    }

    function refreshParent(parentId) {
        var box = childBox(parentId);
        if (!box) { return; }
        var anyOpen = Array.prototype.some.call(box.children, function (c) { return !c.hidden; });
        var allOpen = state.byId[parentId].children.every(function (c) {
            return state.panels[c.id] && !state.panels[c.id].hidden;
        });
        box.hidden = !anyOpen;
        var how = state.panels[parentId].querySelector(":scope > .how");
        if (how) {
            how.setAttribute("aria-expanded", allOpen ? "true" : "false");
            how.textContent = howLabel(state.byId[parentId].children.length, allOpen);
        }
        var anchors = state.panels[parentId].querySelectorAll(':scope > .formula .step-anchor');
        Array.prototype.forEach.call(anchors, function (a) {
            var p = state.panels[a.getAttribute("data-target")];
            a.classList.toggle("open", !!p && !p.hidden);
        });
    }

    function setOpen(id, open) {
        var parentId = state.parentOf[id];
        if (!parentId) { return; }
        if (open) { setOpen(parentId, true); }            // abre también los antepasados
        var panel = open ? ensureChild(parentId, id) : state.panels[id];
        if (!panel) { return; }
        if (panel.hidden === !open) { return; }
        panel.hidden = !open;
        refreshParent(parentId);
        notify("stepToggled", id, open);
    }

    function flash(panel) {
        panel.classList.add("flash");
        setTimeout(function () { panel.classList.remove("flash"); }, 700);
    }

    // Toque en una parte resaltada: alterna su paso. Si el paso no es hijo de la tarjeta donde se
    // tocó (p. ej. V₁ en el resultado final remite al tramo 1), se abre donde vive y se muestra.
    // Los pasos principales (hijos de la raíz) siempre están a la vista: tocarlos solo los señala.
    function activate(targetId, forceOpen) {
        var panel = state.panels[targetId];
        var topLevel = state.tree && state.parentOf[targetId] === state.tree.id;
        if (panel && isVisible(panel) && !forceOpen && !topLevel) {
            setOpen(targetId, false);
            return;
        }
        setOpen(targetId, true);
        panel = state.panels[targetId];
        if (panel) {
            panel.scrollIntoView({ block: "nearest", behavior: "smooth" });
            flash(panel);
        }
    }

    function isVisible(el) {
        while (el && el !== document.body) {
            if (el.hidden) { return false; }
            el = el.parentNode;
        }
        return true;
    }

    function toggleAll(id) {
        var node = state.byId[id];
        var allOpen = node.children.every(function (c) { return state.panels[c.id] && !state.panels[c.id].hidden; });
        node.children.forEach(function (c) { setOpen(c.id, !allOpen); });
    }

    function expandEverything(open) {
        var ids = Object.keys(state.byId);
        ids.forEach(function (id) {
            if (!state.parentOf[id] || !state.parentOf[state.parentOf[id]]) { return; }  // nivel 1 ya visible
            if (open) { setOpen(id, true); } else if (state.panels[id]) { setOpen(id, false); }
        });
    }

    // ── Eventos ─────────────────────────────────────────────────────────────

    function anchorFrom(event) {
        var el = event.target;
        while (el && el !== document) {
            if (el.classList && el.classList.contains("step-anchor")) { return el; }
            el = el.parentNode;
        }
        return null;
    }

    document.addEventListener("click", function (event) {
        var anchor = anchorFrom(event);
        if (!anchor) { return; }
        event.preventDefault();
        activate(anchor.getAttribute("data-target"));
    });

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") { return; }
        var anchor = anchorFrom(event);
        if (!anchor) { return; }
        event.preventDefault();
        activate(anchor.getAttribute("data-target"));
    });

    // ── API para Python ─────────────────────────────────────────────────────

    function render(payload) {
        state.tree = payload && payload.tree ? payload.tree : null;
        state.byId = {};
        state.parentOf = {};
        state.panels = {};
        var main = document.getElementById("steps");
        main.textContent = "";
        var summary = document.getElementById("summary");
        var hint = document.getElementById("hint");
        var empty = document.getElementById("empty");
        if (!state.tree) {
            summary.hidden = true;
            hint.hidden = true;
            empty.hidden = false;
            empty.textContent = (payload && payload.message) || "Aquí aparecerá el desglose interactivo del cálculo.";
            notify("rendered", 0);
            return;
        }
        if (!state.mathReady) {
            state.pending = payload;
            return;
        }
        empty.hidden = true;
        summary.hidden = false;
        hint.hidden = false;
        document.getElementById("summary-title").textContent = payload.title || state.tree.title;
        document.getElementById("summary-meta").textContent = payload.meta || "";
        index(state.tree, null);

        // La raíz se muestra como encabezado (su fórmula es el resultado); sus hijos son los pasos.
        var root = buildPanel(state.tree, "");
        root.classList.add("root");
        main.appendChild(root);
        var box = childBox(state.tree.id);
        state.tree.children.forEach(function (child, i) {
            var panel = buildPanel(child, String(i + 1));
            box.appendChild(panel);
        });
        if (box) { box.hidden = false; }
        var how = root.querySelector(":scope > .how");
        if (how) { how.remove(); }
        notify("rendered", Object.keys(state.byId).length);
    }

    window.IntegralSteps = {
        render: render,
        reveal: function (id) { activate(id, true); },
        setOpen: setOpen,
        isOpen: function (id) { var p = state.panels[id]; return !!p && isVisible(p); },
        expandAll: function () { expandEverything(true); },
        collapseAll: function () { expandEverything(false); },
        anchorCount: function () { return document.querySelectorAll(".step-anchor").length; },
        mathReady: function () {
            // Hoja de estilos de la salida SVG: oculta el MathML de accesibilidad (sin ella se ven
            // dos copias de cada fórmula) y fija tamaños. tex2svgPromise no la inserta sola.
            if (!document.getElementById("MJX-SVG-styles") && MathJax.svgStylesheet) {
                document.head.appendChild(MathJax.svgStylesheet());
            }
            state.mathReady = true;
            if (state.pending) {
                var p = state.pending;
                state.pending = null;
                render(p);
            }
            notify("ready");
        }
    };

    document.addEventListener("DOMContentLoaded", function () {
        document.getElementById("expand-all").addEventListener("click", function () { expandEverything(true); });
        document.getElementById("collapse-all").addEventListener("click", function () { expandEverything(false); });
        if (window.qt && window.qt.webChannelTransport && window.QWebChannel) {
            new QWebChannel(window.qt.webChannelTransport, function (channel) {
                state.bridge = channel.objects.bridge || null;
                if (state.mathReady) { notify("ready"); }
            });
        }
    });
})();
