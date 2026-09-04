/**
 * GENERATED FILE — do not hand-edit.
 * Sources: scripts/export_cli_schemas.py (src/wiki/schemas/cli.py COMMAND_MODELS,
 * model_json_schema(by_alias=True)) compiled by json-schema-to-typescript.
 * Regenerate via: npm run gen:cli-types
 */

// Choice unions — named mirrors of the schema enums (public API aliases).

/** Override ``site.url_style`` (``"file"`` or ``"dir"``). */
export type UrlStyle = "dir" | "file";

/** RDF serialization format. */
export type ExportFormat =
  "dict" | "json-ld" | "turtle" | "xml" | "n3" | "nt" | "trig" | "nquads";

/** JSON-LD mode (``"expanded"`` or ``"compacted"``). */
export type ExportMode = "expanded" | "compacted";

/** Override ``link.style`` (``"standard"`` or ``"wikilink"``). */
export type LinkStyle = "standard" | "wikilink";

/** MCP transport mode (default ``"stdio"``). */
export type McpMode = "stdio";

/** Output format. */
export type QueryFormat =
  "table" | "json" | "csv" | "tsv" | "turtle" | "n3" | "markdown";

/**
 * Options for ``Wiki.build()``.
 */
export interface BuildOptions {
  /**
   * Target directory (default ``"_site"``).
   */
  outputDir?: string;
  /**
   * Override ``site.base_url``.
   */
  baseUrl?: string;
  /**
   * Override ``site.url_style`` (``"file"`` or ``"dir"``).
   */
  urlStyle?: "dir" | "file";
  /**
   * Render inline SPARQL blocks before building.
   */
  render?: boolean;
  /**
   * Rebuild the graph before rendering.
   */
  reload?: boolean;
  /**
   * Persist the graph to disk.
   */
  cache?: boolean;
  /**
   * Skip lint + check preflight.
   */
  noCheck?: boolean;
  /**
   * Print generated file paths.
   */
  verbose?: boolean;
}

/**
 * Options for ``Wiki.check()``.
 */
export interface CheckOptions {
  /**
   * Subset of wiki files to operate on. Omit for whole-wiki mode.
   */
  files?: readonly string[];
  /**
   * Print detailed audit output.
   */
  verbose?: boolean;
  /**
   * Elevate all warnings to errors.
   */
  strict?: boolean;
}

/**
 * Options for ``Wiki.export()``.
 */
export interface ExportOptions {
  /**
   * Subset of wiki files to operate on. Omit for whole-wiki mode.
   */
  files?: readonly string[];
  /**
   * Output file path.
   */
  output?: string;
  /**
   * RDF serialization format.
   */
  format?:
    "dict" | "json-ld" | "turtle" | "xml" | "n3" | "nt" | "trig" | "nquads";
  /**
   * JSON-LD mode (``"expanded"`` or ``"compacted"``).
   */
  mode?: "expanded" | "compacted";
}

/**
 * Options for ``Wiki.fmt()``.
 */
export interface FmtOptions {
  /**
   * Subset of wiki files to operate on. Omit for whole-wiki mode.
   */
  files?: readonly string[];
  /**
   * Report formatting issues without modifying files.
   */
  check?: boolean;
  /**
   * Print per-file formatting status.
   */
  verbose?: boolean;
}

/**
 * Options for ``Wiki.init()``.
 */
export interface InitOptions {
  /**
   * Run ``git init`` after scaffolding.
   */
  git?: boolean;
  /**
   * GitHub ``owner/repo`` string for inferring defaults.
   */
  repo?: string;
  /**
   * Override ``graph.context.wiki`` IRI.
   */
  graphContextWiki?: string;
  /**
   * Override ``site.base_url`` (default ``/wiki`` or inferred from ``--repo``).
   */
  baseUrl?: string;
  /**
   * Override ``site.url_style`` (``"file"`` or ``"dir"``).
   */
  urlStyle?: "dir" | "file";
  /**
   * Override ``site.layout``.
   */
  siteLayout?: string;
  /**
   * Override ``graph.content_predicate``.
   */
  graphContentPredicate?: string;
  /**
   * Override ``link.style`` (``"standard"`` or ``"wikilink"``).
   */
  linkStyle?: "standard" | "wikilink";
  /**
   * Override ``wiki.input`` (repeatable).
   */
  input?: readonly string[];
  /**
   * Override ``graph.base_iri``.
   */
  graphBaseIri?: string;
  /**
   * Default types for untyped documents.
   */
  graphImplicitTypes?: readonly string[];
  /**
   * Strategy when applying ``graph.implicit_types``.
   */
  graphImplicitTypesPolicy?: "fallback" | "append";
  /**
   * Override ``graph.include_file_extension``.
   */
  graphIncludeFileExtension?: boolean;
  /**
   * Scaffold from a starter template in wazootech/wiki-templates.
   */
  template?: string;
}

/**
 * Options for ``Wiki.install()``.
 */
export interface InstallOptions {
  /**
   * Git URL of an external source to add, fetch, and lock. Omit to install all declared sources.
   */
  url?: string;
}

/**
 * Options for ``Wiki.link()``.
 */
export interface LinkOptions {
  /**
   * Subset of wiki files to operate on. Omit for whole-wiki mode.
   */
  files?: readonly string[];
  /**
   * Insert suggested internal links.
   */
  apply?: boolean;
  /**
   * Repair unambiguous broken internal links.
   */
  fixBroken?: boolean;
  /**
   * Preview changes without writing files.
   */
  dryRun?: boolean;
  /**
   * Exit with code 1 if opportunities or broken links remain.
   */
  check?: boolean;
  /**
   * Show target titles; list changed files.
   */
  verbose?: boolean;
}

/**
 * Options for ``Wiki.lint()``.
 */
export interface LintOptions {
  /**
   * Subset of wiki files to operate on. Omit for whole-wiki mode.
   */
  files?: readonly string[];
  /**
   * Print detailed audit output.
   */
  verbose?: boolean;
  /**
   * Elevate all warnings to errors.
   */
  strict?: boolean;
}

/**
 * Options for ``Wiki.mcp()``.
 */
export interface McpOptions {
  /**
   * MCP transport mode (default ``"stdio"``).
   */
  mode?: "stdio";
  /**
   * Persist graph under ``.wiki/cache`` across MCP launches.
   */
  cache?: boolean;
}

/**
 * Options for ``Wiki.query()``.
 */
export interface QueryOptions {
  /**
   * The SPARQL query string (required).
   */
  query: string;
  /**
   * Output format.
   */
  format?: "table" | "json" | "csv" | "tsv" | "turtle" | "n3" | "markdown";
  /**
   * Write output to a file.
   */
  output?: string;
  /**
   * Skip OWL-RL inference.
   */
  noInference?: boolean;
  /**
   * Rebuild the graph before querying.
   */
  reload?: boolean;
  /**
   * Persist the graph to disk.
   */
  cache?: boolean;
  /**
   * Key-path filter for JSON output (implies ``format="json"``).
   */
  jq?: string;
  /**
   * Render a rich table (stdout only).
   */
  pretty?: boolean;
  /**
   * Print graph statistics before results.
   */
  verbose?: boolean;
}

/**
 * Options for ``Wiki.remove()``.
 */
export interface RemoveOptions {
  /**
   * Name of the source to remove.
   */
  name: string;
}

/**
 * Options for ``Wiki.render()``.
 */
export interface RenderOptions {
  /**
   * Subset of wiki files to operate on. Omit for whole-wiki mode.
   */
  files?: readonly string[];
  /**
   * Skip OWL-RL inference.
   */
  noInference?: boolean;
  /**
   * Rebuild the graph before rendering.
   */
  reload?: boolean;
  /**
   * Persist the graph to disk.
   */
  cache?: boolean;
  /**
   * Detect stale blocks without modifying files.
   */
  check?: boolean;
  /**
   * Print summary of updated files.
   */
  verbose?: boolean;
}

/**
 * Options for ``Wiki.serve()``.
 */
export interface ServeOptions {
  /**
   * Host to bind the server to.
   */
  host?: string;
  /**
   * Port to serve on.
   */
  port?: number;
  /**
   * Override ``site.base_url``.
   */
  baseUrl?: string;
  /**
   * Override ``site.url_style`` (``"file"`` or ``"dir"``).
   */
  urlStyle?: "dir" | "file";
  /**
   * Watch for file changes and auto-rebuild.
   */
  watch?: boolean;
}

/**
 * Options for ``Wiki.update()``.
 */
export interface UpdateOptions {
  /**
   * Source name to check; omit to check all locked sources.
   */
  name?: string;
  /**
   * Report what would update without modifying wiki.lock.
   */
  dryRun?: boolean;
}

/**
 * Options for ``Wiki.upgrade()``.
 */
export interface UpgradeOptions {
  /**
   * Check for updates without upgrading. Exits 1 if outdated.
   */
  check?: boolean;
  /**
   * Skip confirmation prompt.
   */
  yes?: boolean;
  /**
   * Show pip install output.
   */
  verbose?: boolean;
}
