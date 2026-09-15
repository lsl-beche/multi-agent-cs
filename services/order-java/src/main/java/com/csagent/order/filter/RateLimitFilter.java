package com.csagent.order.filter;

import com.csagent.order.common.ApiResponse;
import com.csagent.order.common.ErrorCode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 滑动窗口限流(ZSET 实现,Redis Lua 原子执行):
 * - 维度:接口 scope + 调用方身份(X-User-Id 优先,退回远端 IP);
 * - deduct 15 次/10s、下单 5 次/10s(可配置),超限 429 + Retry-After;
 * - Redis 故障 fail-open 放行(限流器不能成为可用性单点)。
 * 执行顺序在幂等过滤器之前:被限流的请求不消耗幂等键。
 */
@Component
@Order(1)
@RequiredArgsConstructor
public class RateLimitFilter extends OncePerRequestFilter {

    /**
     * ZSET 滑动窗口,单脚本原子执行。
     * 注意清除上界是 now - 窗口毫秒:若用 now 本身,会把当前窗口内的记录全部清掉,
     * 计数永远为 1、永不触发限流(本次实测踩中的边界 bug)。
     */
    private static final DefaultRedisScript<Long> SLIDING_WINDOW = new DefaultRedisScript<>("""
            redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, tonumber(ARGV[1]) - tonumber(ARGV[4]) * 1000)
            redis.call('ZADD', KEYS[1], tonumber(ARGV[1]), ARGV[2])
            local n = redis.call('ZCARD', KEYS[1])
            redis.call('EXPIRE', KEYS[1], tonumber(ARGV[4]))
            return n
            """, Long.class);

    private static final String KEY_HEADER = "X-User-Id";

    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;

    @Value("${app.rate-limit.enabled:true}")
    private boolean enabled;

    @Value("${app.rate-limit.deduct-limit:15}")
    private int deductLimit;

    @Value("${app.rate-limit.order-limit:5}")
    private int orderLimit;

    @Value("${app.rate-limit.window-seconds:10}")
    private int windowSeconds;

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        if (!enabled || !"POST".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String uri = request.getRequestURI();
        return !(uri.matches("/api/inventory/\\d+/deduct") || "/api/orders".equals(uri));
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String scope = "/api/orders".equals(request.getRequestURI()) ? "order" : "deduct";
        int limit = "order".equals(scope) ? orderLimit : deductLimit;
        String identity = request.getHeader(KEY_HEADER) == null
                ? request.getRemoteAddr() : request.getHeader(KEY_HEADER);

        Long count;
        try {
            long now = System.currentTimeMillis();
            count = redis.execute(SLIDING_WINDOW,
                    List.of("rl:" + scope + ":" + identity),
                    String.valueOf(now), UUID.randomUUID().toString(), "", String.valueOf(windowSeconds));
        } catch (Exception e) {
            // fail-open:限流器故障不阻塞业务(与 CSagent 限流语义一致)
            chain.doFilter(request, response);
            return;
        }

        if (count != null && count > limit) {
            response.setStatus(ErrorCode.RATE_LIMITED.httpStatus().value());
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            response.setCharacterEncoding(StandardCharsets.UTF_8.name());
            response.setHeader("Retry-After", String.valueOf(windowSeconds));
            response.getOutputStream().write(objectMapper.writeValueAsBytes(
                    com.csagent.order.common.ApiResponse.error(
                            ErrorCode.RATE_LIMITED.code(), ErrorCode.RATE_LIMITED.defaultMessage())));
            return;
        }
        chain.doFilter(request, response);
    }
}
