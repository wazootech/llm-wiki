/**
 * CLI drift detector — verifies TypeScript bindings match Pydantic models.
 *
 * Runs in three stages:
 *
 * 1. CLI/model conformance (`scripts/check_cli_models.py`): introspects the
 *    real Click command tree and fails when a non-hidden subcommand or
 *    option has no Pydantic model entry (e.g. a new `@click.option` that
 *    was never mirrored into `src/wiki/schemas/cli.py`).
 * 2. Model/TS drift: generates a command→options map from Pydantic models,
 *    then checks that every subcommand has a Wiki.prototype method and
 *    matching expected option names.
 * 3. Generated-types freshness: regenerates `npm/src/types.generated.ts`
 *    from the models into a temp file and diffs it against the committed
 *    copy, so a model change that was not regenerated fails here.
 */

const { execSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const prettier = require("prettier");
const { Wiki } = require("./dist/index.js");

const EXPECTED_OPTIONS = {
  build: ["baseUrl", "cache", "noCheck", "outputDir", "reload", "render", "urlStyle", "verbose"],
  check: ["files", "strict", "verbose"],
  export: ["files", "format", "mode", "output"],
  fmt: ["check", "files", "verbose"],
  init: ["baseUrl", "git", "graphBaseIri", "graphContentPredicate", "graphContextWiki", "graphImplicitTypes", "graphImplicitTypesPolicy", "graphIncludeFileExtension", "linkStyle", "repo", "siteLayout", "template", "urlStyle", "wikiInputs"],
  install: ["url"],
  link: ["apply", "check", "dryRun", "files", "fixBroken", "verbose"],
  lint: ["files", "strict", "verbose"],
  mcp: ["cache", "mode"],
  query: ["cache", "format", "jq", "noInference", "output", "pretty", "query", "reload", "verbose"],
  remove: ["name"],
  render: ["cache", "check", "files", "noInference", "reload", "verbose"],
  serve: ["baseUrl", "host", "port", "urlStyle", "watch"],
  update: ["dryRun", "name"],
  upgrade: ["check", "verbose", "yes"],
};

// Prototype methods without a same-named COMMAND_MODELS key. Note: neither is
// TS-only — `format` is the TS/Python alias of the `fmt` subcommand (whose
// model IS FmtOptions) and `preflight` is a both-sides composite method over
// lint + check with no CLI command on either side.
const NO_MANIFEST_METHODS = new Set(["preflight", "format"]);

const GENERATED_TYPES = "npm/src/types.generated.ts";

/** Stage 3: regenerate the generated types and compare to the committed file. */
async function checkFreshness() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "wiki-cli-schemas-"));
  const schemasDir = path.join(tmp, "schemas");
  const outFile = path.join(tmp, "types.generated.ts");
  try {
    execSync(`uv run python scripts/export_cli_schemas.py --out ${JSON.stringify(schemasDir)}`, {
      encoding: "utf-8",
      stdio: "inherit",
      timeout: 60_000,
    });
    execSync(`node scripts/generate_cli_types.mjs ${JSON.stringify(schemasDir)} ${JSON.stringify(outFile)}`, {
      encoding: "utf-8",
      stdio: "inherit",
      timeout: 60_000,
    });
    // prettier v3 `format` is async; the committed file was formatted with the
    // repo's prettier defaults, so format the fresh output the same way.
    const regenerated = await prettier.format(fs.readFileSync(outFile, "utf8"), {
      filepath: GENERATED_TYPES,
    });
    const committed = fs.readFileSync(GENERATED_TYPES, "utf8");
    if (regenerated !== committed) {
      return (
        `${GENERATED_TYPES} is stale — the Pydantic COMMAND_MODELS changed but the ` +
        `generated TypeScript was not regenerated. Run \`npm run gen:cli-types\` and ` +
        `commit the result.`
      );
    }
    return null;
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

async function main() {
  let exitCode = 0;
  const errors = [];

  // Stage 1: CLI ↔ Pydantic model conformance. Any CLI subcommand/option
  // missing from COMMAND_MODELS fails here before the TS comparison runs.
  try {
    execSync("uv run python scripts/check_cli_models.py", {
      encoding: "utf-8",
      stdio: "inherit",
      timeout: 60_000,
    });
  } catch (error) {
    console.error(error.message || String(error));
    process.exit(1);
  }

  // Stage 2: model ↔ TS drift.
  const manifest = JSON.parse(
    execSync("uv run python scripts/export_cli_shapes.py", {
      encoding: "utf-8",
      timeout: 30_000,
    })
  );

  const tsProto = Wiki.prototype;
  const tsMethods = new Set(
    Object.getOwnPropertyNames(tsProto).filter(
      (n) => typeof tsProto[n] === "function" && n !== "constructor"
    )
  );

  for (const [cmd, pyOptions] of Object.entries(manifest)) {
    if (!tsMethods.has(cmd)) {
      errors.push(`Missing TS method: Wiki.prototype.${cmd}()`);
      continue;
    }

    const tsOptions = EXPECTED_OPTIONS[cmd];
    if (!tsOptions) {
      errors.push(`Missing EXPECTED_OPTIONS entry for "${cmd}" — add to npm/test-cli-drift.js`);
      continue;
    }

    const tsSet = new Set(tsOptions);
    for (const opt of pyOptions) {
      if (!tsSet.has(opt)) {
        errors.push(`Missing TS option: ${cmd}() → "${opt}" — expected one of: [${tsOptions.join(", ")}]`);
      }
    }
  }

  for (const method of NO_MANIFEST_METHODS) {
    if (!tsMethods.has(method)) {
      errors.push(`Missing method without a manifest entry: Wiki.prototype.${method}()`);
    }
  }

  // Stage 3: generated-types freshness.
  const freshnessError = await checkFreshness();
  if (freshnessError) errors.push(freshnessError);

  if (exitCode === 0 && errors.length === 0) {
    const cmdCount = Object.keys(manifest).length;
    console.log(`Drift check passed: ${cmdCount} commands, ${Object.values(manifest).flat().length} options match TS bindings; generated types are fresh.`);
  } else {
    exitCode = 1;
    console.error(`Drift check FAILED (${errors.length} issue(s)):\n`);
    for (const err of errors) {
      console.error(`  *  ${err}`);
    }
  }

  process.exit(exitCode);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
