"""Two-agent workflow: a writer drafts, a reviewer critiques and returns the improved version."""

from agent_framework import Agent, WorkflowBuilder


def create_workflow(client):
    writer = Agent(
        client,
        "You write a short, clear first draft for the user's request. Output only the draft.",
        name="writer",
    )
    reviewer = Agent(
        client,
        "You review the draft you receive. List up to three concrete improvements, then give the revised text.",
        name="reviewer",
    )
    return (
        # output_from: whose responses are the workflow result.
        # intermediate_output_from: stream everyone else's reasoning/tool calls too, so mafx can show them.
        WorkflowBuilder(
            name="draft-review",
            start_executor=writer,
            output_from=[reviewer],
            intermediate_output_from="all_other",
        )
        .add_edge(writer, reviewer)
        .build()
    )
