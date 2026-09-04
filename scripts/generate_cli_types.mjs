#!/usr/bin/env node
/**
 * Generate TypeScript option-bag declarations from the exported CLI JSON
 * Schemas (issue #286). Each <ModelName>.schema.json written by
 * scripts/export_cli_schemas.py becomes an `export interface <ModelName>`
 * in npm/src/types.generated.ts.
 *
 * Usage:
 *   node scripts/generate_cli_types.mjs [schemasDir] [outFile]
 *
 * Defaults: schemasDir ".cli-schemas", outFile "npm/src/types.generated.ts".
 * Run end-to-end via `npm run gen:cli-types` (which also formats the output
 * with the repo's prettier). The freshness gate in npm/test-cli-drift.js
 * regenerates to a temp file and diffs against the committed output, so a
 * Python model change that is not regenerated fails CI.
 *
 * Schema normalizations, mirroring the hand-written types.ts conventions:
 *
 * 1. Property `title` stripping — Pydantic v2 stamps a `title` on every
 *    property (the PascalCased field name). json-schema-to-typescript turns
 *    titled property subschemas into standalone named aliases (e.g.
 *    `Outputdir`, `Files`) that collide across concatenated declarations, so
 *    titles are dropped and property types inline.
 * 2. `null` stripping from optional properties — Pydantic emits
 *    `anyOf: [T, null]` for `T | None = None`; in TS the `?` already carries
 *    the optionality, so the convention is `?: T`. Required nullable fields
 *    keep their `null`.
 * 3. `readonly` emission for tuple arrays — jstt has no `readonly` support,
 *    so fields the exporter flagged `readOnly: true` (Python `tuple[...]`
 *    annotations) get their emitted `name?: string[];` member rewritten to
 *    `name?: readonly string[];`. The rewrite is scoped per model to exactly
 *    the flagged property names and throws if a flagged member is missing.
 * 4. QueryOptions delta — the CLI `query` positional is an optional variadic
 *    (so the schema truthfully says `query?: string[]`), but the TS binding
 *    deliberately requires a single scalar `query: string`. The patch below
 *    encodes that documented divergence; a schema-shape guard throws if the
 *    CLI positional ever changes shape so the delta cannot silently rot.
 */

import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { compile } from "json-schema-to-typescript";

const [schemasDir = ".cli-schemas", outFile = "npm/src/types.generated.ts"] =
  process.argv.slice(2);

const header = [
  "/**",
  " * GENERATED FILE — do not hand-edit.",
  " * Sources: scripts/export_cli_schemas.py (src/wiki/schemas/cli.py COMMAND_MODELS,",
  " * model_json_schema(by_alias=True)) compiled by json-schema-to-typescript.",
  " * Regenerate via: npm run gen:cli-types",
  " */",
  "",
].join("\n");

/** Recursively drop `title` keys so jstt inlines property types. */
function stripTitles(node) {
  if (node === null || typeof node !== "object") return;
  for (const [key, value] of Object.entries(node)) {
    if (key === "title") delete node.title;
    else stripTitles(value);
  }
}

/**
 * Drop `null` from `anyOf` on optional properties of object schemas.
 *
 * Pydantic emits `anyOf: [T, null]` for `T | None = None` fields. In TS the
 * optionality is already expressed by `?`, so `?: T | null` is noise — the
 * types.ts convention is `?: T`. Fields listed in `required` stay nullable
 * (they would genuinely accept null).
 */
function stripNullFromOptional(node) {
  if (node === null || typeof node !== "object") return;
  if (
    typeof node.properties === "object" &&
    !Array.isArray(node.properties) &&
    node.type === "object"
  ) {
    const required = new Set(node.required ?? []);
    for (const [propName, propSchema] of Object.entries(node.properties)) {
      if (!required.has(propName) && Array.isArray(propSchema.anyOf)) {
        propSchema.anyOf = propSchema.anyOf.filter(
          (branch) => branch?.type !== "null"
        );
        if (propSchema.anyOf.length === 1) {
          Object.assign(propSchema, propSchema.anyOf[0]);
          delete propSchema.anyOf;
        }
      }
    }
  }
  for (const value of Object.values(node)) {
    if (value && typeof value === "object") stripNullFromOptional(value);
  }
}

/**
 * Documented delta (issue #286 §4.1): QueryOptions.query is a required scalar
 * in TS while the CLI exposes it as an optional variadic positional. Guarded
 * so the patch only applies to the shape it expects.
 */
function applyQueryDelta(schema) {
  const query = schema.properties?.query;
  if (!query) return;
  const optionalVariadicArray =
    query.type === "array" &&
    query.items?.type === "string" &&
    !(schema.required ?? []).includes("query");
  if (!optionalVariadicArray) {
    throw new Error(
      "QueryOptions.query delta expects an optional array of strings. The CLI " +
        "positional must have changed shape — re-evaluate the documented delta " +
        "in issue #286 before regenerating."
    );
  }
  const { description } = query;
  schema.properties.query = description
    ? { type: "string", description }
    : { type: "string" };
  schema.required = [...(schema.required ?? []), "query"];
}

/**
 * Rewrite readOnly-flagged optional array members to `readonly`. Scoped to
 * exactly the flagged property names inside one model's own declaration.
 */
function applyReadonly(out, name, schema) {
  for (const [propName, propSchema] of Object.entries(schema.properties ?? {})) {
    if (propSchema.readOnly !== true) continue;
    const re = new RegExp(`^(\\s*${propName}\\?: )(string\\[\\])`, "m");
    if (!re.test(out)) {
      throw new Error(
        `${name}.${propName} is flagged readOnly but no \`${propName}?: string[]\` member was emitted`
      );
    }
    out = out.replace(re, "$1readonly $2");
  }
  return out;
}

const files = (await readdir(schemasDir))
  .filter((f) => f.endsWith(".schema.json"))
  .sort();

const chunks = [];
for (const file of files) {
  const name = file.replace(/\.schema\.json$/, "");
  const schema = JSON.parse(await readFile(path.join(schemasDir, file), "utf8"));
  applyQueryDelta(schema);
  stripTitles(schema);
  stripNullFromOptional(schema);
  let out = await compile(schema, name, { bannerComment: "" });
  out = applyReadonly(out, name, schema);
  chunks.push(out);
}

await mkdir(path.dirname(outFile), { recursive: true });
await writeFile(outFile, header + chunks.join("\n\n") + "\n");
console.log(`Wrote ${chunks.length} model declarations to ${outFile}`);
