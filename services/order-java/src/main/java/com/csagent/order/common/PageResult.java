package com.csagent.order.common;

import java.util.List;

/**
 * 分页结果:不向外层接口暴露 ORM 的 Page 对象,字段即契约。
 */
public record PageResult<T>(long total, long page, int size, List<T> records) {
}
