from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

svg = ROOT / "custom_components/eink_dashboard/svg_render.py"
s = svg.read_text()
old = "    _build_sensor_context,\n    _build_separator_context,\n    _build_tile_context,"
new = "    _build_sensor_context,\n    _build_separator_context,\n    _build_sph_stundenplan_context,\n    _build_sph_stundenplan_grid_context,\n    _build_sph_stundenplan_tag_context,\n    _build_tile_context,"
if old not in s:
    raise SystemExit("svg_render import anchor not found")
s = s.replace(old, new, 1)
old = "    WidgetType.WEATHER: _build_weather_context,\n}"
new = "    WidgetType.WEATHER: _build_weather_context,\n    \"sph_stundenplan\": _build_sph_stundenplan_context,\n    \"sph_stundenplan_tag\": _build_sph_stundenplan_tag_context,\n    \"sph_stundenplan_grid\": _build_sph_stundenplan_grid_context,\n}"
if old not in s:
    raise SystemExit("svg_render registry anchor not found")
svg.write_text(s.replace(old, new, 1))

editor = ROOT / "custom_components/eink_dashboard/frontend/src/eink-dashboard-editor.ts"
s = editor.read_text()
anchor = "  graph: {\n    label: \"Graph\","
start = s.find(anchor)
if start < 0:
    raise SystemExit("editor graph anchor not found")
end = s.find("\n  },\n};\n\n// ── ha-form schema", start)
if end < 0:
    raise SystemExit("editor registry end not found")
insert = '''\n  sph_stundenplan: {\n    label: "SPH Stundenplan",\n    description: "Mehrere Schultage untereinander",\n    icon: "mdi:school",\n    defaults: { type: "sph_stundenplan", entity: "", x: 24, y: 0, w: 600, days: 5 },\n  },\n  sph_stundenplan_tag: {\n    label: "SPH Stundenplan Tag",\n    description: "Nur der heutige Stundenplan",\n    icon: "mdi:school-outline",\n    defaults: { type: "sph_stundenplan_tag", entity: "", x: 24, y: 0, w: 600 },\n  },\n  sph_stundenplan_grid: {\n    label: "SPH Stundenplan Grid",\n    description: "Kompletter Stundenplan über die volle Displaybreite",\n    icon: "mdi:view-grid-outline",\n    defaults: { type: "sph_stundenplan_grid", entity: "", x: 0, y: 0, h: 648 },\n  },'''
s = s[:end+5] + insert + s[end+5:]

schema_anchor = "export const SCHEMAS: Record<\n  string,\n  (d: DisplayConfig) => HaFormSchema[]\n> = {"
pos = s.find(schema_anchor)
if pos < 0:
    raise SystemExit("schema map not found")
end_schema = s.find("\n};", pos)
if end_schema < 0:
    raise SystemExit("schema map end not found")
schema_insert = '''\n  sph_stundenplan: (d) => [\n    identitySection(),\n    { name: "entity", selector: { entity: {} } },\n    { name: "days", default: 5, selector: { number: { min: 1, max: 7, step: 1, mode: "box" } } },\n    ...posXYWH(d),\n  ],\n  sph_stundenplan_tag: (d) => [\n    identitySection(),\n    { name: "entity", selector: { entity: {} } },\n    ...posXYWH(d),\n  ],\n  sph_stundenplan_grid: (d) => [\n    identitySection(),\n    { name: "entity", selector: { entity: {} } },\n    { name: "h", default: 648, selector: { number: { min: 100, max: d.height, step: 8, mode: "box" } } },\n  ],'''
s = s[:end_schema] + schema_insert + s[end_schema:]
editor.write_text(s)
