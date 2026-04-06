from unittest.mock import Mock, patch

import wechat_uploader


@patch("wechat_uploader.requests.get")
def test_get_wx_access_token(mock_get: Mock) -> None:
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"access_token": "token-123"}
    mock_get.return_value = response

    token = wechat_uploader.get_wx_access_token()

    assert token == "token-123"
    assert mock_get.call_args.kwargs["params"]["grant_type"] == "client_credential"


@patch("wechat_uploader.get_wx_access_token", return_value="token-123")
@patch("wechat_uploader.requests.post")
def test_upload_image(mock_post: Mock, mock_get_token: Mock) -> None:
    credential_response = Mock()
    credential_response.raise_for_status = Mock()
    credential_response.json.return_value = {
        "errcode": 0,
        "url": "https://cos.example.com/upload",
        "authorization": {"policy": "abc", "x-cos-security-token": "sec"},
        "token": "signature-token",
        "cos_file_id": "images/cat/item_20260406.jpg",
        "file_id": "cloud://file-id",
    }
    upload_response = Mock()
    upload_response.raise_for_status = Mock()
    mock_post.side_effect = [credential_response, upload_response]

    file_id = wechat_uploader.upload_image(b"image-bytes", "images/cat/item_20260406.jpg")

    assert file_id == "cloud://file-id"
    first_call = mock_post.call_args_list[0]
    assert first_call.kwargs["params"] == {"access_token": "token-123"}
    assert first_call.kwargs["json"]["path"] == "images/cat/item_20260406.jpg"

    second_call = mock_post.call_args_list[1]
    assert second_call.args[0] == "https://cos.example.com/upload"
    assert second_call.kwargs["files"]["file"][0] == "poster.jpg"
    assert second_call.kwargs["data"]["key"] == "images/cat/item_20260406.jpg"
    assert second_call.kwargs["data"]["Signature"] == "signature-token"
    mock_get_token.assert_called_once()


def test_build_cloud_path() -> None:
    with patch("wechat_uploader.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "20260406"

        path = wechat_uploader.build_cloud_path("泡澡球", "浴小主/樱花限定")

    assert path == "images/泡澡球/浴小主_樱花限定_20260406.jpg"
