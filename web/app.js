/* MANO web app. Plain JavaScript, no build step. */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === false || v == null) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? "" : v);
    }
    for (const child of children.flat()) if (child != null) node.append(child);
    return node;
  };

  let state = null;
  let sentThisVisit = false;
  let busy = false;

  // ---------- helpers ----------
  function timeOfDay(hour = new Date().getHours()) {
    if (hour >= 5 && hour < 11) return "morning";
    if (hour >= 11 && hour < 17) return "afternoon";
    if (hour >= 17 && hour < 21) return "evening";
    return "night";
  }

  function md(text) {
    const div = el("div", { class: "prose" });
    if (window.marked && window.DOMPurify) {
      div.innerHTML = DOMPurify.sanitize(marked.parse(String(text || ""), { breaks: true }));
      div.querySelectorAll("a[href]").forEach((a) => { a.target = "_blank"; a.rel = "noopener noreferrer"; });
    } else {
      String(text || "").split(/\n{2,}/).forEach((para) => div.append(el("p", { text: para })));
    }
    return div;
  }

  let toastTimer;
  function toast(message, bad = false) {
    const t = $("#toast");
    t.textContent = message;
    t.className = "toast" + (bad ? " bad" : "");
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, bad ? 6000 : 3200);
  }

  async function api(path, options = {}) {
    const opts = { credentials: "same-origin", ...options };
    if (opts.json !== undefined) {
      opts.method = opts.method || "POST";
      opts.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
      opts.body = JSON.stringify(opts.json);
      delete opts.json;
    }
    const res = await fetch(path, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Something went wrong (${res.status}).`);
    return data;
  }

  function setState(next) {
    if (next) state = next;
    render();
  }

  // ---------- rendering ----------
  function render() {
    if (!state) return;
    const g = state.greeting;
    $("#hello-title").textContent = g.headline;
    $("#hello-sub").textContent = g.subline;
    document.title = state.profile.name ? `MANO for ${state.profile.name.split(" ")[0]}` : "MANO";
    renderThread();
    renderRail();
    renderFlags();
  }

  function stepsBlock(steps) {
    const box = el("details", { class: "steps" },
      el("summary", { text: `How I worked this out (${steps.length} step${steps.length > 1 ? "s" : ""})` }),
      el("ol", {}, steps.map((s) => el("li", {},
        el("span", { class: s.ok ? "tick" : "", text: s.ok ? "✓" : "!" }),
        el("span", {}, `${(s.label || "").replace(/^\S+\s/, "")}: ${s.summary}`,
          s.thought ? el("span", { class: "step-why", text: s.thought }) : null)))));
    return box;
  }

  function manoMessage(contentNode, steps, speakable) {
    const li = $("#tpl-mano").content.firstElementChild.cloneNode(true);
    const body = $(".body", li);
    if (steps && steps.length) body.append(stepsBlock(steps));
    body.append(contentNode);
    if (speakable && "speechSynthesis" in window) {
      body.append(el("button", { type: "button", class: "speak", text: "Read aloud", onclick: () => speak(speakable) }));
    }
    return li;
  }

  function helloMessage() {
    return manoMessage(md(state.greeting.bubble));
  }

  const ONBOARDING_HINT = {
    name: "Type your name",
    goals: "What you're working toward",
    interests: "Topics you'd like updates on",
    stressors: "What overwhelms you, or type skip",
  };

  function showHello() {
    if (sentThisVisit) return false;
    if (state.onboarding === "done") return true;
    return state.onboarding === "name" && !state.messages.length;
  }

  const KIND = {
    add_task: { what: "Add to your week", yes: "Add it", done: "Added to your week." },
    schedule_block: { what: "Set aside time", yes: "Block it", done: "Time blocked." },
    draft_email: { what: "Draft an email", yes: "Save draft", done: "Draft saved. MANO never sends it." },
    research: { what: "Look this up", yes: "Search now", done: "Searched. The results are in the chat." },
  };

  function proposalItem(item) {
    const p = item.payload, k = KIND[item.kind] || { what: "Suggestion", yes: "Approve", done: "Done." };
    let title = p.title || p.subject || p.query || "";
    let meta = null;
    if (item.kind === "add_task") meta = p.due_at ? `Due ${p.due_at.replace("T", " at ")}` : "No date";
    if (item.kind === "schedule_block") meta = `${p.start_at.replace("T", " ")} to ${p.end_at.slice(11)}`;
    const li = el("li", { class: "proposal" },
      el("p", { class: "what", text: k.what }),
      el("p", { class: "title", text: title }),
      meta ? el("p", { class: "meta", text: meta }) : null,
      item.kind === "draft_email" ? el("details", {}, el("summary", { text: "Read the draft" }), el("pre", { text: p.body })) : null,
      el("div", { class: "actions" },
        el("button", { type: "button", class: "primary", text: k.yes, onclick: (e) => decide(item.id, "approve", e.target, k.done) }),
        el("button", { type: "button", class: "quiet", text: "Not now", onclick: (e) => decide(item.id, "dismiss", e.target) })));
    return li;
  }

  function renderThread() {
    const thread = $("#thread");
    thread.replaceChildren();
    for (const m of state.messages) {
      if (m.role === "user") thread.append(el("li", { class: "msg you" }, el("div", { class: "body", text: m.content })));
      else thread.append(manoMessage(md(m.content), m.steps, m.content));
    }
    if (showHello()) thread.append(helloMessage());
    const fresh = freshProposals();
    if (fresh.length) {
      thread.append(manoMessage(el("div", {},
        el("p", { class: "working", text: fresh.length > 1 ? "If you'd like, I can add these:" : "If you'd like, I can add this:" }),
        el("ul", { class: "proposals" }, fresh.map(proposalItem)))));
    }
  }

  // Suggestions show once, right under the reply that made them. After you move on, they wait quietly in Your week.
  function freshProposals() {
    const lastMano = [...state.messages].reverse().find((m) => m.role === "assistant");
    const since = lastMano ? lastMano.created_at : "";
    return state.proposals.filter((p) => p.created_at >= since);
  }

  function renderRail() {
    const fresh = new Set(freshProposals().map((p) => p.id));
    const waiting = state.proposals.filter((p) => !fresh.has(p.id));
    $("#rail-proposals").replaceChildren(...waiting.map(proposalItem));
    $("#rail-waiting").hidden = !waiting.length;
    $("#rail-waiting-summary").textContent =
      `${waiting.length} suggestion${waiting.length === 1 ? "" : "s"} you haven't decided on`;
    const now = new Date();
    const tasks = $("#tasks");
    tasks.replaceChildren();
    for (const c of state.radar.conflicts) {
      tasks.append(el("li", { class: "conflict", text: `${c.first} overlaps ${c.second}, ${c.when}` }));
    }
    if (!state.tasks.length) tasks.append(el("li", {}, el("p", { class: "empty", text: "Nothing yet. Add what's coming up, or just tell MANO about your week." })));
    for (const t of state.tasks) {
      const due = t.due_at ? new Date(t.due_at) : null;
      const cls = !due ? "" : due < now ? "late" : t.due_at.slice(0, 10) === localDate(now) ? "today" : "";
      const when = !due ? "No date" : cls === "late" ? `Was due ${t.due_label}` : cls === "today" ? `Today, ${t.due_label.split(", ").pop()}` : t.due_label;
      const id = `task-${t.id}`;
      tasks.append(el("li", { class: `task ${cls}` },
        el("input", { type: "checkbox", id, "aria-label": `Mark ${t.title} done`, onchange: () => markDone(t.id, t.title) }),
        el("label", { for: id }, el("span", { text: t.title }), el("span", { class: "when", text: when }))));
    }
    const blocks = $("#blocks");
    blocks.replaceChildren(...state.blocks.map((b) => el("li", { class: "block" },
      el("span", { text: `${b.title}, ${b.start_label} to ${b.end_time}` }),
      el("button", { type: "button", text: "Remove", onclick: () => removeBlock(b.id) }))));
    $("#rail-blocks").hidden = !state.blocks.length;
    const drafts = $("#drafts");
    drafts.replaceChildren(...state.drafts.map((d) => el("details", { class: "draft" }, el("summary", { text: d.subject }), el("pre", { text: d.body }))));
    $("#rail-drafts").hidden = !state.drafts.length;
  }

  function localDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }

  function renderFlags() {
    const f = state.flags;
    const input = $("#composer-input"), send = $("#send");
    const onboarding = state.onboarding !== "done";
    input.disabled = !f.ai;
    send.disabled = !f.ai || busy;
    input.placeholder = onboarding ? ONBOARDING_HINT[state.onboarding] : "What's on your mind?";
    $(".quick").hidden = onboarding;
    let fine = $("#listen").checked
      ? "Just listen is on: MANO won't plan or suggest anything unless you ask for help."
      : "Runs on NVIDIA Nemotron through Nebius Token Factory. Nothing is saved or sent without your OK.";
    if (onboarding) fine = "Getting to know you. Your answers go to About you, where you can change them anytime.";
    else if (!f.ai) fine = "MANO's AI isn't connected yet. Add NEBIUS_API_KEY to .env and restart.";
    else if (f.mode === "demo") fine += ` ${f.calls_left} AI requests left today on this demo.`;
    $("#fineprint").textContent = fine;
    document.querySelectorAll('[data-action="briefing"], [data-open="opps"].chip').forEach((b) => {
      b.disabled = !(f.ai && f.web);
      b.title = f.web ? "" : "Web search isn't connected (TAVILY_API_KEY).";
    });
  }

  // ---------- talking ----------
  function scrollToEnd() {
    requestAnimationFrame(() => window.scrollTo({ top: document.body.scrollHeight, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }));
  }

  function thinkingMessage(label) {
    const live = el("ul", { class: "live-steps" });
    const status = el("p", { class: "working", text: label });
    const li = manoMessage(el("div", {}, status, live));
    li.classList.add("thinking");
    return { li, live, status };
  }

  function setBusy(on) {
    busy = on;
    $("#send").disabled = on || !(state && state.flags.ai);
    $("#composer-input").setAttribute("aria-busy", on ? "true" : "false");
  }

  async function send(text) {
    text = text.trim();
    if (!text || busy) return;
    setBusy(true);
    sentThisVisit = true;
    const thread = $("#thread");
    renderThread();
    thread.append(el("li", { class: "msg you" }, el("div", { class: "body", text })));
    const { li, live, status } = thinkingMessage("Thinking about this with you…");
    thread.append(li);
    scrollToEnd();
    const rows = {};
    try {
      const res = await fetch("/api/chat", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, listen: $("#listen").checked }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Something went wrong (${res.status}).`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let cut;
        while ((cut = buffer.indexOf("\n\n")) >= 0) {
          const chunk = buffer.slice(0, cut);
          buffer = buffer.slice(cut + 2);
          const event = (chunk.match(/^event: (.*)$/m) || [])[1];
          const data = JSON.parse((chunk.match(/^data: (.*)$/m) || [])[1] || "{}");
          if (event === "skill_start") {
            status.textContent = "Working on it…";
            const row = el("li", {}, el("span", { class: "busy", text: "✦" }), el("span", {}, `${data.doing}…`, data.thought ? el("span", { class: "step-why", text: data.thought }) : null));
            rows[data.skill] = row;
            live.append(row);
            scrollToEnd();
          } else if (event === "skill_done") {
            const row = rows[data.skill];
            if (row) row.replaceChildren(el("span", { class: data.ok ? "tick" : "", text: data.ok ? "✓" : "!" }), el("span", {}, `${data.doing}: ${data.summary}`));
            status.textContent = "Putting it together…";
          } else if (event === "done") {
            setState(data.state);
            scrollToEnd();
            if (spokenTurn) {
              const last = [...state.messages].reverse().find((m) => m.role === "assistant");
              if (last) speak(last.content);
            }
          } else if (event === "error") {
            throw new Error(data.message);
          }
        }
      }
    } catch (err) {
      li.classList.remove("thinking");
      status.textContent = err.message;
      toast(err.message, true);
      try { setState(await api("/api/state")); } catch (_) { /* keep what we have */ }
    } finally {
      setBusy(false);
      spokenTurn = false;
    }
  }

  async function briefing() {
    if (busy) return;
    setBusy(true);
    sentThisVisit = true;
    renderThread();
    const { li } = thinkingMessage("Reading this week's news on what you care about…");
    $("#thread").append(li);
    scrollToEnd();
    try {
      setState(await api("/api/briefing", { method: "POST" }));
      scrollToEnd();
    } catch (err) {
      li.remove();
      toast(err.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function decide(id, decision, button, doneText) {
    button.disabled = true;
    try {
      const res = await api(`/api/proposals/${id}/${decision}`, { method: "POST" });
      setState(res.state);
      toast(decision === "approve" ? doneText : "Okay, set aside.");
    } catch (err) {
      button.disabled = false;
      toast(err.message, true);
    }
  }

  async function markDone(id, title) {
    try {
      setState(await api(`/api/tasks/${id}/done`, { method: "POST" }));
      toast(`Nice. ${title} is done.`);
    } catch (err) { toast(err.message, true); }
  }

  async function removeBlock(id) {
    try { setState(await api(`/api/blocks/${id}`, { method: "DELETE" })); toast("Removed."); }
    catch (err) { toast(err.message, true); }
  }

  // ---------- voice ----------
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null, listening = false, spokenTurn = false;

  function plainForSpeech(text) {
    let t = String(text || "")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")          // links -> their words
      .replace(/https?:\/\/\S+/g, "")
      .replace(/[*_#>`]/g, "")
      .replace(/^\s*[-•]\s+/gm, "")
      .replace(/^\s*\d+\.\s+/gm, "")
      .replace(/\p{Extended_Pictographic}/gu, "")
      .replace(/([.!?:])\s*\n{2,}/g, "$1 ").replace(/\n{2,}/g, ". ").replace(/\s+/g, " ").trim();
    if (t.length > 900) {                                    // long plans: read the opening, the rest stays on screen
      const cut = t.slice(0, 900);
      t = cut.slice(0, Math.max(cut.lastIndexOf(". "), 400) + 1) + " The rest is on your screen.";
    }
    return t;
  }

  function pickVoice() {
    const voices = speechSynthesis.getVoices().filter((v) => v.lang && v.lang.startsWith("en"));
    const liked = ["Samantha", "Ava", "Allison", "Google US English", "Karen", "Moira", "Daniel"];
    return liked.map((n) => voices.find((v) => v.name.includes(n))).find(Boolean) || voices[0] || null;
  }

  function speak(text) {
    if (!("speechSynthesis" in window)) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(plainForSpeech(text));
    const v = pickVoice();
    if (v) u.voice = v;
    u.rate = 1.02;
    speechSynthesis.speak(u);
  }

  function setListening(on) {
    listening = on;
    const mic = $("#mic");
    mic.classList.toggle("listening", on);
    mic.setAttribute("aria-pressed", String(on));
    mic.setAttribute("aria-label", on ? "Stop listening" : "Talk to MANO");
    $("#composer-input").placeholder = on ? "Listening… tap the mic when you're done" : (state && state.onboarding !== "done" ? ONBOARDING_HINT.name : "What's on your mind?");
    $("#fineprint").textContent = on
      ? "Listening. Your browser turns your voice into text (Safari uses Apple's speech service, Chrome uses Google's)."
      : $("#fineprint").textContent;
    if (!on && state) renderFlags();
  }

  // Keeps listening through pauses until you tap the mic again (or go quiet for a while).
  const SILENCE_MS = 8000;
  let heard = "", silenceTimer = null, userDone = false;

  function finishListening() {
    userDone = true;
    clearTimeout(silenceTimer);
    try { recognizer && recognizer.stop(); } catch (_) { /* already stopped */ }
  }

  function startRecognizer() {
    const input = $("#composer-input");
    recognizer = new Recognition();
    recognizer.lang = navigator.language || "en-US";
    recognizer.interimResults = true;
    recognizer.continuous = true;
    let sessionFinal = "";
    recognizer.onresult = (e) => {
      let interim = "";
      sessionFinal = "";
      for (let i = 0; i < e.results.length; i++) {
        if (e.results[i].isFinal) sessionFinal += " " + e.results[i][0].transcript;
        else interim += " " + e.results[i][0].transcript;
      }
      input.value = `${heard} ${sessionFinal} ${interim}`.replace(/\s+/g, " ").trim();
      clearTimeout(silenceTimer);
      silenceTimer = setTimeout(finishListening, SILENCE_MS);
    };
    recognizer.onerror = (e) => {
      if (e.error === "no-speech" || e.error === "aborted") return;  // a pause, not a problem
      userDone = true;
      const why = e.error === "not-allowed" || e.error === "service-not-allowed"
        ? "Allow microphone access for this site in your browser settings, then try again."
        : `Voice input stopped (${e.error}).`;
      toast(why, true);
    };
    recognizer.onend = () => {
      heard = input.value.trim();                 // keep everything said so far
      if (!userDone) {                            // the browser stopped on its own: keep going
        try { startRecognizer(); return; } catch (_) { /* fall through and send */ }
      }
      clearTimeout(silenceTimer);
      setListening(false);
      const said = input.value.trim();
      heard = "";
      if (said) {
        input.value = "";
        spokenTurn = true;
        send(said);
      }
    };
    recognizer.start();
  }

  // Sending (button or Enter) while the mic is on: stop listening quietly, don't send twice or refill the box.
  function cancelListening() {
    if (!listening) return;
    userDone = true;
    clearTimeout(silenceTimer);
    const r = recognizer;
    recognizer = null;
    if (r) {
      r.onresult = null;
      r.onend = null;
      try { r.abort(); } catch (_) { /* already stopped */ }
    }
    heard = "";
    setListening(false);
  }

  function toggleListening() {
    if (listening) { finishListening(); return; }
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    heard = $("#composer-input").value.trim();     // you can start typing, then keep talking
    userDone = false;
    try {
      startRecognizer();
      setListening(true);
      silenceTimer = setTimeout(finishListening, SILENCE_MS * 2);  // never left on by accident
    } catch (err) { toast("Voice input couldn't start. Try again in a moment.", true); }
  }

  // ---------- sheets, menu, rail ----------
  function openSheet(id) {
    $("#menu-list").hidden = true;
    $("#menu-button").setAttribute("aria-expanded", "false");
    if (id === "rail") return toggleRail(true);
    if (id === "about") renderAbout();
    if (id === "opps") renderKinds();
    const dlg = document.getElementById(id);
    if (!dlg.open) dlg.showModal();
  }

  function toggleRail(open) {
    const rail = $("#rail");
    rail.classList.toggle("open", open);
    $(".rail-toggle").setAttribute("aria-expanded", String(open));
    if (open) $(".close", rail).focus();
  }

  function renderAbout() {
    const form = $("#about-form");
    form.replaceChildren(
      ...state.profile_fields.map((f) => {
        const field = f.limit > 300
          ? el("textarea", { class: "field", name: f.key, maxlength: f.limit, rows: 3 })
          : el("input", { name: f.key, maxlength: f.limit });
        field.value = state.profile[f.key] || "";
        return el("label", {}, f.label, field);
      }),
      el("button", { type: "submit", class: "primary", text: "Save" }));
  }

  function renderKinds() {
    const box = $("#kinds");
    if (box.childElementCount) return;
    Object.entries(state.opportunity_kinds).forEach(([key, label], i) => {
      box.append(el("label", {}, el("input", { type: "radio", name: "kind", value: key, checked: i === 0 }), el("span", { text: label })));
    });
  }

  function renderOpportunities(result) {
    const out = $("#opps-results");
    out.replaceChildren();
    if (!result.items.length) {
      out.append(el("p", { class: "note", text: "Nothing specific turned up. Try a different focus." }));
    }
    for (const item of result.items) {
      const meta = [item.organization, item.type, item.location].filter(Boolean).join(", ");
      out.append(el("article", { class: "opp" },
        el("h3", {}, el("a", { href: item.url, target: "_blank", rel: "noopener noreferrer", text: item.title })),
        meta ? el("p", { class: "meta", text: meta }) : null,
        el("p", { class: "meta" }, item.deadline ? el("span", { class: "deadline", text: `Deadline ${item.deadline}` }) : "Deadline: check the site"),
        item.why_it_fits ? el("p", { class: "why", text: item.why_it_fits }) : null,
        el("div", { class: "actions" }, el("button", {
          type: "button", class: "quiet", text: "Track this", onclick: async (e) => {
            e.target.disabled = true;
            try {
              const res = await api("/api/opportunities/track", { json: { item } });
              setState(res.state);
              e.target.textContent = res.added ? "Waiting for your OK in chat" : "Already tracked";
            } catch (err) { e.target.disabled = false; toast(err.message, true); }
          },
        }))));
    }
    out.append(el("p", { class: "searched", text: `Searched for: ${result.query}` }));
  }

  async function runAction(action) {
    $("#menu-list").hidden = true;
    $("#menu-button").setAttribute("aria-expanded", "false");
    try {
      if (action === "fresh-chat") {
        setState(await api("/api/fresh-chat", { method: "POST" }));
        sentThisVisit = false; render(); toast("Fresh chat. Your profile and week are still here.");
      } else if (action === "sample-week") {
        if (state.messages.length || state.tasks.length) {
          if (!confirm("Replace everything with a fictional sample week?")) return;
        }
        sentThisVisit = false;
        setState(await api("/api/sample-week", { method: "POST" }));
        document.querySelectorAll("dialog[open]").forEach((d) => d.close());
        toast("Loaded a fictional student week.");
      } else if (action === "erase") {
        if (!confirm("Erase your profile, week and conversation? This can't be undone.")) return;
        sentThisVisit = false;
        setState(await api("/api/erase", { method: "POST" }));
        toast("Everything is erased.");
      } else if (action === "import") {
        $("#import-file").click();
      } else if (action === "briefing") {
        briefing();
      }
    } catch (err) { toast(err.message, true); }
  }

  // ---------- wiring ----------
  function wire() {
    document.body.dataset.time = timeOfDay();

    const input = $("#composer-input");
    const grow = () => { input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 220)}px`; };
    input.addEventListener("input", grow);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("#composer").requestSubmit(); }
    });
    $("#listen").addEventListener("change", () => state && renderFlags());
    if (Recognition) {
      $("#mic").hidden = false;
      $("#mic").addEventListener("click", toggleListening);
    }
    if ("speechSynthesis" in window) speechSynthesis.getVoices();  // loads the voice list early
    input.addEventListener("input", () => { if ("speechSynthesis" in window) speechSynthesis.cancel(); });
    $("#composer").addEventListener("submit", (e) => {
      e.preventDefault();
      const text = input.value;
      if (!text.trim()) return;
      const wasListening = listening;
      cancelListening();
      if (wasListening) spokenTurn = true;
      input.value = ""; grow();
      send(text);
    });

    document.addEventListener("click", (e) => {
      const open = e.target.closest("[data-open]");
      if (open && !open.disabled) { openSheet(open.dataset.open); return; }
      const close = e.target.closest("[data-close]");
      if (close) { toggleRail(false); return; }
      const ask = e.target.closest("[data-ask]");
      if (ask) { send(ask.dataset.ask); return; }
      const act = e.target.closest("[data-action]");
      if (act && !act.disabled) { runAction(act.dataset.action); return; }
      if (!e.target.closest(".menu")) { $("#menu-list").hidden = true; $("#menu-button").setAttribute("aria-expanded", "false"); }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { toggleRail(false); $("#menu-list").hidden = true; }
    });
    $("#menu-button").addEventListener("click", () => {
      const list = $("#menu-list");
      list.hidden = !list.hidden;
      $("#menu-button").setAttribute("aria-expanded", String(!list.hidden));
      if (!list.hidden) list.firstElementChild.focus();
    });

    $("#task-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      try {
        setState(await api("/api/tasks", { json: { title: f.get("title"), due_at: f.get("due") || null } }));
        e.target.reset();
        toast("Added to your week.");
      } catch (err) { toast(err.message, true); }
    });

    $("#about-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const values = Object.fromEntries(new FormData(e.target));
      try {
        setState(await api("/api/profile", { method: "PUT", json: values }));
        $("#about").close();
        toast(values.name ? `Thanks, ${values.name.split(" ")[0]}. I'll keep this in mind.` : "Saved.");
      } catch (err) { toast(err.message, true); }
    });

    $("#opps-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      const go = $("#opps-go");
      go.disabled = true; go.textContent = "Searching…";
      $("#opps-results").replaceChildren(el("p", { class: "working", text: "Searching the web and checking what fits you. This takes about half a minute." }));
      try {
        renderOpportunities(await api("/api/opportunities", { json: { kind: f.get("kind"), focus: f.get("focus") } }));
        setState(await api("/api/state"));
      } catch (err) {
        $("#opps-results").replaceChildren(el("p", { class: "note", text: err.message }));
      } finally { go.disabled = false; go.textContent = "Find for me"; }
    });

    $("#import-file").addEventListener("change", async (e) => {
      const file = e.target.files[0];
      e.target.value = "";
      if (!file) return;
      if (!confirm("Replace everything here with this backup?")) return;
      try {
        const res = await api("/api/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: await file.text() });
        sentThisVisit = false;
        setState(res.state);
        toast(`Restored ${res.counts.commitments} commitments and ${res.counts.messages} messages.`);
      } catch (err) { toast(err.message, true); }
    });
  }

  // A friend's hello: start with the instant greeting, then swap in MANO's own check-in when it's ready.
  async function checkIn() {
    if (!state || state.onboarding !== "done" || !state.flags.ai) return;
    try {
      const { text } = await api("/api/checkin");
      if (text && !sentThisVisit) {
        state.greeting.bubble = text;
        renderThread();
      }
    } catch (_) { /* the instant greeting stays */ }
  }

  async function boot() {
    wire();
    try {
      setState(await api("/api/state"));
      checkIn();
    } catch (err) {
      toast("MANO couldn't load. Check that the server is running, then reload.", true);
    }
  }

  boot();
})();
