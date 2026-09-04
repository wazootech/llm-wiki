const assert = require('assert');
const { Wiki } = require('./dist/index.js');

class TestWiki extends Wiki {
  constructor(options, result) {
    super(options);
    this.result = result || { ok: true, exitCode: 0, stdout: '', stderr: '', command: [] };
    this.calls = [];
  }

  run(args) {
    this.calls.push(args);
    return Promise.resolve({ ...this.result, command: args });
  }
}

async function main() {
  const esm = await import('./dist/index.mjs');
  assert.strictEqual(typeof esm.Wiki, 'function');

  const wiki = new TestWiki({ config: 'docs/wiki.yml', wikiInputs: ['docs/wiki'], cwd: 'repo' });
  assert.deepStrictEqual(wiki.args('check', ['--strict', 'docs/wiki/Page.md']), [
    '--wiki-inputs',
    'docs/wiki',
    '--config',
    'docs/wiki.yml',
    'check',
    '--strict',
    'docs/wiki/Page.md',
  ]);

  await wiki.build({ outputDir: '_site', baseUrl: '', urlStyle: 'file', render: true, cache: true, noCheck: true });
  assert.deepStrictEqual(wiki.calls.at(-1), [
    '--wiki-inputs',
    'docs/wiki',
    '--config',
    'docs/wiki.yml',
    'build',
    '--output-dir',
    '_site',
    '--site-base-url',
    '',
    '--site-url-style',
    'file',
    '--render',
    '--cache',
    '--no-check',
  ]);

  await wiki.link({ apply: true, fixBroken: true, dryRun: true, check: true, verbose: true, files: ['Page.md'] });
  assert.deepStrictEqual(wiki.calls.at(-1), [
    '--wiki-inputs',
    'docs/wiki',
    '--config',
    'docs/wiki.yml',
    'link',
    '--apply',
    '--fix-broken',
    '--dry-run',
    '--check',
    '--verbose',
    'Page.md',
  ]);

  const exportWiki = new TestWiki({}, { ok: true, exitCode: 0, stdout: '{"ok":true}', stderr: '', command: [] });
  const exportResult = await exportWiki.export();
  assert.deepStrictEqual(exportResult.data, { ok: true });

  const queryWiki = new TestWiki({}, { ok: true, exitCode: 0, stdout: '{"head":{},"results":{}}', stderr: '', command: [] });
  const queryResult = await queryWiki.query({ query: 'SELECT ?s WHERE { ?s ?p ?o }', format: 'json' });
  assert.deepStrictEqual(queryResult, { head: {}, results: {} });

  await wiki.graphList();
  assert.deepStrictEqual(wiki.calls.at(-1), [
    '--wiki-inputs',
    'docs/wiki',
    '--config',
    'docs/wiki.yml',
    'graph',
    'list',
  ]);

  assert.deepStrictEqual(wiki.args('mcp', ['--mode', 'stdio', '--cache']), [
    '--wiki-inputs',
    'docs/wiki',
    '--config',
    'docs/wiki.yml',
    'mcp',
    '--mode',
    'stdio',
    '--cache',
  ]);

  const initWiki = new TestWiki();
  await initWiki.init({
    git: true,
    repo: 'wazootech/wiki',
    linkStyle: 'standard',
    wikiInputs: ['wiki', 'docs/wiki'],
    graphImplicitTypes: ['schema:Thing'],
    graphIncludeFileExtension: false,
  });
  assert.deepStrictEqual(initWiki.calls.at(-1), [
    'init',
    '--git',
    '--repo',
    'wazootech/wiki',
    '--link-style',
    'standard',
    '--wiki-inputs',
    'wiki',
    '--wiki-inputs',
    'docs/wiki',
    '--graph-implicit-types',
    'schema:Thing',
    '--no-graph-include-file-extension',
  ]);

  const siteInitWiki = new TestWiki();
  await siteInitWiki.init({
    baseUrl: 'https://wiki.wazoo.dev',
    urlStyle: 'dir',
    siteLayout: 'docs',
    template: 'generic',
  });
  assert.deepStrictEqual(siteInitWiki.calls.at(-1), [
    'init',
    '--site-base-url',
    'https://wiki.wazoo.dev',
    '--site-url-style',
    'dir',
    '--site-layout',
    'docs',
    '--template',
    'generic',
  ]);

  await wiki.install();
  assert.deepStrictEqual(wiki.calls.at(-1), [
    '--wiki-inputs',
    'docs/wiki',
    '--config',
    'docs/wiki.yml',
    'install',
  ]);

  await wiki.install({ url: 'https://github.com/wazootech/wiki-templates.git' });
  assert.deepStrictEqual(wiki.calls.at(-1), [
    '--wiki-inputs',
    'docs/wiki',
    '--config',
    'docs/wiki.yml',
    'install',
    'https://github.com/wazootech/wiki-templates.git',
  ]);

  await wiki.update({ name: 'templates', dryRun: true });
  assert.deepStrictEqual(wiki.calls.at(-1), [
    '--wiki-inputs',
    'docs/wiki',
    '--config',
    'docs/wiki.yml',
    'update',
    '--dry-run',
    'templates',
  ]);

  await wiki.remove({ name: 'templates' });
  assert.deepStrictEqual(wiki.calls.at(-1), [
    '--wiki-inputs',
    'docs/wiki',
    '--config',
    'docs/wiki.yml',
    'remove',
    'templates',
  ]);

  console.log('npm Wiki API regression ok');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
