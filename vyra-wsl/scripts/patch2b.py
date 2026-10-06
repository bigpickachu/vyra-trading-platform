"""Patch 2b: disciplina para news e social analysts."""
base = "/home/francfrancisco/vyra-ia/venv/lib/python3.14/site-packages/tradingagents/agents/prompts/"

regra = (
    "STRICT TOOL BUDGET (MANDATORY RULE): You may make AT MOST 3 tool calls in total. "
    "After the 3rd tool call you MUST stop and immediately write your final report "
    "with whatever data you found, even if it is limited. "
    "NEVER say you need more data or keep searching. "
    "If searches return no results, note that in your report and move on. "
)

for ficheiro in ["news_analyst.md", "social_media_analyst.md"]:
    path = base + ficheiro
    with open(path) as f:
        code = f.read()
    if "STRICT TOOL BUDGET" in code:
        print(f"{ficheiro}: ja tinha o patch, pulado.")
        continue
    # injeta a regra logo no inicio do prompt
    with open(path, "w") as f:
        f.write(regra + code)
    print(f"{ficheiro}: PATCH APLICADO!")
