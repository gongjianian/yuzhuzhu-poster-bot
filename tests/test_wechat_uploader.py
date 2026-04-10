import re
from unittest.mock import MagicMock, Mock, patch

import pytest

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


@patch("wechat_uploader.get_wx_access_token", return_value="fake_token")
@patch("wechat_uploader.requests.post")
def test_register_material_calls_tcb_api(mock_post, mock_token):
    from wechat_uploader import register_material

    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"errcode": 0, "id_list": ["mat_001"]}
    )
    mat_id = register_material(
        file_id="cloud://env.abc/materials/test.jpg",
        title="积食停滞类 · 五行泡浴",
        category_id="cat_pw_jstl",
        level1_category_id="cat_piwei",
        product_type="五行泡浴",
    )
    assert mat_id == "mat_001"
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "databaseadd" in call_kwargs[0][0]


@patch("wechat_uploader.get_wx_access_token", return_value="fake_token")
@patch("wechat_uploader.requests.post")
def test_register_material_raises_on_error(mock_post, mock_token):
    from wechat_uploader import register_material

    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"errcode": -1, "errmsg": "system error"}
    )
    with pytest.raises(RuntimeError, match="register_material"):
        register_material(
            file_id="cloud://env.abc/materials/test.jpg",
            title="test",
            category_id="cat_pw_jstl",
            level1_category_id="cat_piwei",
            product_type="五行泡浴",
        )


def test_build_material_cloud_path_format():
    from wechat_uploader import build_material_cloud_path
    path = build_material_cloud_path(
        level1_category_id="cat_piwei",
        category_id="cat_pw_jstl",
        product_type="五行泡浴",
    )
    assert re.match(r"materials/cat_piwei/cat_pw_jstl/五行泡浴_\d{8}\.jpg", path)
