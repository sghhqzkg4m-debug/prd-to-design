#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const targetArg = args.find((arg) => !arg.startsWith("--"));
if (!targetArg) {
  console.error("Usage: node validate-artifacts.mjs <output-dir> [--feishu] [--competitive]");
  process.exit(2);
}

const targetDir = path.resolve(targetArg);
const requireFeishu = args.includes("--feishu");
const requireCompetitive = args.includes("--competitive");
const templateArg = args.find((arg) => arg.startsWith("--template="))?.slice("--template=".length);
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

const htmlSources = new Map(htmlFiles.map((name) => [name, fs.readFileSync(path.join(targetDir, name), "utf8")]));
const htmlIds = new Map(htmlFiles.map((name) => [name, new Set([...htmlSources.get(name).matchAll(/\bid\s*=\s*["']([^"']+)["']/g)].map((match) => match[1]))]));
const localLinks = new Map();
for (const [htmlName, source] of htmlSources) {
  if (/\bdata-template-href\s*=/.test(source)) errors.push(`${htmlName}: template link marker remains; use a real href.`);
  const links = [];
  for (const anchor of source.matchAll(/<a\b([^>]*)>/gi)) {
    const hrefMatch = anchor[1].match(/(?:^|\s)href\s*=\s*["']([^"']*)["']/i);
    if (!hrefMatch) {
      errors.push(`${htmlName}: anchor without href (${anchor[0].slice(0, 100)}).`);
      continue;
    }
    const href = hrefMatch[1].replace(/&amp;/g, "&");
    if (!href || href === "#" || /^javascript:/i.test(href)) {
      errors.push(`${htmlName}: invalid link target ${href || "(empty)"}.`);
      continue;
    }
    if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(href)) continue;
    const [rawPath, fragment] = href.split("#", 2);
    let decodedPath;
    try { decodedPath = decodeURIComponent(rawPath.split("?")[0]); }
    catch { errors.push(`${htmlName}: malformed link encoding ${href}.`); continue; }
    const target = decodedPath ? path.resolve(targetDir, decodedPath) : path.join(targetDir, htmlName);
    if (!fs.existsSync(target)) {
      errors.push(`${htmlName}: missing linked file ${href}.`);
      continue;
    }
    if (fragment && target.endsWith(".html")) {
      const targetName = path.basename(target);
      const ids = htmlIds.get(targetName) ?? new Set([...fs.readFileSync(target, "utf8").matchAll(/\bid\s*=\s*["']([^"']+)["']/g)].map((match) => match[1]));
      if (!ids.has(decodeURIComponent(fragment))) errors.push(`${htmlName}: missing linked anchor ${href}.`);
    }
    links.push(target);
  }
  localLinks.set(htmlName, links);
}
const mainHtml = htmlFiles.find((name) => !/competitive-analysis/i.test(name));
const competitiveHtml = htmlFiles.find((name) => /competitive-analysis/i.test(name));
if (mainHtml && competitiveHtml) {
  if (!localLinks.get(mainHtml)?.includes(path.join(targetDir, competitiveHtml))) errors.push(`${mainHtml}: no navigable link to competitive report.`);
  if (!localLinks.get(competitiveHtml)?.includes(path.join(targetDir, mainHtml))) errors.push(`${competitiveHtml}: no navigable return link to main report.`);
  const mainSource = htmlSources.get(mainHtml);
  const reportSource = htmlSources.get(competitiveHtml);
  const benchmark = mainSource.match(/<section\b[^>]*id=["']benchmark["'][^>]*>([\s\S]*?)<\/section>/i)?.[1] ?? "";
  const tbody = benchmark.match(/<tbody>([\s\S]*?)<\/tbody>/i)?.[1] ?? "";
  const clean = (value) => value.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/\s+/g, " ").trim();
  const mainTopics = [...tbody.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)].map((match) => {
    const firstCell = match[1].match(/<td\b[^>]*>([\s\S]*?)<\/td>/i)?.[1] ?? "";
    const title = clean(firstCell.match(/<strong\b[^>]*>([\s\S]*?)<\/strong>/i)?.[1] ?? "");
    const href = firstCell.match(/<a\b[^>]*href=["']([^"']+)["']/i)?.[1] ?? "";
    return { title, anchor: href.split("#")[1] ?? "" };
  });
  const reportTopics = [...reportSource.matchAll(/<article\b[^>]*class=["'][^"']*\bresearch-item\b[^"']*["'][^>]*id=["']([^"']+)["'][^>]*>([\s\S]*?)<\/article>/gi)].map((match) => ({
    anchor: match[1], title: clean(match[2].match(/<h3\b[^>]*>([\s\S]*?)<\/h3>/i)?.[1] ?? ""),
  }));
  const basisBlock = reportSource.match(/<div\b[^>]*id=["']question-basis["'][^>]*>([\s\S]*?)<\/div>/i)?.[1] ?? "";
  const basisTopics = [...basisBlock.matchAll(/<article\b[^>]*class=["'][^"']*\bquestion-basis\b[^"']*["'][^>]*>([\s\S]*?)<\/article>/gi)].map((match) => ({
    title: clean(match[1].match(/<h3\b[^>]*>([\s\S]*?)<\/h3>/i)?.[1] ?? ""),
    anchor: match[1].match(/<a\b[^>]*href=["']#([^"']+)["']/i)?.[1] ?? "",
  }));
  if (!mainTopics.length || mainTopics.length !== reportTopics.length || mainTopics.length !== basisTopics.length) {
    errors.push("Competitive topics: main table, report overview, and detailed research must have the same number of topics.");
  }
  for (const topic of mainTopics) {
    const detailed = reportTopics.filter((item) => item.anchor === topic.anchor && item.title === topic.title);
    const basis = basisTopics.filter((item) => item.anchor === topic.anchor && item.title === topic.title);
    if (!topic.title || !topic.anchor || detailed.length !== 1 || basis.length !== 1) errors.push(`Competitive topics: ${topic.title || "(untitled)"} must map to one identically named overview and research section.`);
  }
  if (new Set(mainTopics.map((topic) => topic.anchor)).size !== mainTopics.length) errors.push("Competitive topics: main table reuses a research anchor for multiple topics.");
}

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

for (const htmlName of htmlFiles.filter(name => /交互设计需求分析|design-analysis/i.test(name) && !/competitive-analysis/i.test(name))) {
  const script = fileURLToPath(new URL('./validate-template.py', import.meta.url));
  const check = spawnSync('python3', [script, path.join(targetDir, htmlName), ...(templateArg ? [path.resolve(templateArg)] : [])], { encoding: 'utf8' });
  try {
    const result = JSON.parse(check.stdout);
    errors.push(...result.errors.map(error => `${htmlName}: ${error}`));
  } catch {
    errors.push(`${htmlName}: template validation could not run: ${check.error?.message || check.stderr || check.stdout}`);
  }
}

const result = { ok: errors.length === 0, targetDir, errors, warnings };
console.log(JSON.stringify(result, null, 2));
process.exit(result.ok ? 0 : 1);
