import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  rmSync,
  statSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Plugin } from "@opencode/plugin";

const NAMESPACE = "athena";

function bundledSkillsRoot() {
  return fileURLToPath(new URL("./skills/", import.meta.url));
}

function configBase() {
  const override = process.env.XDG_CONFIG_HOME;
  if (override !== undefined && override !== "") {
    return resolve(override);
  }
  return join(homedir(), ".config");
}

function installTarget() {
  return join(configBase(), "opencode", "skills", NAMESPACE);
}

export function syncSkills() {
  const source = bundledSkillsRoot();
  const target = installTarget();
  if (!existsSync(join(source, "_cli.py"))) {
    throw new Error(
      `The plugin cannot find the Athena skills next to plugin.js: '${source}'.`,
    );
  }
  mkdirSync(dirname(target), { recursive: true });
  rmSync(target, { recursive: true, force: true });
  cpSync(source, target, { recursive: true });
  return target;
}

export default Plugin.define({
  id: "@homericintelligence/athena-opencode",
  setup() {
    try {
      const target = syncSkills();
      console.log(
        `[athena-opencode] The plugin installed the skills at '${target}'.`,
      );
    } catch (error) {
      console.warn(
        `[athena-opencode] The plugin could not install the skills: ${error}`,
      );
    }
  },
});

export function bundledSkillNames() {
  const root = bundledSkillsRoot();
  return readdirSync(root, { withFileTypes: true })
    .filter(
      (entry) =>
        entry.isDirectory() &&
        existsSync(join(root, entry.name, "SKILL.md")) &&
        statSync(join(root, entry.name, "SKILL.md")).isFile(),
    )
    .map((entry) => entry.name)
    .sort();
}
