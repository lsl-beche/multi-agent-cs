package com.csagent.order.idempotency;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.LocalDateTime;
import lombok.Data;

/** 幂等键记录(对应 idempotency_keys 表)。 */
@Data
@TableName("idempotency_keys")
public class IdempotencyKeyEntity {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String idemKey;

    private String scope;

    private String userId;

    private String requestHash;

    private String responseBody;

    /** PROCESSING / DONE */
    private String status;

    private LocalDateTime createdAt;

    private LocalDateTime expiresAt;
}
