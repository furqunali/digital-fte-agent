import pytest

from digital_fte.resume_token import (
    InvalidResumeToken,
    ResumeToken,
    decode_token,
    encode_token,
)


def test_round_trip_offset_only():
    token = encode_token(42)
    decoded = decode_token(token)
    assert isinstance(decoded, ResumeToken)
    assert decoded.offset == 42
    assert decoded.state == {}


def test_round_trip_with_state():
    state = {"cursor": "abc", "page": 3, "flags": [1, 2, 3]}
    token = encode_token(7, state)
    decoded = decode_token(token)
    assert decoded.offset == 7
    assert decoded.state == state


def test_token_is_urlsafe_string():
    token = encode_token(1, {"k": "v"})
    assert isinstance(token, str)
    # URL-safe base64 uses only these characters.
    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_="
    )
    assert set(token) <= allowed


def test_encoding_is_deterministic():
    a = encode_token(5, {"b": 2, "a": 1})
    b = encode_token(5, {"a": 1, "b": 2})
    assert a == b


def test_zero_offset_allowed():
    assert decode_token(encode_token(0)).offset == 0


def test_negative_offset_rejected():
    with pytest.raises(ValueError):
        encode_token(-1)


@pytest.mark.parametrize("bad", [True, 1.5, "3"])
def test_bad_offset_type_rejected(bad):
    with pytest.raises(TypeError):
        encode_token(bad)


def test_non_dict_state_rejected():
    with pytest.raises(TypeError):
        encode_token(1, ["not", "a", "dict"])  # type: ignore[arg-type]


def test_unserialisable_state_rejected():
    with pytest.raises(ValueError):
        encode_token(1, {"bad": object()})


def test_decode_rejects_garbage():
    with pytest.raises(InvalidResumeToken):
        decode_token("!!!not base64!!!")


def test_decode_rejects_non_json_payload():
    import base64

    token = base64.urlsafe_b64encode(b"not json").decode("ascii")
    with pytest.raises(InvalidResumeToken):
        decode_token(token)


def test_decode_rejects_empty():
    with pytest.raises(InvalidResumeToken):
        decode_token("")


def test_decode_rejects_wrong_version():
    import base64
    import json

    raw = json.dumps({"v": 99, "offset": 1, "state": {}}).encode()
    token = base64.urlsafe_b64encode(raw).decode("ascii")
    with pytest.raises(InvalidResumeToken):
        decode_token(token)


def test_decode_rejects_bad_offset():
    import base64
    import json

    raw = json.dumps({"v": 1, "offset": -3, "state": {}}).encode()
    token = base64.urlsafe_b64encode(raw).decode("ascii")
    with pytest.raises(InvalidResumeToken):
        decode_token(token)


def test_decode_tolerates_stripped_padding():
    token = encode_token(123, {"x": 1}).rstrip("=")
    decoded = decode_token(token)
    assert decoded.offset == 123
