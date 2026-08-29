"""Click CLI entrypoint defining subcommands and option handling."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

from . import __version__
from . import upgrade as upgrade_module
from .cli_output import exit_audit_report, print_check_messages
from .errors import BuildError, UpgradeError
from .format_choice import FormatChoice
from .graph import graph_stats
from .init_scaffold import parse_github_repo, resolve_init_options
from .upgrade import PACKAGE_NAME, check_version, perform_upgrade
from .wiki import Wiki, _uses_named_graphs

FILE_COMMANDS = ("check", "lint", "link", "render", "export", "fmt")


def optional_files_argument(f):
    """Decorator: zero or more FILE positionals (``nargs=-1``).

    Handlers receive ``files: tuple[Path, ...]``. Omit FILE for whole-wiki mode.
    """
    return click.argument(
        "files",
        nargs=-1,
        required=False,
        type=click.Path(exists=True, path_type=Path),
    )(f)


@click.group()
@click.version_option(version=__version__, prog_name="wiki")
@click.option(
    "--wiki-inputs",
    "wiki_inputs",
    multiple=True,
    default=None,
    help="Override wiki.inputs from config file (.md, .yaml, .json, .toml; repeatable).",
)
@click.option(
    "-c",
    "--config",
    "config_path",
    default=".",
    help="Path to wiki config file or directory containing wiki.yml/wiki.yaml/wiki.json/wiki.toml (default: current directory).",
)
@click.pass_context
def main(ctx: click.Context, wiki_inputs: tuple[str, ...] | None, config_path: str) -> None:
    """Query, validate, and manage your semantic LLM wiki."""
    try:
        wiki = Wiki.load(
            config_path,
            wiki_inputs=list(wiki_inputs) if wiki_inputs else None,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    ctx.obj = wiki


@main.command()
@optional_files_argument
@click.option("-v", "--verbose", is_flag=True, help="Show integrity audit warnings.")
@click.option("--strict", is_flag=True, help="Elevate all warnings to errors and exit with code 1.")
@click.pass_obj
def check(wiki: Wiki, files: tuple[Path, ...], verbose: bool, strict: bool) -> None:
    """Integrity checks: SHACL, JSON Schema, routes, collisions, layout (FILE...: SHACL + JSON Schema)."""
    try:
        report = wiki.check(list(files) if files else None, strict=strict)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    exit_audit_report(report, verbose=verbose, strict=strict)


@main.command()
@optional_files_argument
@click.option("-v", "--verbose", is_flag=True, help="Show convention audit warnings.")
@click.option("--strict", is_flag=True, help="Elevate all warnings to errors and exit with code 1.")
@click.pass_obj
def lint(wiki: Wiki, files: tuple[Path, ...], verbose: bool, strict: bool) -> None:
    """Convention audits: links, filenames, headings, and link style."""
    try:
        report = wiki.lint(list(files) if files else None, strict=strict)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    exit_audit_report(report, verbose=verbose, strict=strict)


@main.command()
@optional_files_argument
@click.option("--apply", is_flag=True, help="Insert suggested internal links (format from link.style in config file).")
@click.option("--fix-broken", is_flag=True, help="Repair unambiguous broken internal links.")
@click.option("-n", "--dry-run", is_flag=True, help="Preview apply/fix changes without writing files.")
@click.option("-c", "--check", is_flag=True, help="Exit 1 if link opportunities or broken links remain.")
@click.option("-v", "--verbose", is_flag=True, help="Show target titles in suggestions; list changed files when applying.")
@click.pass_obj
def link(
    wiki: Wiki,
    files: tuple[Path, ...],
    apply: bool,
    fix_broken: bool,
    dry_run: bool,
    check: bool,
    verbose: bool,
) -> None:
    """Suggest or repair internal links for wiki pages."""
    try:
        report = wiki.link(
            list(files) if files else None,
            apply=apply,
            fix_broken=fix_broken,
            dry_run=dry_run,
            check=check,
            verbose=verbose,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    for line in report.lines:
        click.echo(line)
    if fix_broken and report.fixes and verbose:
        prefix = "would fix" if dry_run else "fixed"
        for changed_path in report.changed_paths:
            click.echo(f"{prefix} {changed_path}")
    elif apply and report.changed_paths and (verbose or dry_run):
        prefix = "would update" if dry_run else "updated"
        for changed_path in report.changed_paths:
            click.echo(f"{prefix} {changed_path}")

    if check and not report.ok:
        sys.exit(1)
    if fix_broken and not apply:
        sys.exit(0)
    if apply:
        sys.exit(0)
    if report.opportunities == 0:
        sys.exit(0)
    sys.exit(1 if check else 0)


@main.group()
def graph() -> None:
    """Inspect read-only RDF named graph provenance."""


@graph.command(name="list")
@click.pass_obj
def graph_list(wiki: Wiki) -> None:
    """List named graphs available to SPARQL GRAPH queries."""
    descriptors = wiki.graphs()
    rows = [
        (
            descriptor.name,
            descriptor.kind,
            descriptor.uri,
            descriptor.resolved_ref[:12] if descriptor.resolved_ref else "",
            ",".join(descriptor.required_by) if descriptor.required_by else "",
        )
        for descriptor in descriptors
    ]
    headers = ("name", "kind", "uri", "commit", "required_by")
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    click.echo("  ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers)))
    click.echo("  ".join("-" * width for width in widths))
    for row in rows:
        click.echo("  ".join(value.ljust(widths[idx]) for idx, value in enumerate(row)))


@main.command()
@click.argument("query_args", nargs=-1, required=False)
@click.option(
    "-f",
    "--format",
    "output_format",
    type=FormatChoice(
        ["table", "json", "csv", "tsv", "turtle", "n3", "markdown"],
        case_sensitive=False,
    ),
    default="table",
    show_default=True,
    help="Output format for query results.",
)
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Write output to specified file.")
@click.option("--no-inference", is_flag=True, help="Skip OWL-RL inference.")
@click.option("--reload", is_flag=True, help="Rebuild the in-memory graph from wiki sources.")
@click.option(
    "--cache",
    "disk_cache",
    is_flag=True,
    help="Persist the graph under .wiki/cache for faster reuse across new CLI processes.",
)
@click.option("--jq", default=None, help="Extract values from JSON output using a key-path filter (implies -f json).")
@click.option(
    "--pretty",
    is_flag=True,
    help="Rich table for SELECT results (stdout only; not with -o or --jq).",
)
@click.option("-v", "--verbose", is_flag=True, help="Print graph statistics before query results.")
@click.pass_obj
def query(
    wiki: Wiki,
    query_args: tuple[str, ...],
    output_format: str,
    output: Path | None,
    no_inference: bool,
    reload: bool,
    disk_cache: bool,
    jq: str | None,
    pretty: bool,
    verbose: bool,
) -> None:
    """Run SPARQL SELECT or CONSTRUCT (query argument or stdin)."""
    if query_args:
        sparql_query = " ".join(query_args)
    elif not sys.stdin.isatty():
        sparql_query = sys.stdin.read()
    else:
        click.echo("Error: No query provided.", err=True)
        sys.exit(1)

    if pretty:
        if output is not None:
            click.echo("Error: --pretty writes to stdout only; do not use -o/--output.", err=True)
            sys.exit(1)
        if jq is not None:
            click.echo("Error: --pretty is incompatible with --jq.", err=True)
            sys.exit(1)
        if output_format != "table":
            click.echo("Error: --pretty only supports table format (default -f table).", err=True)
            sys.exit(1)

    if verbose:
        if _uses_named_graphs(sparql_query):
            graph = wiki.dataset(infer=not no_inference, reload=reload, disk_cache=disk_cache)
        else:
            graph = wiki.graph(infer=not no_inference, reload=reload, disk_cache=disk_cache)
        stats = graph_stats(graph)
        click.echo(f"Graph stats: {stats['triples']} triples, {stats['subjects']} subjects\n")

    try:
        result = wiki.query(
            sparql_query,
            format=output_format,
            no_inference=no_inference,
            reload=reload,
            cache=disk_cache,
            jq=jq,
            pretty=pretty,
        )
        if output:
            output.write_text(result, encoding="utf-8")
            click.echo(f"Written results to {output}")
        else:
            click.echo(result)
    except (ValueError, SyntaxError, TypeError, RuntimeError) as exc:
        click.echo(f"Query Execution Error: {exc}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--mode",
    type=click.Choice(["stdio"], case_sensitive=False),
    default="stdio",
    show_default=True,
    help="MCP transport mode.",
)
@click.option(
    "--cache",
    "disk_cache",
    is_flag=True,
    help="Persist graph under .wiki/cache for faster reuse across MCP launches.",
)
@click.pass_obj
def mcp(wiki: Wiki, mode: str, disk_cache: bool) -> None:
    """Start a read-only MCP server for the wiki graph."""
    from .mcp import run_mcp_server

    try:
        run_mcp_server(wiki, mode=mode.lower(), disk_cache=disk_cache)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


@main.command()
@optional_files_argument
@click.option("--no-inference", is_flag=True, help="Skip OWL-RL inference.")
@click.option("--reload", is_flag=True, help="Rebuild the in-memory graph from wiki sources before rendering.")
@click.option(
    "--cache",
    "disk_cache",
    is_flag=True,
    help="Persist the graph under .wiki/cache for faster reuse across new CLI processes.",
)
@click.option(
    "--check",
    is_flag=True,
    help="Check if inline SPARQL blocks are up to date without modifying files. Exits with non-zero code if any are stale.",
)
@click.option("-v", "--verbose", is_flag=True, help="Print summary of updated files.")
@click.pass_obj
def render(
    wiki: Wiki,
    files: tuple[Path, ...],
    no_inference: bool,
    reload: bool,
    disk_cache: bool,
    check: bool,
    verbose: bool,
) -> None:
    """Render inline SPARQL blocks in markdown files."""
    try:
        report = wiki.render(
            list(files) if files else None,
            check=check,
            reload=reload,
            cache=disk_cache,
            no_inference=no_inference,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    for error in report.render_errors:
        click.echo(error, err=True)

    if check:
        if report.stale_files:
            click.echo("Error: Inline SPARQL blocks are out of date in the following files:", err=True)
            for stale in report.stale_files:
                click.echo(f"  - {stale}", err=True)
            sys.exit(1)
        if verbose:
            click.echo("All dynamic SPARQL blocks are fully up to date.")
        return

    if verbose:
        parts = [f"Updated {report.updated_count} files"]
        if report.error_count:
            parts.append(f"{report.error_count} errors")
        click.echo(f"Rendered SPARQL: {', '.join(parts)}.")


@main.command()
@click.option(
    "--output-dir",
    default="_site",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Directory to write site files.",
)
@click.option(
    "--site-base-url",
    "site_base_url",
    default=None,
    help="Override site.base_url. Empty string for root-level URLs.",
)
@click.option(
    "--site-url-style",
    "site_url_style",
    type=click.Choice(["file", "dir"]),
    default=None,
    help="Override site.url_style: <slug>.html (file) or <slug>/index.html (dir).",
)
@click.option("--render", is_flag=True, help="Render inline SPARQL blocks before building.")
@click.option("--reload", is_flag=True, help="Rebuild graph before --render (no effect without --render).")
@click.option("--cache", "disk_cache", is_flag=True, help="Persist graph under .wiki/cache when using --render.")
@click.option("--no-check", is_flag=True, help="Skip lint and check preflight before building.")
@click.option("-v", "--verbose", is_flag=True, help="Print generated file paths.")
@click.pass_obj
def build(
    wiki: Wiki,
    output_dir: Path,
    site_base_url: str | None,
    site_url_style: str | None,
    render: bool,
    reload: bool,
    disk_cache: bool,
    no_check: bool,
    verbose: bool,
) -> None:
    """Build static HTML site from wiki documents."""
    try:
        result = wiki.build(
            output_dir,
            base_url=site_base_url,
            url_style=site_url_style,
            render=render,
            reload=reload,
            cache=disk_cache,
            no_check=no_check,
            verbose=verbose,
        )
    except BuildError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if render and verbose and result.ok:
        click.echo("Rendered SPARQL dynamic blocks before build.")

    if not result.ok:
        if result.error_message:
            click.echo(f"Error: {result.error_message}", err=True)
            sys.exit(1)
        if result.preflight is not None:
            errors, warnings = result.preflight.messages()
            print_check_messages(errors, warnings, verbose)
            sys.exit(1)

    if verbose:
        for rel_path in result.written_paths:
            click.echo(f"  {rel_path}")
        click.echo(
            f"\nBuilt {result.page_count} pages and {result.asset_count} assets to {output_dir}"
        )


@main.command()
@optional_files_argument
@click.option("-o", "--output", type=click.Path(path_type=Path), help="File to write serialized RDF output.")
@click.option(
    "-f",
    "--format",
    "rdf_format",
    type=FormatChoice(
        ["dict", "json-ld", "turtle", "xml", "n3", "nt", "trig", "nquads"],
        case_sensitive=False,
    ),
    default="dict",
    show_default=True,
    help="Output format for RDF export.",
)
@click.option(
    "--mode",
    type=click.Choice(["expanded", "compacted"], case_sensitive=False),
    default="expanded",
    show_default=True,
    help="Serialization mode for formats that support compaction.",
)
@click.pass_obj
def export(
    wiki: Wiki,
    files: tuple[Path, ...],
    output: Path | None,
    rdf_format: str,
    mode: str,
) -> None:
    """Export document frontmatter as RDF or JSON-LD."""
    try:
        result = wiki.export(
            list(files) if files else None,
            format=rdf_format,
            mode=mode,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if not result.ok:
        click.echo(f"Error: {result.error_message}", err=True)
        sys.exit(1)

    _raw_formats = {"turtle", "xml", "n3", "nt", "trig", "nquads"}
    if output:
        output.write_text(result.output, encoding="utf-8")
        if rdf_format in _raw_formats and (not files or len(files) == 1):
            click.echo(f"Written {rdf_format} output to {output}")
        else:
            desc = "payload array" if files and len(files) != 1 else "payload"
            click.echo(f"Written {desc} to {output}")
    else:
        click.echo(result.output)


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind the server to.")
@click.option("--port", default=8080, type=int, show_default=True, help="Port to serve on.")
@click.option(
    "--site-base-url",
    "site_base_url",
    default=None,
    help="Override site.base_url. Empty string for root-level URLs.",
)
@click.option(
    "--site-url-style",
    "site_url_style",
    default=None,
    type=click.Choice(["file", "dir"]),
    help="Override site.url_style: <slug>.html (file) or <slug>/ (dir).",
)
@click.option(
    "--watch",
    is_flag=True,
    help="Watch wiki; rebuild graph, SPARQL blocks, site, and reload browser.",
)
@click.pass_obj
def serve(
    wiki: Wiki,
    host: str,
    port: int,
    site_base_url: str | None,
    site_url_style: str | None,
    watch: bool,
) -> None:
    """Start a local HTTP server for browsing the wiki."""
    wiki.serve(
        host=host,
        port=port,
        base_url=site_base_url,
        url_style=site_url_style,
        watch=watch,
    )


@main.command()
@click.option("--git", "init_git", is_flag=True, help="Run git init after scaffolding the wiki project.")
@click.option(
    "--repo",
    default=None,
    help="GitHub owner/repo; infer graph.context.wiki and site.base_url for GitHub Pages.",
)
@click.option(
    "--graph-context-wiki",
    "graph_context_wiki",
    default=None,
    help="Override graph.context.wiki (overrides --repo inference).",
)
@click.option(
    "--site-base-url",
    "site_base_url",
    default=None,
    help="Override site.base_url (default /wiki or inferred from --repo).",
)
@click.option(
    "--site-url-style",
    "site_url_style",
    type=click.Choice(["file", "dir"]),
    default=None,
    help="Override site.url_style.",
)
@click.option(
    "--site-layout",
    "site_layout",
    default=None,
    help="Override site.layout.",
)
@click.option(
    "--graph-content-predicate",
    "graph_content_predicate",
    default=None,
    help="Override graph.content_predicate.",
)
@click.option(
    "--link-style",
    "link_style",
    type=click.Choice(["standard", "wikilink"]),
    default=None,
    help="Override link.style.",
)
@click.option(
    "--wiki-inputs",
    "wiki_inputs",
    multiple=True,
    default=None,
    help="Override wiki.inputs (repeatable).",
)
@click.option("--graph-base-iri", "graph_base_iri", default=None, help="Override graph.base_iri.")
@click.option(
    "--graph-implicit-types",
    "graph_implicit_types",
    type=str,
    multiple=True,
    help="Default types applied to untyped documents.",
)
@click.option(
    "--graph-implicit-types-policy",
    "graph_implicit_types_policy",
    type=click.Choice(["fallback", "append"]),
    default=None,
    help="Strategy when applying graph.implicit_types.",
)
@click.option(
    "--graph-include-file-extension/--no-graph-include-file-extension",
    "graph_include_file_extension",
    default=None,
    help="Override graph.include_file_extension.",
)
def init(
    init_git: bool,
    repo: str | None,
    graph_context_wiki: str | None,
    site_base_url: str | None,
    site_url_style: str | None,
    site_layout: str | None,
    graph_content_predicate: str | None,
    link_style: str | None,
    wiki_inputs: tuple[str, ...],
    graph_base_iri: str | None,
    graph_implicit_types: tuple[str, ...],
    graph_implicit_types_policy: str | None,
    graph_include_file_extension: bool | None,
) -> None:
    """Scaffold a new wiki project in the current directory."""
    cwd = Path.cwd()
    config_path = cwd / "wiki.yml"
    legacy_config_paths = (
        cwd / "wiki.yaml",
        cwd / "wiki.json",
        cwd / "wiki.toml",
    )
    readme_path = cwd / "README.md"
    wiki_dir = cwd / "wiki"

    if config_path.exists() or any(p.exists() for p in legacy_config_paths):
        click.echo(
            "Error: wiki.yml/wiki.yaml/wiki.json/wiki.toml already exists. Use a new directory or remove the config file.",
            err=True,
        )
        sys.exit(1)
    if readme_path.exists():
        click.echo(
            "Error: README.md already exists. Use a new directory or remove README.md.",
            err=True,
        )
        sys.exit(1)
    if wiki_dir.exists() and any(wiki_dir.iterdir()):
        click.echo(
            "Error: wiki/ is not empty. Use a new directory or clear wiki/ before init.",
            err=True,
        )
        sys.exit(1)

    if repo is not None:
        try:
            parse_github_repo(repo)
        except ValueError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)

    def prompt_context_wiki(default: str) -> str:
        return str(click.prompt("Custom wiki namespace IRI (graph.context.wiki)", default=default))

    init_options = resolve_init_options(
        repo=repo,
        graph_context_wiki=graph_context_wiki,
        site_base_url=site_base_url,
        site_url_style=site_url_style,
        site_layout=site_layout,
        graph_content_predicate=graph_content_predicate,
        link_style=link_style,
        cwd=cwd,
        init_git=init_git,
        prompt_context_wiki=prompt_context_wiki,
        wiki_inputs=list(wiki_inputs) if wiki_inputs else None,
        graph_base_iri=graph_base_iri,
        graph_implicit_types=list(graph_implicit_types) if graph_implicit_types else None,
        graph_implicit_types_policy=graph_implicit_types_policy,
        graph_include_file_extension=graph_include_file_extension,
    )

    result = Wiki.init(cwd, init_options, git=init_git)
    if not result.ok:
        click.echo(f"Error: {result.error_message}", err=True)
        sys.exit(1)
    click.echo(result.message)


@main.command()
@optional_files_argument
@click.option(
    "--check",
    is_flag=True,
    help="Check formatting without writing files back. Exits with code 1 if any files would change.",
)
@click.option("-v", "--verbose", is_flag=True, help="Print fmt config source and formatted file names.")
@click.pass_obj
def fmt(wiki: Wiki, files: tuple[Path, ...], check: bool, verbose: bool) -> None:
    """Format markdown wiki pages using mdformat."""
    from .fmt_util import describe_fmt_source

    try:
        if verbose and files:
            click.echo(f"Using {describe_fmt_source(files[0], wiki.config)}.")
        elif verbose and not files:
            from .paths import iter_markdown_files

            markdown_files = iter_markdown_files(wiki.config)
            if markdown_files:
                click.echo(f"Using {describe_fmt_source(markdown_files[0], wiki.config)}.")

        report = wiki.format(
            list(files) if files else None,
            check=check,
            verbose=verbose,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    for line in report.verbose_lines:
        click.echo(line)

    if check:
        if report.stale_files:
            click.echo("Error: The following files are not correctly formatted:", err=True)
            for stale in report.stale_files:
                click.echo(f"  - {stale.name}", err=True)
            sys.exit(1)
        if verbose:
            click.echo("All files are correctly formatted.")
        return

    if not report.ok:
        click.echo(report.error_message, err=True)
        sys.exit(1)

    if report.formatted_count > 0:
        click.echo(f"Format complete. Reformatted {report.formatted_count} files.")


@main.command()
@click.argument("url", required=False, default=None)
@click.pass_obj
def install(wiki: Wiki, url: str | None) -> None:
    """Fetch and lock external data sources.

    With no arguments, installs all sources declared in the config file and
    updates wiki.lock.

    With a URL, adds a new git source to the config file, fetches it,
    and locks it. Append \x23<ref> to pin a branch, tag, or commit.
    """
    from .sources import install as install_sources

    try:
        lockfile = install_sources(wiki.config, url)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    count = len(lockfile.sources)
    if count == 0:
        click.echo("No sources to install.")
        return

    click.echo(f"Locked {count} source{'s' if count != 1 else ''}.")
    for name, locked in lockfile.sources.items():
        click.echo(f"  {name}: {locked.resolved_ref[:12]} ({locked.fetched_at})")


@main.command(hidden=True)
@click.argument("url", required=False, default=None)
@click.pass_obj
def i(wiki: Wiki, url: str | None) -> None:
    """Alias for install."""
    install(wiki, url)


@main.command()
@click.argument("name", required=False, default=None)
@click.option("-n", "--dry-run", is_flag=True, help="Show what would update without modifying wiki.lock.")
@click.pass_obj
def update(wiki: Wiki, name: str | None, dry_run: bool) -> None:
    """Check locked sources for newer commits and update wiki.lock.

    Fetches each source, resolves the current HEAD (or pinned ref), and
    compares against the locked SHA. With --dry-run, reports what would
    change without writing. With a NAME argument, checks only that source.
    """
    from .sources import update as update_sources

    try:
        result = update_sources(wiki.config, name, dry_run=dry_run)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    if not result.updates:
        click.echo("No sources to update.")
        return

    changed = result.changed
    if not changed:
        click.echo("All sources are up to date.")
        return

    for u in changed:
        action = "would update" if dry_run else "updated"
        click.echo(f"{action} {u.name}: {u.previous_ref} -> {u.current_ref}")

    if not dry_run:
        click.echo(f"Updated {len(changed)} source{'s' if len(changed) != 1 else ''} in wiki.lock.")


@main.command()
@click.argument("name")
@click.pass_obj
def remove(wiki: Wiki, name: str) -> None:
    """Remove a source from the config file, its cache, and wiki.lock."""
    from .sources import remove as remove_source

    try:
        remove_source(wiki.config, name)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Removed source {name!r}.")


@main.command()
@click.option("-c", "--check", "check_only", is_flag=True, help="Check for updates without upgrading.")
@click.option("-y", "--yes", "auto_yes", is_flag=True, help="Skip confirmation prompt and upgrade immediately.")
@click.option("-v", "--verbose", is_flag=True, help="Show pip install output.")
def upgrade(check_only: bool, auto_yes: bool, verbose: bool) -> None:
    """Check for updates and upgrade the wiki CLI."""
    current, latest, is_outdated = check_version()
    path_warning = upgrade_module.get_windows_path_mismatch_warning()

    if current is None:
        click.echo("Error: cannot determine current version (package not found?).", err=True)
        sys.exit(1)

    if latest is None:
        click.echo("Error: cannot reach PyPI to check for updates.", err=True)
        sys.exit(1)

    if is_outdated:
        click.echo(f"Update available: {current} -> {latest}")
    else:
        click.echo(f"You're up to date ({current}).")

    if path_warning:
        click.echo(path_warning, err=True)

    if check_only:
        sys.exit(0 if not is_outdated else 1)

    if not is_outdated:
        return

    if not auto_yes:
        click.confirm("Upgrade now?", default=True, abort=True)

    try:
        if verbose:
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE_NAME]
            click.echo(f"Running: {' '.join(cmd)}")
        perform_upgrade(verbose=verbose)
        click.echo(f"Upgraded to {latest}.")
    except UpgradeError as exc:
        raise click.ClickException(str(exc)) from exc
    except subprocess.SubprocessError as exc:
        click.echo(f"Upgrade failed: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
