const map = document.querySelector("#map");
const species = document.querySelector("#species");
const inspector = document.querySelector("#inspector");
const rankings = document.querySelector("#rankings");
const svgNS = "http://www.w3.org/2000/svg";
const methodNames = {herbgap: "HerbGap", nearest: "Nearest target report", activity: "Highest background activity"};
const places = [["Aberystwyth", -4.0829, 52.4153], ["Cardiff", -3.1791, 51.4816], ["Shrewsbury", -2.754, 52.707], ["Exeter", -3.5339, 50.7184], ["Llanwrtyd Wells", -3.6388, 52.1055]];
const number = new Intl.NumberFormat("en-GB");
const keyOf = ([x, y]) => x + "," + y;
let audit;
let layer = "coverage";
let selected;
let cellElements = new Map();

function svgElement(tag, attributes) {
  const element = document.createElementNS(svgNS, tag);
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
  return element;
}

function target() {
  return audit.species[species.value];
}

function cellName([x, y]) {
  return "Cell " + x + " / " + y;
}

function explanation([, , count, days]) {
  if (count > 0) return "The target was reported in this cell in 2024.";
  if (days === 0) return "This dataset has no background reporting days here. The target’s status is unknown.";
  if (days < 3) return "Background reporting was sparse. The target’s status is unknown.";
  return "Other plants were reported here on multiple dates. The target remains unreported in these records.";
}

function selectCell(cell, focus = false) {
  selected = keyOf(cell);
  for (const [key, element] of cellElements) {
    const active = key === selected;
    element.classList.toggle("selected", active);
    element.setAttribute("aria-pressed", active);
    element.setAttribute("tabindex", active ? 0 : -1);
  }
  for (const button of rankings.querySelectorAll("button")) {
    button.setAttribute("aria-current", button.dataset.cell === selected ? "true" : "false");
  }
  const [, , count, days, nearby, nearest] = cell;
  const shortlistRank = target().shortlist.findIndex(item => keyOf(item) === selected) + 1;
  inspector.innerHTML = '<h3 id="inspect-title">' + cellName(cell) + '</h3><dl class="facts">' +
    '<div><dt>Target reports</dt><dd>' + count + '</dd></div>' +
    '<div><dt>Background days</dt><dd>' + days + '</dd></div>' +
    '<div><dt>Nearby target cells</dt><dd>' + (nearby ?? "–") + '</dd></div></dl>' +
    '<p class="inspector-description">' + explanation(cell) +
    (shortlistRank ? " Shortlist #" + shortlistRank + ". Nearest recorded cell is " + nearest + " km away." : "") + '</p>';
  if (focus) cellElements.get(selected)?.focus();
}

function colour(count, days, shortlisted) {
  if (count) return "#c5e3ab";
  if (layer === "sightings") return "#2d453b";
  if (shortlisted) return "#a4773b";
  if (days >= 3) return "#699379";
  if (days) return "#456957";
  return "#2d453b";
}

function renderMap(item, lookup) {
  const [west, south, east, north] = audit.view;
  map.setAttribute("viewBox", [west, -north, east - west, north - south].join(" "));
  map.replaceChildren();
  cellElements = new Map();
  const land = svgElement("path", {class: "coast", "fill-rule": "evenodd",
    d: audit.coast.flatMap(polygon => polygon.map(ring => "M" + ring.map(([x, y]) => x + "," + -y).join(" L") + " Z")).join(" ")});
  map.append(land);
  const top = new Set(item.shortlist.map(keyOf));
  const size = audit.cellKm;
  for (const cell of item.cells) {
    const [x, y, count, days] = cell;
    const key = keyOf(cell);
    const shortlisted = layer === "coverage" && top.has(key);
    const label = cellName(cell) + ", " + count + " target reports, " + days + " background days" + (shortlisted ? ", shortlisted" : "");
    const rect = svgElement("rect", {
      x: x * size, y: -(y + 1) * size, width: size, height: size,
      class: "cell" + (shortlisted ? " priority" : ""), fill: colour(count, days, shortlisted),
      role: "button", tabindex: -1, "aria-label": label,
    });
    const title = svgElement("title", {});
    title.textContent = label;
    rect.append(title);
    rect.addEventListener("click", () => selectCell(cell));
    rect.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectCell(cell);
      }
      const direction = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowDown: [0, -1], ArrowUp: [0, 1]}[event.key];
      if (direction) {
        event.preventDefault();
        const next = lookup.get(keyOf([x + direction[0], y + direction[1]]));
        if (next) selectCell(next, true);
      }
    });
    cellElements.set(key, rect);
    map.append(rect);
  }
  const scale = Math.cos(52 * Math.PI / 180);
  for (const [name, lon, lat] of places) {
    const x = 6371.0088 * lon * Math.PI / 180 * scale;
    const y = -6371.0088 * Math.sin(lat * Math.PI / 180) / scale;
    const dot = svgElement("circle", {cx: x, cy: y, r: 2, fill: "#f2f3e8", "pointer-events": "none"});
    const label = svgElement("text", {x: x + 4, y: y - 4, class: "place"});
    label.textContent = name;
    map.append(dot, label);
  }
}

function renderAtlas() {
  const item = target();
  const lookup = new Map(item.cells.map(cell => [keyOf(cell), cell]));
  renderMap(item, lookup);
  rankings.replaceChildren();
  document.querySelector("#shortlist-meta").textContent = item.shortlist.length + " of " + item.eligible + " eligible cells · " + item.name;
  item.shortlist.forEach((coords, index) => {
    const cell = lookup.get(keyOf(coords));
    const row = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "rank-button";
    button.dataset.cell = keyOf(coords);
    button.innerHTML = '<span class="rank-num">' + String(index + 1).padStart(2, "0") + '</span><strong>' +
      cellName(coords) + '</strong><span class="rank-meta">' + cell[3] + ' days</span>';
    button.addEventListener("click", () => selectCell(cell));
    row.append(button);
    rankings.append(row);
  });
  selectCell(lookup.get(selected) ?? lookup.get(keyOf(item.shortlist[0] ?? item.cells[0])));
  document.querySelectorAll(".legend [data-coverage], .legend span:has(.priority)").forEach(item => {
    item.hidden = layer === "sightings";
  });
}

function renderBenchmark() {
  const results = document.querySelector("#results");
  for (const item of Object.values(audit.species)) {
    const article = document.createElement("article");
    article.className = "result";
    const rows = Object.entries(item.benchmark).map(([method, outcome]) =>
      "<tr><th scope='row'>" + methodNames[method] + "</th><td>" + outcome.hits + " / " + outcome.selected +
      "</td><td>" + outcome.anyReporting + " / " + outcome.selected + "</td></tr>").join("");
    article.innerHTML = "<h3>" + item.name + "</h3><em>" + item.latin + "</em>" +
      "<table><thead><tr><th>Method</th><th>Target reported</th><th>Any reporting</th></tr></thead><tbody>" + rows + "</tbody></table>";
    results.append(article);
  }
  const counts = audit.counts;
  document.querySelector("#record-counts").textContent = "Records used after filters: " + number.format(counts["2024"].used) +
    " in 2024 and " + number.format(counts["2025"].used) + " in 2025.";
}

function downloadShortlist() {
  const item = target();
  const lookup = new Map(item.cells.map(cell => [keyOf(cell), cell]));
  const rows = ["rank,species,cell_x,cell_y,center_lat,center_lon,target_reports_2024,background_days_2024,nearby_target_cells,nearest_target_km,score"];
  item.shortlist.forEach((coords, index) => {
    const [x, y, count, days, nearby, distance, score] = lookup.get(keyOf(coords));
    const scale = Math.cos(52 * Math.PI / 180);
    const lon = (x + 0.5) * audit.cellKm / (6371.0088 * scale) * 180 / Math.PI;
    const lat = Math.asin((y + 0.5) * audit.cellKm * scale / 6371.0088) * 180 / Math.PI;
    rows.push([index + 1, item.latin, x, y, lat.toFixed(4), lon.toFixed(4), count, days, nearby, distance, score].join(","));
  });
  const href = URL.createObjectURL(new Blob([rows.join("\n") + "\n"], {type: "text/csv;charset=utf-8"}));
  const link = document.createElement("a");
  link.href = href;
  link.download = "herbgap-" + item.name.toLowerCase().replaceAll(" ", "-") + ".csv";
  link.click();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

try {
  const response = await fetch("./data/audit.json");
  if (!response.ok) throw new Error("Could not load the field records.");
  audit = await response.json();
  renderAtlas();
  renderBenchmark();
  document.querySelector("#loading").hidden = true;
  species.addEventListener("change", () => {
    selected = undefined;
    renderAtlas();
  });
  for (const button of document.querySelectorAll("[data-mode]")) {
    button.addEventListener("click", () => {
      layer = button.dataset.mode;
      document.querySelectorAll("[data-mode]").forEach(other => other.setAttribute("aria-pressed", other === button));
      renderAtlas();
    });
  }
  document.querySelector("#export").addEventListener("click", downloadShortlist);
} catch (error) {
  document.querySelector("#loading").textContent = "Field records could not load. Serve the app with a local HTTP server and refresh.";
  console.error(error);
}
