# Wiki CLI Agent Skill

[![skills.sh](https://skills.sh/b/wazootech/wiki)](https://skills.sh/wazootech/wiki)

One agent skill for [Wiki CLI](https://github.com/wazootech/wiki): install the CLI, scaffold a wiki project, audit hygiene, and deploy to GitHub Pages. Skills live under `skills/` and are **not** wiki content — do not add this folder to `wiki.input`.

Typical flow: **install** → **create** → **deploy** → **improve** (each optional; route to one workflow per turn).

| Skill                 | Purpose                                                                  |
| --------------------- | ------------------------------------------------------------------------ |
| [wiki](wiki/SKILL.md) | Install, `wiki init`, audit (fmt/lint/check/render), GitHub Pages deploy, Git-anchored delta sync of code wikis with opt-in `detail_level` |

## Install

```bash
npx skills add wazootech/wiki@wiki -g -y
```

Docs: [Wiki_Skills.md](../docs/wiki/Wiki_Skills.md). User walkthrough: [Getting_Started.md](../docs/wiki/Getting_Started.md).
