# athena-opencode

[Athena](https://github.com/HomericIntelligence/Athena) packages its workflow skills as an
[opencode](https://opencode.ai) plugin. The plugin contains the full canonical skill corpus. It puts
the corpus in the opencode configuration directory. Opencode finds and loads the corpus there.

Athena uses the
[ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md)
for its English technical prose.

## Install

Add the package to the `plugins` array in the opencode configuration. Use one of these configuration
files:

- `~/.config/opencode/opencode.json`; or
- a project `opencode.json`.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugins": ["@homericintelligence/athena-opencode"]
}
```

Quit opencode. Then, restart opencode. During startup, the plugin copies the bundled `skills/` corpus
to this location:

```text
XDG_CONFIG_HOME/opencode/skills/athena/
```

If `XDG_CONFIG_HOME` does not have a value, the target is
`~/.config/opencode/skills/athena/`. The plugin writes only in the `athena/` namespace. It does not
change other skills in your configuration. At each restart, the plugin makes the namespace agree
with the installed plugin version. Thus, a package update also updates the skills.

## Update

OpenCode installs this package into its cache one time. At each start, it loads that cached copy.
OpenCode checks unpinned npm plugins for updates, but it does not replace the installed package.
A restart alone is not an upgrade.

The minimum loadable version is `0.6.0`. The published `0.4.4`, `0.5.0`, `0.5.1`, `0.5.2`, and
`0.5.3` artifacts cannot load on OpenCode 2.

To upgrade a cached install:

1. Remove `"@homericintelligence/athena-opencode"` from the `plugins` array in your opencode
   configuration, or delete the cached install:

   ```bash
   rm -rf ~/.cache/opencode/npm/@homericintelligence/athena-opencode@latest
   ```

2. Add `"@homericintelligence/athena-opencode"` to the `plugins` array again.
3. Restart opencode. It installs the missing package in the background.
4. Check the result:

   - `opencode plugin list` shows the installed version;
   - `opencode plugin check @homericintelligence/athena-opencode` shows update availability;
   - `opencode plugin update @homericintelligence/athena-opencode` upgrades a configured plugin;
   - or run the on-demand version check from the corpus:

     ```bash
     python3 ~/.config/opencode/skills/athena/_cli.py check-update
     ```

   Quit and restart opencode after an upgrade so the server loads the new package.

If you install through the CLI, `opencode plugin add @homericintelligence/athena-opencode` writes
the unpinned entry to `opencode.json` and installs the current version at the next start. It
records no pinned version, so the entry stays unpinned and is treated like the hand-edited form.

## Troubleshooting

### The server log shows a plugin load failure

Server log entries like this one mean the cached package is too old:

```text
failed to load plugin @homericintelligence/athena-opencode
cause="Cause([Fail(PluginModule.LoadError: Plugin must export a default definition
with an id and an effect or setup function. ...)])"
```

The `0.4.x` and `0.5.x` artifacts predate the object plugin definition that OpenCode 2 requires.
They are deprecated on npm. Remove the cached install and add the plugin again (see
[Update](#update)). Then verify that the installed version is `0.6.0` or newer.

## Use

Use the native opencode skill mechanism. For example, ask opencode to use the `repo-review`,
`pr-review`, or `plan-issue` skill. See the root
[`README.md`](https://github.com/HomericIntelligence/Athena#readme) for this information:

- the full skill catalog;
- dependency requirements for Git and Python 3.12.3 or newer;
- the authenticated GitHub CLI (`gh`) requirement for forge routes; and
- capability fallbacks.

## Uninstall

1. Remove `"@homericintelligence/athena-opencode"` from the `plugins` array.
2. Restart opencode.
3. To remove the files immediately, delete `opencode/skills/athena/` from your configuration
   directory.

## License

BSD-3-Clause. See `LICENSE` and `NOTICE`.
