"""Data analyst on the Agent Framework harness, with file access and tool approvals.

Python port of the official ``harness_data_processing.py`` sample:
https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness

Reading files is auto-approved (``FileAccessProvider.read_only_tools_auto_approval_rule``); writing, replacing
or deleting asks the user, which mafx relays (interactive prompt, or --yes / --allow-tool with -p).

The agent works on a copy of ``projects/harness-lab/data`` under ``.mafx/work/harness-lab/analyst`` so its
writes never modify the repository.
"""

import shutil
from pathlib import Path

from agent_framework import FileAccessProvider, FileSystemAgentFileStore, create_harness_agent

DATA_ANALYST_INSTRUCTIONS = """\
You are a data analyst assistant. You have access to a folder of data files via the file_access_* tools.

## Getting started
- Start by listing available files with file_access_ls to see what data is available.
- Read the files to understand their structure and contents.

## Working with data
- When asked to analyze data, read the relevant files first, then perform the analysis.
- Show your analysis clearly with tables, summaries, and key insights.
- When calculations are needed, work through them step by step and show your reasoning.

## Writing output
- When asked to produce output files (e.g., reports, summaries, filtered data), use file_access_write to write them.
- Use appropriate file formats: CSV for tabular data, Markdown for reports.
- Confirm what you wrote and where.

## Important
- Never modify or delete the original input data files unless explicitly asked to do so.
- If asked about data you haven't read yet, read it first before answering.
- Always explain your reasoning and thought process as you work through tasks.
"""

MAX_CONTEXT_WINDOW_TOKENS = 262_144
MAX_OUTPUT_TOKENS = 16_384


def _working_dir(context) -> Path:
    workspace = context.workspace_root or context.project.root
    work = workspace / ".mafx" / "work" / context.project.name / "analyst"
    seed = context.project.root / "data"
    work.mkdir(parents=True, exist_ok=True)
    for source in seed.glob("*"):
        target = work / source.name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)
    return work


def create_agent(client, context):
    return create_harness_agent(
        client=client,
        name="analyst",
        description="A data analyst assistant that reads, analyzes, and processes data files.",
        agent_instructions=DATA_ANALYST_INSTRUCTIONS,
        max_context_window_tokens=MAX_CONTEXT_WINDOW_TOKENS,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        file_access_store=FileSystemAgentFileStore(_working_dir(context)),
        auto_approval_rules=[FileAccessProvider.read_only_tools_auto_approval_rule],
        disable_todo=True,
        disable_mode=True,
        disable_web_search=True,
    )
