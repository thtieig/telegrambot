import pytest


class FakeMessage:
    """Stand-in for a telegram Message; records replies instead of sending."""
    def __init__(self):
        self.replies = []

    async def reply_text(self, text):
        self.replies.append(text)


@pytest.fixture
def fake_message():
    return FakeMessage()
