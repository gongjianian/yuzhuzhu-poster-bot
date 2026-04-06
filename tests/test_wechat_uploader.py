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
        "url": "https://cos.ap-shanghai.myqcloud.com/bucket",
        "token": "cos_security_token_xxx",
        "authorization": "q-sign-algorithm=sha1&q-ak=xxx",
        "file_id": "cloud://env.bucket/images/test.jpg",
        "cos_file_id": "xxx-xxx-xxx",
    }
    upload_response = Mock()
    upload_response.status_code = 204
    mock_post.side_effect = [credential_response, upload_response]

    file_id = wechat_uploader.upload_image(b"image-bytes", "images/cat/item_20260406.jpg")

    assert file_id == "cloud://env.bucket/images/test.jpg"

    first_call = mock_post.call_args_list[0]
    assert first_call.args[0] == "https://api.weixin.qq.com/tcb/uploadfile"
    assert first_call.kwargs["params"] == {"access_token": "token-123"}
    assert first_call.kwargs["json"]["path"] == "images/cat/item_20260406.jpg"

    second_call = mock_post.call_args_list[1]
    assert second_call.args[0] == "https://cos.ap-shanghai.myqcloud.com/bucket"
    assert second_call.kwargs["files"]["file"] == ("poster.jpg", b"image-bytes", "image/jpeg")
    assert second_call.kwargs["data"] == {
        "key": "images/cat/item_20260406.jpg",
        "Signature": "q-sign-algorithm=sha1&q-ak=xxx",
        "x-cos-security-token": "cos_security_token_xxx",
        "x-cos-meta-fileid": "xxx-xxx-xxx",
    }
    mock_get_token.assert_called_once()


def test_build_cloud_path() -> None:
    with patch("wechat_uploader.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "20260406"

        path = wechat_uploader.build_cloud_path("bath-bombs", "store/product")

    assert path == "images/bath-bombs/store_product_20260406.jpg"
