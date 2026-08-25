import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

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
      `The plugin cannot find the Athena skills next to plugin.js: ${source}`,
    );
  }
  mkdirSync(dirname(target), { recursive: true });
  rmSync(target, { recursive: true, force: true });
  cpSync(source, target, { recursive: true });
  return target;
}

async function athenaPlugin() {
  try {
    syncSkills();
  } catch (error) {
    console.warn(
      `[athena-opencode] The plugin could not install the skills: ${error}`,
    );
  }
  return {};
}

export default athenaPlugin;

export function bundledSkillNames() {
  return readdirSync(bundledSkillsRoot(), { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
}
