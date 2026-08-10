/**
 * TypeScript SDK for the wazootech-wiki CLI.
 *
 * Each method shells out to the Python CLI and returns typed results.
 * Options use camelCase names mapped to the corresponding CLI flags.
 *
 * ```ts
 * import { Wiki } from "wazootech-wiki";
 * const wiki = Wiki.load({ config: "docs/wiki.yml" });
 * await wiki.check({ strict: true });
 * ```
 */
import type { ChildProcess } from "node:child_process";
import { runWiki, spawnWiki } from "./runner";
import type {
  BuildOptions,
  CheckOptions,
  ExportOptions,
  ExportResult,
  FmtOptions,
  InitOptions,
  LinkOptions,
  LintOptions,
  McpOptions,
  PreflightOptions,
  PreflightResult,
  QueryOptions,
  RenderOptions,
  RunOptions,
  RuntimeOptions,
  ServeOptions,
  UpgradeOptions,
  WikiCommandResult,
  WikiLoadOptions,
} from "./types";

type FlagValue = string | number | boolean | undefined;

function pushFlag(args: string[], flag: string, value: FlagValue): void {
  if (value === undefined) return;
  if (typeof value === "boolean") {
    if (value) args.push(flag);
    return;
  }
  args.push(flag, String(value));
}

function pushRepeated(
  args: string[],
  flag: string,
  values: readonly string[] | undefined,
): void {
  for (const value of values ?? []) {
    args.push(flag, value);
  }
}

function appendFiles(
  args: string[],
  files: readonly string[] | undefined,
): void {
  if (files?.length) args.push(...files);
}

function parseJsonOutput<T>(result: WikiCommandResult): ExportResult<T> {
  return { ...result, data: JSON.parse(result.stdout) as T };
}

/** Loaded wiki configuration binding for TypeScript consumers.
 *
 * Create via {@link Wiki.load}, then call methods that mirror the CLI surface.
 */
export class Wiki {
  /** Path to the ``wiki.yml`` config file (or directory). */
  readonly config: string | undefined;
  /** Overridden ``wiki.inputs`` paths. */
  readonly wikiInputs: readonly string[];
  /** Working directory for CLI subprocesses. */
  readonly cwd: string | undefined;
  /** Extra environment variables. */
  readonly env: NodeJS.ProcessEnv | undefined;
  /** Runtime URL overrides. */
  readonly runtime: RuntimeOptions;

  /** @internal Use {@link Wiki.load} to construct. */
  constructor(options: WikiLoadOptions & { runtime?: RuntimeOptions } = {}) {
    this.config = options.config;
    this.wikiInputs = options.wikiInputs ?? [];
    this.cwd = options.cwd;
    this.env = options.env;
    this.runtime = options.runtime ?? {};
  }

  /** Create a new Wiki instance from load options.
   *
   * @param options - Load options (config path, inputs, working directory).
   */
  static load(options: WikiLoadOptions = {}): Wiki {
    return new Wiki(options);
  }

  /** Return a new Wiki with merged runtime overrides.
   *
   * @param options - Runtime overrides (baseUrl, urlStyle).
   */
  withRuntime(options: RuntimeOptions): Wiki {
    const loadOptions: WikiLoadOptions & { runtime?: RuntimeOptions } = {
      wikiInputs: this.wikiInputs,
      runtime: { ...this.runtime, ...options },
    };
    if (this.config !== undefined) loadOptions.config = this.config;
    if (this.cwd !== undefined) loadOptions.cwd = this.cwd;
    if (this.env !== undefined) loadOptions.env = this.env;
    return new Wiki(loadOptions);
  }

  /** Build the argv array for a subcommand.
   *
   * Prepends ``--wiki-inputs`` and ``--config`` from the instance state.
   *
   * @param subcommand - CLI subcommand name (e.g. ``"check"``).
   * @param subcommandArgs - Additional arguments for the subcommand.
   */
  args(subcommand: string, subcommandArgs: readonly string[] = []): string[] {
    const args: string[] = [];
    pushRepeated(args, "--wiki-inputs", this.wikiInputs);
    pushFlag(args, "--config", this.config);
    args.push(subcommand, ...subcommandArgs);
    return args;
  }

  /** Run arbitrary CLI arguments against the wiki Python binary.
   *
   * @param args - Full argument list.
   * @param options - Run options (cwd, env, timeout, stdin).
   */
  run(
    args: readonly string[],
    options: RunOptions = {},
  ): Promise<WikiCommandResult> {
    const runOptions: RunOptions = { env: { ...this.env, ...options.env } };
    const cwd = options.cwd ?? this.cwd;
    if (cwd !== undefined) runOptions.cwd = cwd;
    if (options.stdin !== undefined) runOptions.stdin = options.stdin;
    if (options.timeoutMs !== undefined)
      runOptions.timeoutMs = options.timeoutMs;
    if (options.throwOnError !== undefined)
      runOptions.throwOnError = options.throwOnError;
    if (options.signal !== undefined) runOptions.signal = options.signal;
    return runWiki(args, runOptions);
  }

  /** Run integrity checks: SHACL, JSON Schema, routes, collisions, layout.
   *
   * @param options - Check options (strict, verbose, file filter).
   */
  check(options: CheckOptions = {}): Promise<WikiCommandResult> {
    const args: string[] = [];
    pushFlag(args, "--verbose", options.verbose);
    pushFlag(args, "--strict", options.strict);
    appendFiles(args, options.files);
    return this.run(this.args("check", args));
  }

  /** Run convention audits: links, filenames, headings, link style.
   *
   * @param options - Lint options (strict, verbose, file filter).
   */
  lint(options: LintOptions = {}): Promise<WikiCommandResult> {
    const args: string[] = [];
    pushFlag(args, "--verbose", options.verbose);
    pushFlag(args, "--strict", options.strict);
    appendFiles(args, options.files);
    return this.run(this.args("lint", args));
  }

  /** Run lint then check sequentially and return a merged report.
   *
   * @param options - Preflight options (strict, verbose).
   */
  async preflight(options: PreflightOptions = {}): Promise<PreflightResult> {
    const lint = await this.lint(options);
    const check = await this.check(options);
    return { lint, check };
  }

  /** Build a static HTML site from wiki documents.
   *
   * @param options - Build options (outputDir, baseUrl, urlStyle, render, etc.).
   */
  build(options: BuildOptions = {}): Promise<WikiCommandResult> {
    const args: string[] = [];
    pushFlag(args, "--output-dir", options.outputDir);
    pushFlag(args, "--site-base-url", options.baseUrl ?? this.runtime.baseUrl);
    pushFlag(
      args,
      "--site-url-style",
      options.urlStyle ?? this.runtime.urlStyle,
    );
    pushFlag(args, "--render", options.render);
    pushFlag(args, "--reload", options.reload);
    pushFlag(args, "--cache", options.cache);
    pushFlag(args, "--no-check", options.noCheck);
    pushFlag(args, "--verbose", options.verbose);
    return this.run(this.args("build", args));
  }

  /** Format markdown wiki pages using mdformat.
   *
   * @param options - Format options (check, verbose, file filter).
   */
  fmt(options: FmtOptions = {}): Promise<WikiCommandResult> {
    const args: string[] = [];
    pushFlag(args, "--check", options.check);
    pushFlag(args, "--verbose", options.verbose);
    appendFiles(args, options.files);
    return this.run(this.args("fmt", args));
  }

  /** Alias for {@link fmt}. */
  format(options: FmtOptions = {}): Promise<WikiCommandResult> {
    return this.fmt(options);
  }

  /** Render inline SPARQL blocks in markdown files.
   *
   * @param options - Render options (check, reload, cache, noInference, file filter).
   */
  render(options: RenderOptions = {}): Promise<WikiCommandResult> {
    const args: string[] = [];
    pushFlag(args, "--no-inference", options.noInference);
    pushFlag(args, "--reload", options.reload);
    pushFlag(args, "--cache", options.cache);
    pushFlag(args, "--check", options.check);
    pushFlag(args, "--verbose", options.verbose);
    appendFiles(args, options.files);
    return this.run(this.args("render", args));
  }

  /** Export document frontmatter as RDF or JSON-LD.
   *
   * @param options - Export options (format, mode, output, file filter).
   */
  async export<T = unknown>(
    options: ExportOptions = {},
  ): Promise<ExportResult<T>> {
    const args: string[] = [];
    pushFlag(args, "--output", options.output);
    pushFlag(args, "--format", options.format);
    pushFlag(args, "--mode", options.mode);
    appendFiles(args, options.files);
    const result = await this.run(this.args("export", args));
    const shouldParseJson =
      options.parseJson ??
      (options.format === undefined ||
        options.format === "dict" ||
        options.format === "json-ld");
    if (shouldParseJson) {
      return parseJsonOutput<T>(result);
    }
    return result;
  }

  /** Suggest or repair internal links for wiki pages.
   *
   * @param options - Link options (apply, fixBroken, dryRun, check, verbose, file filter).
   */
  link(options: LinkOptions = {}): Promise<WikiCommandResult> {
    const args: string[] = [];
    pushFlag(args, "--apply", options.apply);
    pushFlag(args, "--fix-broken", options.fixBroken);
    pushFlag(args, "--dry-run", options.dryRun);
    pushFlag(args, "--check", options.check);
    pushFlag(args, "--verbose", options.verbose);
    appendFiles(args, options.files);
    return this.run(this.args("link", args));
  }

  /** Run a SPARQL query against the wiki's RDF graph.
   *
   * @param options - Query options (query string, format, jq, etc.).
   */
  async query<T = unknown>(options: QueryOptions): Promise<string | T> {
    const args: string[] = [];
    pushFlag(args, "--format", options.format);
    pushFlag(args, "--output", options.output);
    pushFlag(args, "--no-inference", options.noInference);
    pushFlag(args, "--reload", options.reload);
    pushFlag(args, "--cache", options.cache);
    pushFlag(args, "--jq", options.jq);
    pushFlag(args, "--pretty", options.pretty);
    pushFlag(args, "--verbose", options.verbose);
    args.push(options.query);
    const result = await this.run(this.args("query", args));
    if (options.parseJson ?? options.format === "json") {
      return JSON.parse(result.stdout) as T;
    }
    return result.stdout;
  }

  /** List read-only RDF named graphs for root and installed source provenance. */
  graphList(): Promise<WikiCommandResult> {
    return this.run(this.args("graph", ["list"]));
  }

  /** Start a local HTTP server for browsing the wiki.
   *
   * @param options - Serve options (host, port, baseUrl, urlStyle, watch).
   * @returns The spawned child process (not a Promise).
   */
  serve(options: ServeOptions = {}): ChildProcess {
    const args: string[] = [];
    pushFlag(args, "--host", options.host);
    pushFlag(args, "--port", options.port);
    pushFlag(args, "--site-base-url", options.baseUrl ?? this.runtime.baseUrl);
    pushFlag(
      args,
      "--site-url-style",
      options.urlStyle ?? this.runtime.urlStyle,
    );
    pushFlag(args, "--watch", options.watch);
    return spawnWiki(this.args("serve", args), {
      cwd: options.cwd ?? this.cwd,
      env: { ...this.env, ...options.env },
    });
  }

  /** Start a read-only MCP server for the wiki graph.
   *
   * @param options - MCP options (mode, cache, cwd, env).
   * @returns The spawned child process (not a Promise).
   */
  mcp(options: McpOptions = {}): ChildProcess {
    const args: string[] = [];
    pushFlag(args, "--mode", options.mode);
    pushFlag(args, "--cache", options.cache);
    return spawnWiki(this.args("mcp", args), {
      cwd: options.cwd ?? this.cwd,
      env: { ...this.env, ...options.env },
    });
  }

  /** Scaffold a new wiki project in an empty directory.
   *
   * @param options - Init options (git, repo, wiki inputs, graph settings).
   */
  init(options: InitOptions = {}): Promise<WikiCommandResult> {
    const args: string[] = [];
    pushFlag(args, "--git", options.git);
    pushFlag(args, "--repo", options.repo);
    pushFlag(args, "--graph-context-wiki", options.graphContextWiki);
    pushFlag(args, "--site-base-url", options.baseUrl);
    pushFlag(args, "--site-url-style", options.urlStyle);
    pushFlag(args, "--graph-content-predicate", options.graphContentPredicate);
    pushFlag(args, "--link-style", options.linkStyle);
    pushRepeated(args, "--wiki-inputs", options.wikiInputs);
    pushFlag(args, "--graph-base-iri", options.graphBaseIri);
    pushRepeated(args, "--graph-implicit-types", options.graphImplicitTypes);
    pushFlag(
      args,
      "--graph-implicit-types-policy",
      options.graphImplicitTypesPolicy,
    );
    if (options.graphIncludeFileExtension !== undefined) {
      args.push(
        options.graphIncludeFileExtension
          ? "--graph-include-file-extension"
          : "--no-graph-include-file-extension",
      );
    }
    return this.run(this.args("init", args));
  }

  /** Check for updates and upgrade the wiki CLI.
   *
   * @param options - Upgrade options (check, yes, verbose).
   */
  upgrade(options: UpgradeOptions = {}): Promise<WikiCommandResult> {
    const args: string[] = [];
    pushFlag(args, "--check", options.check);
    pushFlag(args, "--yes", options.yes);
    pushFlag(args, "--verbose", options.verbose);
    return this.run(this.args("upgrade", args));
  }
}
