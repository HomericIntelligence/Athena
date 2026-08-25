# athena-opencode

[Athena](https://github.com/HomericIntelligence/Athena) packages its workflow skills as an
[opencode](https://opencode.ai) plugin. The plugin contains the full canonical skill corpus. It puts
the corpus in the opencode configuration directory. Opencode finds and loads the corpus there.

Athena uses the
[ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md)
for its English technical prose.

## Install

Add the package to the `plugin` array in the opencode configuration. Use one of these configuration
files:

- `~/.config/opencode/opencode.json`; or
- a project `opencode.json`.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["@homericintelligence/athena-opencode"]
}
```

Quit opencode. Then, restart opencode. During startup, the plugin copies the bundled `skills/` corpus
to this location:

```
$XDG_CONFIG_HOME/opencode/skills/athena/
```

If `XDG_CONFIG_HOME` does not have a value, the target is
`~/.config/opencode/skills/athena/`. The plugin writes only in the `athena/` namespace. It does not
change other skills in your configuration. At each restart, the plugin makes the namespace agree
with the installed plugin version. Thus, a package update also updates the skills.

## Use

Use the native opencode skill mechanism. For example, ask opencode to use the `repo-review`,
`pr-review`, or `plan-issue` skill. See the root
[`README.md`](https://github.com/HomericIntelligence/Athena#readme) for this information:

- the full skill catalog;
- dependency requirements for Git and Python 3.13;
- the authenticated GitHub CLI (`gh`) requirement for forge routes; and
- capability fallbacks.

## Uninstall

1. Remove `"@homericintelligence/athena-opencode"` from the `plugin` array.
2. Restart opencode.
3. To remove the files immediately, delete `opencode/skills/athena/` from your configuration
   directory.

## License

BSD-3-Clause. See `LICENSE` and `NOTICE`.
