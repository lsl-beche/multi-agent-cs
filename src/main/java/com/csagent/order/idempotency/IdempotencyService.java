package com.csagent.order.idempotency;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDateTime;
import java.util.HexFormat;
import java.util.Objects;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

/**
 * 幂等服务:tryBegin 抢占;冲突时校验哈希(防同键不同参)并回收过期 PROCESSING。
 * PROCESSING 过期(持有者崩溃)→ 删除后重新抢占,新请求接管执行。
 * 返回状态枚举而非抛异常:过滤器层无 @RestControllerAdvice,异常需就地转为响应。
 */
@Service
@RequiredArgsConstructor
public class IdempotencyService {

    public enum BeginResult { OWNER, PROCESSING, DONE, MISMATCH }

    private final IdempotencyKeyMapper mapper;

    public BeginResult tryBegin(String key, String scope, String userId, String body) {
        String hash = sha256(body);
        if (mapper.tryBegin(key, scope, userId, hash) > 0) {
            return BeginResult.OWNER;
        }
        IdempotencyKeyEntity existing = getByKey(key);
        if (existing == null) {
            // 竞态兜底:刚被持有者失败释放等极端时序,重试一次抢占
            return mapper.tryBegin(key, scope, userId, hash) > 0 ? BeginResult.OWNER : BeginResult.PROCESSING;
        }
        if (!Objects.equals(existing.getRequestHash(), hash)) {
            return BeginResult.MISMATCH;
        }
        if ("PROCESSING".equals(existing.getStatus())
                && existing.getExpiresAt() != null
                && existing.getExpiresAt().isBefore(LocalDateTime.now())) {
            // 持有者疑似崩溃:过期 PROCESSING 回收接管
            mapper.release(key);
            return mapper.tryBegin(key, scope, userId, hash) > 0 ? BeginResult.OWNER : BeginResult.PROCESSING;
        }
        return "PROCESSING".equals(existing.getStatus()) ? BeginResult.PROCESSING : BeginResult.DONE;
    }

    /** DONE 时返回存档记录供回放;PROCESSING 返回 null(调用方按处理中拒绝)。 */
    public IdempotencyKeyEntity getReplayable(String key) {
        IdempotencyKeyEntity entity = getByKey(key);
        return entity == null || "PROCESSING".equals(entity.getStatus()) ? null : entity;
    }

    public void complete(String key, String responseJson) {
        mapper.complete(key, responseJson);
    }

    public void release(String key) {
        mapper.release(key);
    }

    private IdempotencyKeyEntity getByKey(String key) {
        return mapper.selectOne(new LambdaQueryWrapper<IdempotencyKeyEntity>()
                .eq(IdempotencyKeyEntity::getIdemKey, key));
    }

    static String sha256(String input) {
        try {
            return HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(input.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
