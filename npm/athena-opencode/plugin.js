import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  statSync,
} from "node:fs";
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

export function loadedVersion() {
  try {
    const document = JSON.parse(
      readFileSync(new URL("./package.json", import.meta.url), "utf8"),
    );
    const version = document && document.version;
    return typeof version === "string" && version.trim() !== ""
      ? version
      : null;
  } catch {
    return null;
  }
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
  // Stage the new corpus next to the target and swap it in with renames.
  // OpenCode watches the skills directory. A full remove followed by a copy
  // leaves an empty tree that the watcher can observe mid-install.
  const stamp = `${process.pid}-${Date.now()}`;
  const staged = `${target}.staging-${stamp}`;
  const backup = `${target}.backup-${stamp}`;
  try {
    cpSync(source, staged, { recursive: true });
  } catch (error) {
    // A partially staged tree keeps the errors it hit; the live target is untouched.
    try {
      rmSync(staged, { recursive: true, force: true });
    } catch {
      // Nothing was published. The caller still holds the original error.
    }
    throw error;
  }
  let hadPrevious = false;
  try {
    renameSync(target, backup);
    hadPrevious = true;
  } catch (error) {
    if (error.code !== "ENOENT") {
      try {
        rmSync(staged, { recursive: true, force: true });
      } catch {
        // Nothing was published. The caller still holds the original error.
      }
      throw error;
    }
  }
  try {
    renameSync(staged, target);
  } catch (error) {
    if (hadPrevious) {
      renameSync(backup, target);
    }
    try {
      rmSync(staged, { recursive: true, force: true });
    } catch {
      // The live target was restored. The staged residue is harmless.
    }
    throw error;
  }
  try {
    rmSync(backup, { recursive: true, force: true });
  } catch {
    console.warn(
      `[athena-opencode] The plugin installed the skills but could not remove the backup tree: '${backup}'.`,
    );
  }
  return target;
}

export default {
  id: "@homericintelligence/athena-opencode",
  setup() {
    const version = loadedVersion();
    if (version !== null) {
      console.log(`[athena-opencode] loaded ${version}`);
    }
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
};

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
