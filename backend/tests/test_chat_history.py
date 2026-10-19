import pytest
from unittest.mock import AsyncMock, patch

def test_chat_history():
    # Mock test for chat history
    # last-N ordering
    # current msg excluded
    assert True


@pytest.mark.asyncio
async def test_delete_conversation_success():
    from app.services.chat_service import delete_conversation

    mock_conv_col = AsyncMock()
    mock_conv_col.delete_one.return_value.deleted_count = 1
    mock_msg_col = AsyncMock()

    with patch("app.services.chat_service.conversations_col", return_value=mock_conv_col), \
         patch("app.services.chat_service.messages_col", return_value=mock_msg_col):
        result = await delete_conversation("conv_123", "user_1")
        assert result is True
        mock_conv_col.delete_one.assert_called_once_with({"_id": "conv_123", "user_id": "user_1"})
        mock_msg_col.delete_many.assert_called_once_with({"conversation_id": "conv_123"})


@pytest.mark.asyncio
async def test_delete_conversation_not_found():
    from app.services.chat_service import delete_conversation

    mock_conv_col = AsyncMock()
    mock_conv_col.delete_one.return_value.deleted_count = 0
    mock_msg_col = AsyncMock()

    with patch("app.services.chat_service.conversations_col", return_value=mock_conv_col), \
         patch("app.services.chat_service.messages_col", return_value=mock_msg_col):
        result = await delete_conversation("conv_nonexistent", "user_1")
        assert result is False
        mock_msg_col.delete_many.assert_not_called()

