package com.csagent.order.idempotency;

import com.csagent.order.common.ApiResponse;
import com.csagent.order.common.ErrorCode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletOutputStream;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Set;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 幂等过滤器:统一接入所有受保护的写接口——
 * 带 Idempotency-Key 的 JSON POST 才走幂等逻辑,其余请求直通。
 *
 * 语义:
 * - 持有者:执行业务,2xx 存档响应(供回放),≥4xx 释放键(允许同键重试);
 * - 冲突-处理中:409 IDEMPOTENCY_PROCESSING;
 * - 冲突-已完成:原样回放首次 200 响应,附 Idempotent-Replayed: true;
 * - 同键不同参:400 IDEMPOTENCY_MISMATCH(客户端 bug,必须显式暴露)。
 */
@Component
@RequiredArgsConstructor
public class IdempotencyFilter extends OncePerRequestFilter {

    private static final Set<String> PROTECTED_PREFIXES =
            Set.of("/api/inventory/", "/api/orders/", "/api/pending-actions/");
    private static final String KEY_HEADER = "Idempotency-Key";

    private final IdempotencyService idempotencyService;
    private final ObjectMapper objectMapper;

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        if (!"POST".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String path = request.getRequestURI();
        boolean protectedPath = PROTECTED_PREFIXES.stream().anyMatch(path::startsWith);
        return !protectedPath || request.getHeader(KEY_HEADER) == null;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        RepeatableRequestWrapper wrappedRequest = new RepeatableRequestWrapper(request);
        String key = wrappedRequest.getHeader(KEY_HEADER);
        String scope = deriveScope(wrappedRequest.getRequestURI());
        String userId = wrappedRequest.getHeader("X-User-Id") == null
                ? "anon" : wrappedRequest.getHeader("X-User-Id");

        String contentType = wrappedRequest.getContentType() == null
                ? "" : wrappedRequest.getContentType().split(";")[0].trim();
        if (!"application/json".equals(contentType)) {
            chain.doFilter(wrappedRequest, response);
            return;
        }

        IdempotencyService.BeginResult result =
                idempotencyService.tryBegin(key, scope, userId, wrappedRequest.bodyAsString());
        switch (result) {
            case MISMATCH -> {
                writeError(response, ErrorCode.IDEMPOTENCY_MISMATCH);
                return;
            }
            case PROCESSING -> {
                writeError(response, ErrorCode.IDEMPOTENCY_PROCESSING);
                return;
            }
            case DONE -> {
                IdempotencyKeyEntity record = idempotencyService.getReplayable(key);
                if (record == null) {
                    writeError(response, ErrorCode.IDEMPOTENCY_PROCESSING);
                    return;
                }
                replay(response, record);
                return;
            }
            default -> { /* OWNER:放行执行 */ }
        }

        ContentCaching cached = new ContentCaching(response);
        try {
            chain.doFilter(wrappedRequest, cached);
            if (cached.getStatus() < 400) {
                idempotencyService.complete(key, cached.bodyAsString());
            } else {
                idempotencyService.release(key);   // 失败释放,同键可重试
            }
            cached.copyBodyToResponse();
        } catch (Exception ex) {
            idempotencyService.release(key);
            throw ex;
        }
    }

    /** 过滤器层无 @RestControllerAdvice,业务异常需就地转为统一错误响应。 */
    private void writeError(HttpServletResponse response, ErrorCode errorCode) throws IOException {
        response.setStatus(errorCode.httpStatus().value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.getOutputStream().write(objectMapper.writeValueAsBytes(
                ApiResponse.error(errorCode.code(), errorCode.defaultMessage())));
    }

    private void replay(HttpServletResponse response, IdempotencyKeyEntity record) throws IOException {
        response.setStatus(HttpServletResponse.SC_OK);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setHeader("Idempotent-Replayed", "true");
        response.getOutputStream().write(
                record.getResponseBody() == null ? "{}".getBytes(StandardCharsets.UTF_8)
                        : record.getResponseBody().getBytes(StandardCharsets.UTF_8));
    }

    private String deriveScope(String uri) {
        String[] parts = uri.split("/");
        return parts.length >= 3 ? parts[1] + "/" + parts[2] : uri;
    }

    /** 最小响应缓存包装:仅为幂等存档捕获业务响应体。 */
    static class ContentCaching extends jakarta.servlet.http.HttpServletResponseWrapper {
        private final HttpServletResponse target;
        private final ByteArrayOutputStream out = new ByteArrayOutputStream();
        private final ServletOutputStream sink = new ServletOutputStream() {
            @Override
            public void write(int b) {
                out.write(b);
            }

            @Override
            public boolean isReady() {
                return true;
            }

            @Override
            public void setWriteListener(jakarta.servlet.WriteListener listener) {
                throw new UnsupportedOperationException();
            }
        };

        ContentCaching(HttpServletResponse response) {
            super(response);
            this.target = response;
        }

        @Override
        public ServletOutputStream getOutputStream() {
            return sink;
        }

        byte[] body() {
            return out.toByteArray();
        }

        String bodyAsString() {
            return new String(body(), StandardCharsets.UTF_8);
        }

        void copyBodyToResponse() throws IOException {
            target.getOutputStream().write(body());
        }
    }
}
