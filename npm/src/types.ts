import type { ChildProcess } from "node:child_process";

/** Build output URL style: ``<slug>.html`` (file) or ``<slug>/index.html`` (dir). */
export type UrlStyle = "dir" | "file";
/** Internal link syntax: ``[text](Page.md)`` (standard) or ``[[Page]]`` (wikilink). */
export type LinkStyle = "standard" | "wikilink";
/** Output formats for SPARQL query results. */
export type QueryFormat =
  "table" | "json" | "csv" | "tsv" | "turtle" | "n3" | "markdown";
/** MCP server transport mode. */
export type McpMode = "stdio";
/** Output formats for RDF export. */
export type ExportFormat =
  "dict" | "json-ld" | "turtle" | "xml" | "n3" | "nt" | "trig" | "nquads";
/** JSON-LD serialization mode. */
export type ExportMode = "expanded" | "compacted";

/** Options for loading a Wiki instance. */
export interface WikiLoadOptions {
  /** Path to ``wiki.yml`` (or directory containing it). */
  config?: string;
  /** Override ``wiki.inputs`` from the config file. */
  wikiInputs?: readonly string[];
  /** Working directory for the wiki CLI subprocess. */
  cwd?: string;
  /** Environment variables for the wiki CLI subprocess. */
  env?: NodeJS.ProcessEnv;
}

/** Low-level options for ``Wiki.run()``. */
export interface RunOptions {
  /** Working directory for the subprocess. */
  cwd?: string;
  /** Extra environment variables. */
  env?: NodeJS.ProcessEnv;
  /** String to pipe to stdin. */
  stdin?: string;
  /** Kill the command after this many milliseconds. */
  timeoutMs?: number;
  /** Whether to throw on non-zero exit (default ``true``). */
  throwOnError?: boolean;
  /** AbortSignal for cancellation. */
  signal?: AbortSignal;
}

/** Result returned by ``Wiki.run()`` and most command methods. */
export interface WikiCommandResult {
  /** ``true`` when the CLI exited with code 0. */
  ok: boolean;
  /** The numeric exit code. */
  exitCode: number;
  /** Stdout content. */
  stdout: string;
  /** Stderr content. */
  stderr: string;
  /** The full argv array passed to the CLI. */
  command: readonly string[];
}

/** Mixin for methods that accept a ``files`` filter. */
export interface FilesOption {
  /** Subset of wiki files to operate on. Omit for whole-wiki mode. */
  files?: readonly string[];
}

/** Shared options for check and lint. */
export interface StrictOption extends FilesOption {
  /** Elevate all warnings to errors. */
  strict?: boolean;
  /** Print detailed audit output. */
  verbose?: boolean;
}

/** Options for ``Wiki.check()``. */
export type CheckOptions = StrictOption;
/** Options for ``Wiki.lint()``. */
export type LintOptions = StrictOption;

/** Options for ``Wiki.preflight()``. */
export interface PreflightOptions {
  /** Elevate all warnings to errors. */
  strict?: boolean;
  /** Print detailed audit output. */
  verbose?: boolean;
}

/** Options for ``Wiki.build()``. */
export interface BuildOptions {
  /** Target directory (default ``"_site"``). */
  outputDir?: string;
  /** Override ``site.base_url``. */
  baseUrl?: string;
  /** Override ``site.url_style`` (``"file"`` or ``"dir"``). */
  urlStyle?: UrlStyle;
  /** Render inline SPARQL blocks before building. */
  render?: boolean;
  /** Rebuild the graph before rendering. */
  reload?: boolean;
  /** Persist the graph to disk. */
  cache?: boolean;
  /** Skip lint + check preflight. */
  noCheck?: boolean;
  /** Print generated file paths. */
  verbose?: boolean;
}

/** Options for ``Wiki.fmt()``. */
export interface FmtOptions extends FilesOption {
  /** Report formatting issues without modifying files. */
  check?: boolean;
  /** Print per-file formatting status. */
  verbose?: boolean;
}

/** Options for ``Wiki.render()``. */
export interface RenderOptions extends FilesOption {
  /** Detect stale blocks without modifying files. */
  check?: boolean;
  /** Rebuild the graph before rendering. */
  reload?: boolean;
  /** Persist the graph to disk. */
  cache?: boolean;
  /** Skip OWL-RL inference. */
  noInference?: boolean;
  /** Print summary of updated files. */
  verbose?: boolean;
}

/** Options for ``Wiki.export()``. */
export interface ExportOptions extends FilesOption {
  /** Output file path. */
  output?: string;
  /** RDF serialization format. */
  format?: ExportFormat;
  /** JSON-LD mode (``"expanded"`` or ``"compacted"``). */
  mode?: ExportMode;
  /** Automatically parse JSON output into ``data`` field. */
  parseJson?: boolean;
}

/** Extended result from ``Wiki.export()`` with parsed JSON data. */
export interface ExportResult<T = unknown> extends WikiCommandResult {
  /** Parsed output data when ``parseJson`` is enabled. */
  data?: T;
}

/** Options for ``Wiki.link()``. */
export interface LinkOptions extends FilesOption {
  /** Insert suggested internal links. */
  apply?: boolean;
  /** Repair unambiguous broken internal links. */
  fixBroken?: boolean;
  /** Preview changes without writing files. */
  dryRun?: boolean;
  /** Exit with code 1 if opportunities or broken links remain. */
  check?: boolean;
  /** Show target titles; list changed files. */
  verbose?: boolean;
}

/** Options for ``Wiki.query()``. */
export interface QueryOptions {
  /** The SPARQL query string (required). */
  query: string;
  /** Output format. */
  format?: QueryFormat;
  /** Write output to a file. */
  output?: string;
  /** Skip OWL-RL inference. */
  noInference?: boolean;
  /** Rebuild the graph before querying. */
  reload?: boolean;
  /** Persist the graph to disk. */
  cache?: boolean;
  /** Key-path filter for JSON output (implies ``format="json"``). */
  jq?: string;
  /** Render a rich table (stdout only). */
  pretty?: boolean;
  /** Print graph statistics before results. */
  verbose?: boolean;
  /** Automatically parse JSON output. */
  parseJson?: boolean;
}

/** Options for ``Wiki.serve()``. */
export interface ServeOptions {
  /** Host to bind the server to. */
  host?: string;
  /** Port to serve on. */
  port?: number;
  /** Override ``site.base_url``. */
  baseUrl?: string;
  /** Override ``site.url_style`` (``"file"`` or ``"dir"``). */
  urlStyle?: UrlStyle;
  /** Watch for file changes and auto-rebuild. */
  watch?: boolean;
  /** Working directory for the subprocess. */
  cwd?: string;
  /** Extra environment variables. */
  env?: NodeJS.ProcessEnv;
}

/** Options for ``Wiki.mcp()``. */
export interface McpOptions {
  /** MCP transport mode (default ``"stdio"``). */
  mode?: McpMode;
  /** Persist graph under ``.wiki/cache`` across MCP launches. */
  cache?: boolean;
  /** Working directory for the subprocess. */
  cwd?: string;
  /** Extra environment variables. */
  env?: NodeJS.ProcessEnv;
}

/** Runtime overrides applied to a Wiki session (immutable config copy). */
export interface RuntimeOptions {
  /** Override ``site.base_url`` for this session. */
  baseUrl?: string;
  /** Override ``site.url_style`` (``"file"`` or ``"dir"``). */
  urlStyle?: UrlStyle;
}

/** Options for ``Wiki.init()``. */
export interface InitOptions {
  /** Run ``git init`` after scaffolding. */
  git?: boolean;
  /** GitHub ``owner/repo`` string for inferring defaults. */
  repo?: string;
  /** Override ``graph.context.wiki`` IRI. */
  graphContextWiki?: string;
  /** Override ``site.base_url`` (default ``/wiki`` or inferred from ``--repo``). */
  baseUrl?: string;
  /** Override ``site.url_style`` (``"file"`` or ``"dir"``). */
  urlStyle?: UrlStyle;
  /** Override ``graph.content_predicate``. */
  graphContentPredicate?: string;
  /** Override ``link.style`` (``"standard"`` or ``"wikilink"``). */
  linkStyle?: LinkStyle;
  /** Override ``wiki.inputs`` (repeatable). */
  wikiInputs?: readonly string[];
  /** Override ``graph.base_iri``. */
  graphBaseIri?: string;
  /** Default types for untyped documents. */
  graphImplicitTypes?: readonly string[];
  /** Strategy when applying ``graph.implicit_types``. */
  graphImplicitTypesPolicy?: "fallback" | "append";
  /** Override ``graph.include_file_extension``. */
  graphIncludeFileExtension?: boolean;
}

/** Options for ``Wiki.upgrade()``. */
export interface UpgradeOptions {
  /** Check for updates without upgrading. Exits 1 if outdated. */
  check?: boolean;
  /** Skip confirmation prompt. */
  yes?: boolean;
  /** Show pip install output. */
  verbose?: boolean;
}

/** Result of ``Wiki.preflight()`` — lint and check reports. */
export interface PreflightResult {
  /** Lint audit result. */
  lint: WikiCommandResult;
  /** Check audit result. */
  check: WikiCommandResult;
}

/** The child process returned by ``Wiki.serve()``. */
export type ServeProcess = ChildProcess;
/** The child process returned by ``Wiki.mcp()``. */
export type McpProcess = ChildProcess;
