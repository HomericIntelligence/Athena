export default function (pi) {
  pi.registerCommand("ci-verify-subagent-tool", {
    handler: async (_args, ctx) => {
      const tools = pi.getAllTools();
      const subagent = tools.find((tool) => tool.name === "subagent");
      const activeToolNames = pi.getActiveTools().sort();

      ctx.ui.notify(
        JSON.stringify({
          package: "pi-subagents",
          configuredToolNames: tools.map((tool) => tool.name).sort(),
          activeToolNames,
          tool: subagent && {
            name: subagent.name,
            active: activeToolNames.includes("subagent"),
            sourceInfo: subagent.sourceInfo,
          },
        }),
        subagent ? "info" : "error",
      );
    },
  });
}
