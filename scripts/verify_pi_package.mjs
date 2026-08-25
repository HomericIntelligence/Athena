import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";

const [packageRootArgument, rpcOutputPath] = process.argv.slice(2);

if (!packageRootArgument || !rpcOutputPath) {
  throw new Error("Usage: node verify_pi_package.mjs PACKAGE_ROOT RPC_OUTPUT_PATH");
}

const packageRoot = resolve(packageRootArgument);
const skillsRoot = join(packageRoot, "skills");
const expectedCommands = readdirSync(skillsRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && existsSync(join(skillsRoot, entry.name, "SKILL.md")))
  .map((entry) => `skill:${entry.name}`)
  .sort();
const responses = readFileSync(rpcOutputPath, "utf8")
  .split("\n")
  .filter(Boolean)
  .map((line) => JSON.parse(line));
const commandResponse = responses.find(
  (entry) =>
    entry.type === "response" && entry.command === "get_commands" && entry.success === true,
);

if (!commandResponse || !Array.isArray(commandResponse.data?.commands)) {
  throw new Error(
    "The get_commands response did not contain a successful Pi command inventory.",
  );
}

const actualCommands = commandResponse.data.commands
  .filter(
    (command) =>
      command.source === "skill" &&
      command.sourceInfo?.origin === "package" &&
      resolve(command.sourceInfo.baseDir) === packageRoot,
  )
  .map((command) => command.name)
  .sort();

if (JSON.stringify(actualCommands) !== JSON.stringify(expectedCommands)) {
  throw new Error(
    `The Pi skill inventory does not match. The expected command list follows.\n${JSON.stringify(expectedCommands)}\nThe actual command list follows.\n${JSON.stringify(actualCommands)}`,
  );
}

for (const required of ["skill:advise", "skill:learn", "skill:pr-review"]) {
  if (!actualCommands.includes(required)) {
    throw new Error(`The Pi skill inventory does not contain the required skill '${required}'.`);
  }
}

process.stdout.write(
  `The script verified ${actualCommands.length} Pi package skills from '${packageRoot}'.\n`,
);
