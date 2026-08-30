from app.api.response import BusinessError, NotFoundError, ok


def test_ok_uses_unified_shape():
    assert ok({"id": 1}) == {"code": 0, "data": {"id": 1}, "message": "ok"}


def test_business_error_maps_status():
    err = NotFoundError("订单不存在")
    assert err.status_code == 404
    assert err.code == 404
    assert err.message == "订单不存在"


def test_business_error_can_carry_data():
    err = BusinessError("失败", code=400, data={"trace": "x"})
    assert err.data == {"trace": "x"}
