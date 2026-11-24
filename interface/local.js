/* Adaptateur local : remplace l'application Claude quand la page est servie par `uv run hub-web`.
   - mcp : appelle les outils du hub via http://127.0.0.1 (jeton propre au lancement) ;
   - sample : réponses rédigées par Claude via l'API Anthropic si une clé est configurée,
     sinon mise en forme des pistes trouvées par le hub (mode sans IA). */
(function () {
  "use strict";
  var TOKEN = (window.HUB_LOCAL || {}).token || "";

  function post(path, body) {
    return fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Token": TOKEN }, body: JSON.stringify(body || {}) })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (!r.ok) throw { code: j.code || "upstream_error", message: j.message || ("HTTP " + r.status) };
          return j;
        });
      }, function () { throw { code: "server_not_connected", message: "la page web locale ne répond plus (fenêtre du hub fermée ?)" }; });
  }

  var MCP = {
    callTool: function (server, tool, input) {
      return post("/api/tool/" + encodeURIComponent(tool), input || {}).then(function (j) { return { payload: j.payload, content: [] }; });
    },
    watchTool: function (server, tool, input, handler, opts) {
      var stop = false;
      function run() {
        MCP.callTool(server, tool, input).then(function (r) { if (!stop) handler({ type: "data", result: r }); },
          function (e) { if (!stop) handler({ type: "error", error: e }); });
      }
      setTimeout(run, 0);
      var every = opts && opts.refetchInterval ? Math.max(30000, opts.refetchInterval) : 0;
      var id = every ? setInterval(run, every) : null;
      WATCHES.push({ tool: tool, run: run });
      return function () { stop = true; if (id) clearInterval(id); };
    },
    invalidate: function (server, tool) {
      WATCHES.forEach(function (w) { if (!tool || w.tool === tool) w.run(); });
      return Promise.resolve();
    },
    listTools: function () { return Promise.resolve({ servers: [] }); }
  };
  var WATCHES = [];

  function lastQuestion(messages) {
    var m = messages[messages.length - 1] || {};
    var t = typeof m.content === "string" ? m.content : "";
    var i = t.lastIndexOf("Question : ");
    return (i >= 0 ? t.slice(i + 11) : t).trim();
  }
  function mdLink(title, url) { return /^https:\/\//.test(url || "") ? "[" + String(title).replace(/[\[\]]/g, "") + "](" + url + ")" : String(title); }
  function nfmt(v) { return v == null ? "—" : new Intl.NumberFormat("fr-FR").format(v); }

  function formatDpe(d) {
    if (d.erreur) return d.erreur + (d.adresse_reconnue ? "\nAdresse reconnue : " + d.adresse_reconnue : "");
    var out = ["**Adresse reconnue : " + d.adresse_reconnue + "** · " + nfmt(d.total) + " diagnostic(s) trouvé(s)."];
    (d.diagnostics || []).forEach(function (x) {
      out.push("- **Étiquette énergie " + (x.etiquette_dpe || "?") + ", climat " + (x.etiquette_ges || "?") + "** · " + (x.type_batiment || "logement") +
        (x.surface_habitable_logement ? ", " + Math.round(x.surface_habitable_logement) + " m²" : "") +
        (x.date_etablissement_dpe ? ", établi le " + x.date_etablissement_dpe : "") +
        (x.date_fin_validite_dpe ? ", valable jusqu'au " + x.date_fin_validite_dpe : "") +
        (x.conso_5_usages_par_m2_ep != null ? ", " + Math.round(x.conso_5_usages_par_m2_ep) + " kWh/m²/an" : ""));
    });
    if (!(d.diagnostics || []).length) out.push("Aucun DPE « logements existants » à cette adresse exacte.");
    out.push("Sources : " + (d.sources || []).join(" ; ") + ".");
    if (d.limites) out.push(d.limites);
    return out.join("\n");
  }
  function formatLeads(d) {
    var out = ["Mode sans IA : voici ce que le hub a trouvé dans les sources publiques. Pour une réponse rédigée, ajoutez une clé d'API Anthropic (voir le mode d'emploi)."];
    if (d.lieu_detecte) out.push("Lieu détecté : **" + d.lieu_detecte + "**.");
    (d.pistes || []).forEach(function (p) {
      var line = "- **" + p.jeu + "** (" + (p.producteur || "producteur inconnu") + ") : fichier « " + p.fichier + " »";
      if (p.erreur) line += ", lecture impossible (" + p.erreur + ")";
      else {
        line += ", " + nfmt(p.total) + " ligne(s)" + (p.filtre ? " où " + p.filtre : "");
        var row = (p.lignes || [])[0];
        if (row) line += ". Exemple : " + Object.keys(row).filter(function (k) { return k !== "__id" && row[k] != null && row[k] !== ""; }).slice(0, 6)
          .map(function (k) { return k.trim() + " = " + String(row[k]).slice(0, 40); }).join(" ; ");
      }
      out.push(line + ". " + mdLink("Voir le jeu", p.page));
    });
    var res = d.resultats || {};
    if ((res.datasets || []).length) {
      out.push("Autres jeux de données :");
      res.datasets.slice(0, 5).forEach(function (x) { out.push("- " + mdLink(x.title, x.page) + " (" + (x.organization_name || "—") + ")"); });
    }
    if ((d.api || []).length) {
      out.push("API publiques :");
      d.api.forEach(function (a) { out.push("- " + a.titre + " (" + (a.producteur || "—") + ", accès " + a.acces + ")"); });
    }
    if (!(d.pistes || []).length && !(res.datasets || []).length) out.push("Aucune source pertinente trouvée. Essayez d'autres mots-clés.");
    if (d.limites) out.push(d.limites);
    return out.join("\n");
  }

  function sampleWithoutAI(messages) {
    var q = lastQuestion(messages);
    return MCP.callTool("local", "repondre", { question: q }).then(function (r) {
      var d = r.payload || {};
      return { text: d.intention === "dpe" ? formatDpe(d) : formatLeads(d), truncated: false };
    });
  }

  function sampleWithAI(messages, opts) {
    var tools = opts.tools || [];
    var defs = tools.map(function (t) { return { name: t.name, description: t.description, input_schema: t.inputSchema }; });
    var msgs = messages.map(function (m) { return { role: m.role, content: m.content }; });
    var step = 0;
    function turn() {
      if (step++ >= 10) return Promise.resolve({ text: "Recherche interrompue : trop d'étapes. Reformulez la question.", truncated: true });
      return post("/api/llm", { messages: msgs, tools: defs }).then(function (r) {
        if (r.error) throw { code: "upstream_error", message: r.error };
        var content = r.content || [];
        msgs.push({ role: "assistant", content: content });
        var text = content.filter(function (b) { return b.type === "text"; }).map(function (b) { return b.text; }).join("\n");
        if (text && opts.onText) opts.onText({ text: text, delta: text });
        var uses = content.filter(function (b) { return b.type === "tool_use"; });
        if (!uses.length) return { text: text, truncated: r.stop_reason === "max_tokens" };
        return Promise.all(uses.map(function (u) {
          var t = tools.filter(function (x) { return x.name === u.name; })[0];
          var run = t ? Promise.resolve().then(function () { return t.execute(u.input || {}); }) : Promise.reject(new Error("outil inconnu : " + u.name));
          return run.then(function (out) { return { type: "tool_result", tool_use_id: u.id, content: typeof out === "string" ? out : JSON.stringify(out) }; },
            function (e) { return { type: "tool_result", tool_use_id: u.id, content: String((e && e.message) || e), is_error: true }; });
        })).then(function (results) { msgs.push({ role: "user", content: results }); return turn(); });
      });
    }
    return turn();
  }

  var AI = null;
  function sample(messages, opts) {
    opts = opts || {};
    var check = AI === null ? post("/api/llm/status", {}).then(function (s) { AI = !!s.ia; }) : Promise.resolve();
    return check.then(function () { return AI ? sampleWithAI(messages, opts) : sampleWithoutAI(messages); })
      .catch(function (e) { throw { code: (e && e.code) || "upstream_error", message: (e && e.message) || String(e) }; });
  }

  window.claude = { use: function (name) { return Promise.resolve(name === "mcp" ? MCP : name === "sample" ? sample : null); } };
})();
