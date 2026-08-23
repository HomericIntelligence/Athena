# athena-opencode

[Athena](https://github.com/HomericIntelligence/Athena) workflow skills packaged as an
[opencode](https://opencode.ai) plugin. Installing this plugin places the full canonical skill
corpus under your opencode configuration directory, where opencode discovers and loads it natively.

## Install

Add the package to the `plugin` array of your opencode configuration
(`~/.config/opencode/opencode.json` or a project `opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["@homericintelligence/athena-opencode"]
}
```

Quit and restart opencode. On startup the plugin copies the bundled `skills/` corpus to:

```
$XDG_CONFIG_HOME/opencode/skills/athena/
```

(`~/.config/opencode/skills/athena/` by default.) The plugin only ever writes inside that
`athena/` namespace; other skills in your configuration are never touched. Each restart refreshes
the namespace to match the installed plugin version, so upgrading the npm package upgrades the
skills.

## Use

Invoke skills through opencode's native skill mechanism, for example by asking opencode to use the
`repo-review`, `pr-review`, or `plan-issue` skill. See the root
[`README.md`](https://github.com/HomericIntelligence/Athena#readme) for the full skill catalog,
dependency requirements (Git, Python 3.13, authenticated `gh` for forge routes), and capability
fallbacks.

## Uninstall

Remove `"@homericintelligence/athena-opencode"` from the `plugin` array, restart opencode, and delete
`opencode/skills/athena/` from your configuration directory if you want the files gone immediately.

## License

BSD-3-Clause. See `LICENSE` and `NOTICE`.
