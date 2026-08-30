import fs from "node:fs/promises";
import path from "node:path";
import { Workbook } from "@oai/artifact-tool";

const outputDir = path.resolve("outputs/01a05384-26ef-7e31-8172-0d87ea9ed215");
const outputPath = path.join(outputDir, "transacciones_inversiones_pendientes_2026-07_2026-08.csv");
const previewPath = path.join(outputDir, ".transacciones_inversiones_preview.png");

const headers = [
  "date",
  "asset",
  "action",
  "amount",
  "shares",
  "price_per_share",
  "notes",
];

const rows = [
  ["2026-07-01", "Bitcoin", "BUY", "50.00", "0.00096803", "51651.2", "Comisión: 0,20 EUR"],
  ["2026-07-02", "Physical Gold USD", "BUY", "2.63", "0.037967", "69.27", ""],
  ["2026-07-02", "Physical Gold USD", "BUY", "0.18", "0.002598", "69.26", ""],
  ["2026-07-02", "Physical Gold USD", "BUY", "50.00", "0.721761", "69.275", ""],
  ["2026-07-04", "Vanguard Emerging Markets", "BUY", "97.72", "0.31", "315.241", ""],
  ["2026-07-07", "Fidelity MSCI World Index", "BUY", "325.00", "23.042", "14.104", ""],
  ["2026-07-09", "Physical Gold USD", "BUY", "2.04", "0.029215", "69.83", ""],
  ["2026-07-16", "Physical Gold USD", "BUY", "3.37", "0.049366", "68.27", ""],
  ["2026-07-16", "Physical Gold USD", "BUY", "3.57", "0.051318", "69.56", ""],
  ["2026-07-18", "Fidelity MSCI World Index", "BUY", "325.00", "23.362", "13.911", ""],
  ["2026-08-01", "Bitcoin", "BUY", "50.00", "0.00091447", "54676.4", "Comisión: 0,40 EUR"],
  ["2026-08-03", "Physical Gold USD", "BUY", "4.75", "0.069571", "68.28", ""],
  ["2026-08-03", "Physical Gold USD", "BUY", "50.00", "0.73185", "68.32", ""],
  ["2026-08-03", "Physical Gold USD", "BUY", "2.00", "0.029271", "68.33", ""],
  ["2026-08-03", "Physical Gold USD", "BUY", "1.80", "0.023341", "77.11", ""],
  ["2026-08-05", "Vanguard Emerging Markets", "BUY", "100.00", "0.33", "300.63", ""],
  ["2026-08-05", "Fidelity MSCI World Index", "BUY", "325.00", "22.727", "14.3", ""],
  ["2026-08-19", "Fidelity MSCI World Index", "BUY", "325.00", "22.857", "14.218", ""],
];

const validAssets = new Set([
  "Bitcoin",
  "Physical Gold USD",
  "Vanguard Emerging Markets",
  "Fidelity MSCI World Index",
]);

function quoteCsv(value) {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function decimalPlaces(value) {
  const [, fraction = ""] = String(value).split(".");
  return fraction.length;
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(rows.length === 18, `Expected 18 rows, received ${rows.length}`);

const keys = new Set();
for (const [index, row] of rows.entries()) {
  const rowNumber = index + 2;
  assert(row.length === headers.length, `Row ${rowNumber}: expected ${headers.length} columns`);
  const [date, asset, action, amount, shares, price, notes] = row;
  assert(/^\d{4}-\d{2}-\d{2}$/.test(date), `Row ${rowNumber}: invalid ISO date`);
  assert(!Number.isNaN(Date.parse(`${date}T00:00:00Z`)), `Row ${rowNumber}: invalid calendar date`);
  assert(validAssets.has(asset), `Row ${rowNumber}: unknown asset '${asset}'`);
  assert(action === "BUY" || action === "SELL", `Row ${rowNumber}: invalid action`);
  assert(Number(amount) > 0 && decimalPlaces(amount) <= 2, `Row ${rowNumber}: invalid amount`);
  assert(Number(shares) > 0 && decimalPlaces(shares) <= 8, `Row ${rowNumber}: invalid shares`);
  assert(Number(price) > 0 && decimalPlaces(price) <= 6, `Row ${rowNumber}: invalid price`);
  assert(typeof notes === "string", `Row ${rowNumber}: invalid notes`);
  const key = row.join("\u001f");
  assert(!keys.has(key), `Row ${rowNumber}: exact duplicate`);
  keys.add(key);
}

const csvText = [headers, ...rows]
  .map((row) => row.map(quoteCsv).join(","))
  .join("\n") + "\n";

await fs.mkdir(outputDir, { recursive: true });

const workbook = await Workbook.fromCSV(csvText, { sheetName: "Transactions" });
const sheet = workbook.worksheets.getItem("Transactions");
sheet.showGridLines = false;
sheet.freezePanes.freezeRows(1);
sheet.getRange("A1:G19").format.font = { name: "Aptos", size: 10 };
sheet.getRange("A1:G1").format = {
  fill: "#17365D",
  font: { name: "Aptos", size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
};
sheet.getRange("A2:A19").format.columnWidth = 13;
sheet.getRange("B2:B19").format.columnWidth = 31;
sheet.getRange("C2:C19").format.columnWidth = 10;
sheet.getRange("D2:F19").format.columnWidth = 15;
sheet.getRange("G2:G19").format.columnWidth = 23;
sheet.getRange("D2:F19").format.horizontalAlignment = "right";
sheet.getRange("A1:G19").format.rowHeight = 18;

const preview = await workbook.render({
  sheetName: "Transactions",
  range: "A1:G19",
  scale: 1.25,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

const inspection = await workbook.inspect({
  kind: "table",
  range: "Transactions!A1:G19",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 7,
  maxChars: 12000,
});

const errorScan = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});

await fs.writeFile(outputPath, csvText, "utf8");

const totalsByAsset = {};
for (const [, asset, , amount] of rows) {
  totalsByAsset[asset] = Number(((totalsByAsset[asset] ?? 0) + Number(amount)).toFixed(2));
}

console.log(inspection.ndjson);
console.log(errorScan.ndjson);
console.log(JSON.stringify({
  outputPath,
  rowCount: rows.length,
  totalAmount: rows.reduce((sum, row) => sum + Number(row[3]), 0).toFixed(2),
  totalsByAsset,
  firstDate: rows[0][0],
  lastDate: rows.at(-1)[0],
}, null, 2));
