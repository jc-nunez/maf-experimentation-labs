from mail_agent.tools.mail_digest import mail_digest


async def test_mail_digest():
    result = await mail_digest.invoke(arguments={"value": "x"}, skip_parsing=True)
    assert result == {"echo": "x"}
