import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";

const [installRootArgument] = process.argv.slice(2);

if (!installRootArgument) {
  throw new Error("Usage: node find_pi_package_root.mjs PI_INSTALL_ROOT");
}

const installRoot = resolve(installRootArgument);
const ignoredDirectories = new Set([".git", "node_modules"]);
const candidates = [];

function visit(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true }).sort((left, right) =>
    left.name.localeCompare(right.name),
  )) {
    const entryPath = join(directory, entry.name);
    if (entry.isDirectory()) {
      if (!ignoredDirectories.has(entry.name)) {
        visit(entryPath);
      }
      continue;
    }

    if (entry.name !== "package.json") {
      continue;
    }

    const packageRoot = directory;
    const manifest = JSON.parse(readFileSync(entryPath, "utf8"));
    const skills = manifest.pi?.skills;
    if (
      Array.isArray(skills) &&
      skills.includes("./skills") &&
      existsSync(join(packageRoot, "skills"))
    ) {
      candidates.push(packageRoot);
    }
  }
}

visit(installRoot);

if (candidates.length !== 1) {
  throw new Error(
    `The scan expected one Pi package root below '${installRoot}'. The scan found these roots in a JSON array.\n${JSON.stringify(candidates)}`,
  );
}

process.stdout.write(`${candidates[0]}\n`);
