#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const args = process.argv.slice(2);
const targetArg = args.find((arg) => !arg.startsWith("--"));
if (!targetArg) {
  console.error("Usage: node validate-artifacts.mjs <output-dir> [--feishu] [--competitive]");
  process.exit(2);
}

const targetDir = path.resolve(targetArg);
const requireFeishu = args.includes("--feishu");
const requireCompetitive = args.includes("--competitive");
const errors = [];
const warnings = [];

if (!fs.existsSync(targetDir) || !fs.statSync(targetDir).isDirectory()) {
  console.error(JSON.stringify({ ok: false, errors: [`Output directory not found: ${targetDir}`] }, null, 2));
  process.exit(1);
}

const files = fs.readdirSync(targetDir, { withFileTypes: true }).filter((entry) => entry.isFile()).map((entry) => entry.name);
const markdownFiles = files.filter((name) => name.endsWith(".md"));
const htmlFiles = files.filter((name) => name.endsWith(".html"));
if (!markdownFiles.some((name) => /交互设计需求分析|design-analysis/i.test(name)) && !htmlFiles.some((name) => !/competitive-analysis/i.test(name))) errors.push("Missing interaction design analysis HTML or Markdown file.");
if (requireFeishu && !markdownFiles.some((name) => /飞书同步稿|feishu/i.test(name))) errors.push("Missing Feishu sync draft for --feishu mode.");
if (requireCompetitive && !htmlFiles.some((name) => /competitive-analysis/i.test(name))) errors.push("Missing independent competitive analysis HTML for --competitive mode.");

const imagePattern = /!\[[^\]]*\]\(([^)]+)\)/g;
for (const markdownName of markdownFiles) {
  const markdownPath = path.join(targetDir, markdownName);
  const source = fs.readFileSync(markdownPath, "utf8");
  let match;
  while ((match = imagePattern.exec(source))) {
    const ref = match[1].trim().replace(/^<|>$/g, "");
    if (/^(https?:|data:|\/)/.test(ref)) continue;
    const assetPath = path.resolve(path.dirname(markdownPath), ref.split("#")[0]);
    if (!fs.existsSync(assetPath)) errors.push(`${markdownName}: missing image ${ref}`);
  }
}

for (const svgName of files.filter((name) => name.endsWith(".svg") && /(flow|diagram|architecture|relationship|whiteboard)/i.test(name))) {
  const svg = fs.readFileSync(path.join(targetDir, svgName), "utf8");
  if (/font-family\s*=/.test(svg)) errors.push(`${svgName}: font-family is not supported by editable Feishu whiteboards.`);
  if (/<(?:linearGradient|radialGradient|filter|pattern|clipPath|mask)\b/.test(svg)) errors.push(`${svgName}: contains an unsupported SVG feature.`);
  if (/<polygon\b/.test(svg)) warnings.push(`${svgName}: polygon may flatten; inspect whether it is a hand-drawn arrowhead.`);
}

const result = { ok: errors.length === 0, targetDir, errors, warnings };
console.log(JSON.stringify(result, null, 2));
process.exit(result.ok ? 0 : 1);
