/**
 * CLI drift detector — verifies TypeScript bindings match the Python CLI.
 *
 * Runs in four stages:
 *
 * 1. CLI/model conformance (`scripts/check_cli_models.py`): introspects the
 *    real Click command tree and fails when a non-hidden subcommand or
 *    option has no Pydantic model entry (e.g. a new `@click.option` that
 *    was never mirrored into `src/wiki/schemas/cli.py`).
 * 2. Command presence: every manifest command must have a
 *    Wiki.prototype method (and vice versa for the documented extras that
 *    have no manifest key).
 * 3. Generated-types freshness: regenerates `npm/src/types.generated.ts`
 *    from the models into a temp file and diffs it against the committed
 *    copy. Option-name parity Python ↔ TypeScript needs no hand-maintained
 *    echo here — the generated file carries the model's aliases, and
 *    `npm/src/types.ts` re-exports/extend it (issue #286 §7(d), the
 *    `EXPECTED_OPTIONS` echo was retired once the freshness gate landed).
 * 4. Flag-string parity: the wrapper's `--flag` literals in
 *    `npm/src/wiki.ts` are duplicated from Click's `@click.option`
 *    declarations, and stages 1–3 never look at them (models carry field
 *    names/aliases, not flag strings). This stage introspects the real Click
 *    tree (`scripts/export_cli_flags.py`) and asserts every `--flag` literal
 *    each wrapper method emits — including direct `args.push` emissions like
 *    `update`'s `--dry-run` and `init`'s boolean-pair ternary — is a real
 *    option string on that command (or on the root `wiki` command for
 *    `args()`, which emits `--config`/`--wiki-inputs` from no model entry).
 */

const { execSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const prettier = require("prettier");
const ts = require("typescript");
const { Wiki } = require("./dist/index.js");

// Prototype methods without a same-named COMMAND_MODELS key. Note: neither is
// TS-only — `format` is the TS/Python alias of the `fmt` subcommand (whose
// model IS FmtOptions) and `preflight` is a both-sides composite method over
// lint + check with no CLI command on either side.
const NO_MANIFEST_METHODS = new Set(["preflight", "format"]);

const GENERATED_TYPES = "npm/src/types.generated.ts";
const ROOT_FLAGS_KEY = "__root__";
const ROOT_DISPLAY = "wiki (root)";

/**
 * Stage 4: per-method `--flag` string literals from npm/src/wiki.ts, using the
 * TypeScript compiler API so doc comments can't leak false flags and direct
 * `args.push(...)` emissions (update's `--dry-run`, init's boolean-pair
 * ternary) are captured as well as `pushFlag`/`pushRepeated` arguments.
 */
function extractMethodFlags(source) {
  const sf = ts.createSourceFile(
    "wiki.ts",
    source,
    ts.ScriptTarget.Latest,
    false,
    ts.ScriptKind.TS,
  );
  const byMethod = new Map();

  function collectFlags(body) {
    const flags = new Set();
    (function walk(node) {
      if (ts.isStringLiteral(node) && node.text.startsWith("--")) {
        flags.add(node.text);
      }
      ts.forEachChild(node, walk);
    })(body);
    return flags;
  }

  (function visit(node) {
    if (ts.isClassDeclaration(node) && node.name && node.name.text === "Wiki") {
      for (const member of node.members) {
        if (
          (ts.isMethodDeclaration(member) ||
            ts.isConstructorDeclaration(member)) &&
          member.body
        ) {
          const name = member.name ? member.name.getText(sf) : "constructor";
          byMethod.set(name, collectFlags(member.body));
        }
      }
    }
    ts.forEachChild(node, visit);
  })(sf);

  return byMethod;
}

/** Stage 3: regenerate the generated types and compare to the committed file. */
async function checkFreshness() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "wiki-cli-schemas-"));
  const schemasDir = path.join(tmp, "schemas");
  const outFile = path.join(tmp, "types.generated.ts");
  try {
    execSync(
      `uv run python scripts/export_cli_schemas.py --out ${JSON.stringify(schemasDir)}`,
      {
        encoding: "utf-8",
        stdio: "inherit",
        timeout: 60_000,
      },
    );
    execSync(
      `node scripts/generate_cli_types.mjs ${JSON.stringify(schemasDir)} ${JSON.stringify(outFile)}`,
      {
        encoding: "utf-8",
        stdio: "inherit",
        timeout: 60_000,
      },
    );
    // prettier v3 `format` is async; the committed file was formatted with the
    // repo's prettier defaults, so format the fresh output the same way.
    const regenerated = await prettier.format(
      fs.readFileSync(outFile, "utf8"),
      {
        filepath: GENERATED_TYPES,
      },
    );
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

  // Stage 2: command presence — every manifest command needs a wrapper.
  const manifest = JSON.parse(
    execSync("uv run python scripts/export_cli_shapes.py", {
      encoding: "utf-8",
      timeout: 30_000,
    }),
  );

  const tsProto = Wiki.prototype;
  const tsMethods = new Set(
    Object.getOwnPropertyNames(tsProto).filter(
      (n) => typeof tsProto[n] === "function" && n !== "constructor",
    ),
  );

  for (const cmd of Object.keys(manifest)) {
    if (!tsMethods.has(cmd)) {
      errors.push(`Missing TS method: Wiki.prototype.${cmd}()`);
    }
  }

  for (const method of NO_MANIFEST_METHODS) {
    if (!tsMethods.has(method)) {
      errors.push(
        `Missing method without a manifest entry: Wiki.prototype.${method}()`,
      );
    }
  }

  // Stage 3: generated-types freshness.
  const freshnessError = await checkFreshness();
  if (freshnessError) errors.push(freshnessError);

  // Stage 4: flag-string parity — every `--flag` a wrapper method emits must
  // be a real Click option string on that command (or on the root command).
  const commandFlags = JSON.parse(
    execSync("uv run python scripts/export_cli_flags.py", {
      encoding: "utf-8",
      timeout: 30_000,
    }),
  );
  const flagsByMethod = extractMethodFlags(
    fs.readFileSync("npm/src/wiki.ts", "utf8"),
  );
  let flagCount = 0;
  for (const [method, flags] of flagsByMethod) {
    const cmd = Object.prototype.hasOwnProperty.call(commandFlags, method)
      ? method
      : method === "args"
        ? ROOT_FLAGS_KEY
        : undefined;
    if (cmd === undefined) {
      if (flags.size > 0) {
        errors.push(
          `Wiki.prototype.${method}() emits flags (${[...flags].join(", ")}) but ` +
            `'${method}' is not a CLI command; emit them through a command method ` +
            `or add a mapping to the drift check.`,
        );
      }
      continue;
    }
    const real = new Set(commandFlags[cmd] ?? []);
    const display = cmd === ROOT_FLAGS_KEY ? ROOT_DISPLAY : `'${cmd}'`;
    for (const flag of flags) {
      flagCount++;
      if (!real.has(flag)) {
        errors.push(
          `Wiki.prototype.${method}() emits ${flag} but the ${display} command has ` +
            `no such option (real options: ${[...real].join(", ") || "none"}).`,
        );
      }
    }
  }

  if (exitCode === 0 && errors.length === 0) {
    const cmdCount = Object.keys(manifest).length;
    console.log(
      `Drift check passed: ${cmdCount} commands mirrored on Wiki.prototype; ` +
        `${flagCount} wrapper flag emissions verified against the Click tree; ` +
        `generated types are fresh.`,
    );
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
