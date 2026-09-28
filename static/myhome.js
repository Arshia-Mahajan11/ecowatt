/* EcoWatt - "My Home" tab: appliance calculator. No libraries; runs fully in the browser. */
(function () {
  "use strict";

  var KEY = "ecowatt-myhome-v1";
  var COLORS = ["var(--accent)", "var(--blue)", "var(--amber)", "var(--purple)", "var(--red)", "var(--indigo)", "var(--muted)"];

  // w = average watts while running, q = how many, h = hours per day
  var DEFAULTS = [
    { n: "Ceiling fan",           w: 75,   q: 1, h: 8 },
    { n: "LED bulb / tube",       w: 12,   q: 3, h: 6 },
    { n: "Refrigerator",          w: 60,   q: 1, h: 24, note: "Average draw over the day, since the compressor switches on and off." },
    { n: "Laptop",                w: 60,   q: 1, h: 5 },
    { n: "Phone charger",         w: 10,   q: 1, h: 2 },
    { n: "TV",                    w: 80,   q: 1, h: 2 },
    { n: "Wi-Fi router",          w: 10,   q: 1, h: 24 },
    { n: "Air conditioner",       w: 1200, q: 1, h: 0,   note: "Average draw of a 1.5 ton AC. Try 4 to 6 hours a day in summer." },
    { n: "Geyser / water heater", w: 2000, q: 1, h: 0.5 },
    { n: "Air cooler",            w: 150,  q: 1, h: 0 },
    { n: "Washing machine",       w: 500,  q: 1, h: 0.5 },
    { n: "Iron",                  w: 1000, q: 1, h: 0.2 },
    { n: "Water pump",            w: 750,  q: 1, h: 1 }
  ];

  var $ = function (id) { return document.getElementById(id); };
  if (!$("mh-rows")) return;

  function fresh() {
    return {
      tariff: 7,
      bill: "",
      items: DEFAULTS.map(function (d, i) { return { id: i + 1, n: d.n, w: d.w, q: d.q, h: d.h, note: d.note || "" }; })
    };
  }
  function load() {
    try {
      var s = JSON.parse(localStorage.getItem(KEY));
      return s && Array.isArray(s.items) ? s : null;
    } catch (e) { return null; }
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* storage blocked */ } }

  var state = load() || fresh();

  function num(v) { var n = parseFloat(v); return isFinite(n) && n > 0 ? n : 0; }
  function inr(v) { return "₹" + Math.round(v).toLocaleString("en-IN"); }
  function fmt(v) { return (Math.round(v * 10) / 10).toLocaleString("en-IN"); }
  function monthlyKwh(it) { return it.w * it.q * it.h / 1000 * 30; }

  var uid = 0;
  function field(labelText, value, step, onInput) {
    var wrap = document.createElement("div"); wrap.className = "field";
    var lab = document.createElement("label");
    var inp = document.createElement("input");
    inp.id = "mh-f" + (++uid);
    lab.htmlFor = inp.id; lab.textContent = labelText;
    inp.type = "number"; inp.min = "0"; inp.step = step; inp.value = value; inp.inputMode = "decimal";
    inp.addEventListener("input", function () { onInput(inp.value); });
    wrap.appendChild(lab); wrap.appendChild(inp);
    return wrap;
  }

  function buildRows() {
    var host = $("mh-rows");
    host.innerHTML = "";
    state.items.forEach(function (it) {
      var row = document.createElement("div"); row.className = "mh-row";

      var head = document.createElement("div"); head.className = "mh-row-head";
      var title = document.createElement("div"); title.className = "mh-row-title";
      var name = document.createElement("span"); name.className = "mh-name"; name.textContent = it.n;
      var rm = document.createElement("button");
      rm.type = "button"; rm.className = "btn ghost small"; rm.textContent = "Remove";
      rm.setAttribute("aria-label", "Remove " + it.n);
      rm.addEventListener("click", function () {
        state.items = state.items.filter(function (x) { return x.id !== it.id; });
        buildRows(); update();
      });
      title.appendChild(name); title.appendChild(rm);
      var cost = document.createElement("span"); cost.className = "mh-cost"; cost.id = "mh-cost-" + it.id;
      head.appendChild(title); head.appendChild(cost);

      var fields = document.createElement("div"); fields.className = "mh-fields";
      fields.appendChild(field("Watts", it.w, "1", function (v) { it.w = num(v); update(); }));
      fields.appendChild(field("How many", it.q, "1", function (v) { it.q = num(v); update(); }));
      fields.appendChild(field("Hours per day", it.h, "0.5", function (v) { it.h = num(v); update(); }));

      row.appendChild(head); row.appendChild(fields);
      if (it.note) {
        var note = document.createElement("div"); note.className = "mh-note"; note.textContent = it.note;
        row.appendChild(note);
      }
      host.appendChild(row);
    });
  }

  function update() {
    var rate = num(state.tariff);
    var total = 0;

    state.items.forEach(function (it) {
      var k = monthlyKwh(it); total += k;
      var c = $("mh-cost-" + it.id);
      if (c) c.textContent = inr(k * rate) + " / month";
    });

    var bill = total * rate;
    $("mh-k-cost").textContent = inr(bill);
    $("mh-hole-cost").textContent = inr(bill);
    $("mh-k-kwh").textContent = fmt(total);
    $("mh-k-day").textContent = fmt(total / 30);

    // Ranked by monthly units; top 6 shown, the rest grouped
    var ranked = state.items
      .map(function (it) { return { it: it, k: monthlyKwh(it) }; })
      .filter(function (x) { return x.k > 0; })
      .sort(function (a, b) { return b.k - a.k; });

    var slices = ranked.slice(0, 6).map(function (x) { return { n: x.it.n, k: x.k }; });
    var rest = ranked.slice(6).reduce(function (s, x) { return s + x.k; }, 0);
    if (rest > 0) slices.push({ n: "Everything else", k: rest });

    var legend = $("mh-legend"); legend.innerHTML = "";
    var stops = [], acc = 0;
    slices.forEach(function (s, i) {
      var pct = total ? s.k / total * 100 : 0;
      var col = COLORS[i % COLORS.length];
      stops.push(col + " " + acc + "% " + (acc + pct) + "%");
      acc += pct;

      var li = document.createElement("li");
      var dot = document.createElement("i"); dot.style.background = col;
      var nm = document.createElement("span"); nm.className = "name"; nm.textContent = s.n;
      var val = document.createElement("span"); val.className = "val"; val.textContent = inr(s.k * rate);
      var pc = document.createElement("span"); pc.className = "pct"; pc.textContent = Math.round(pct) + "%";
      li.appendChild(dot); li.appendChild(nm); li.appendChild(val); li.appendChild(pc);
      legend.appendChild(li);
    });
    $("mh-donut").style.background = stops.length ? "conic-gradient(" + stops.join(", ") + ")" : "";

    // Biggest cost + saving tip
    var topName = $("mh-k-top"), topSub = $("mh-k-top-sub"), tip = $("mh-tip");
    if (ranked.length && rate > 0) {
      topName.textContent = ranked[0].it.n;
      topSub.textContent = Math.round(ranked[0].k / total * 100) + "% of your estimate";

      // The tip skips always-on appliances (fridge, router), since you can't run them less.
      var adjustable = ranked.filter(function (x) { return x.it.h < 20; })[0];
      if (adjustable) {
        var a = adjustable.it;
        var hrs = Math.min(1, a.h);
        var saved = a.w * a.q / 1000 * hrs * 30 * rate;
        tip.textContent = a.n + " is the biggest cost you can control. Using it " + (hrs < 1 ? "a little" : "1 hour") +
          " less each day saves about " + inr(saved) + " a month.";
      } else {
        tip.textContent = "Most of your use is from appliances that stay on all day. Look for a more efficient model when you replace them.";
      }
    } else {
      topName.textContent = "-";
      topSub.textContent = "add hours to see";
      tip.textContent = "Set the hours for your appliances to see a saving tip.";
    }

    // Compare with the real bill
    var typed = num(state.bill), bm = $("mh-billmsg");
    if (typed > 0 && total > 0 && rate > 0) {
      var diff = (bill - typed) / typed * 100;
      if (Math.abs(diff) <= 15) {
        bm.textContent = "Your estimate is close to your real bill.";
      } else if (diff < 0) {
        bm.textContent = "Your estimate is " + Math.round(-diff) + "% below your bill. You may have missed an appliance, or your bill includes fixed charges and taxes.";
      } else {
        bm.textContent = "Your estimate is " + Math.round(diff) + "% above your bill. Some hours may be lower than you entered, or your rate per unit may be under ₹" + fmt(rate) + ".";
      }
    } else {
      bm.textContent = "Enter last month's bill above to see how close this estimate is.";
    }

    save();
  }

  /* ---------- Controls ---------- */
  $("mh-tariff").value = state.tariff;
  $("mh-bill").value = state.bill;
  $("mh-tariff").addEventListener("input", function (e) { state.tariff = num(e.target.value); update(); });
  $("mh-bill").addEventListener("input", function (e) { state.bill = e.target.value; update(); });

  $("mh-add").addEventListener("click", function () {
    var name = $("mh-newname").value.trim();
    var w = num($("mh-newwatts").value);
    var msg = $("mh-addmsg");
    if (!name || !w) { msg.textContent = "Enter a name and the watts (printed on the appliance label)."; return; }
    var id = state.items.reduce(function (m, x) { return Math.max(m, x.id); }, 0) + 1;
    state.items.push({ id: id, n: name, w: w, q: 1, h: 1, note: "" });
    $("mh-newname").value = ""; $("mh-newwatts").value = "";
    msg.textContent = name + " added. Set its hours above.";
    buildRows(); update();
  });

  $("mh-reset").addEventListener("click", function () {
    state = fresh();
    $("mh-tariff").value = state.tariff;
    $("mh-bill").value = "";
    $("mh-addmsg").textContent = "";
    buildRows(); update();
  });

  $("mh-copy").addEventListener("click", function () {
    var rate = num(state.tariff);
    var total = state.items.reduce(function (s, it) { return s + monthlyKwh(it); }, 0);
    var top = state.items
      .map(function (it) { return { n: it.n, c: monthlyKwh(it) * rate }; })
      .filter(function (x) { return x.c > 0; })
      .sort(function (a, b) { return b.c - a.c; })
      .slice(0, 3);
    var text = "My estimated monthly electricity bill: " + inr(total * rate) + " (" + fmt(total) + " units).\n" +
      top.map(function (x, i) { return (i + 1) + ". " + x.n + " - " + inr(x.c); }).join("\n") +
      "\nCheck yours on EcoWatt: " + location.origin;
    var msg = $("mh-copymsg");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () { msg.textContent = "Copied. Paste it in WhatsApp or Instagram."; },
        function () { msg.textContent = "Could not copy. Take a screenshot instead."; }
      );
    } else {
      msg.textContent = "Could not copy. Take a screenshot instead.";
    }
  });

  buildRows();
  update();
})();