package com.csagent.order.idempotency;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.csagent.order.idempotency.IdempotencyKeyEntity;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface IdempotencyKeyMapper extends BaseMapper<IdempotencyKeyEntity> {

    /** 抢占:唯一约束兜底,INSERT IGNORE 冲突返回 0(非本线程为持有者)。 */
    @Insert("INSERT IGNORE INTO idempotency_keys "
            + "(idem_key, scope, user_id, request_hash, response_body, status, created_at, expires_at) "
            + "VALUES (#{key}, #{scope}, #{userId}, #{hash}, NULL, 'PROCESSING', NOW(), NOW() + INTERVAL 24 HOUR)")
    int tryBegin(@Param("key") String key, @Param("scope") String scope,
                 @Param("userId") String userId, @Param("hash") String hash);

    /** 首次执行成功后回放存档。 */
    @Update("UPDATE idempotency_keys SET response_body = #{body}, status = 'DONE' "
            + "WHERE idem_key = #{key} AND status = 'PROCESSING'")
    int complete(@Param("key") String key, @Param("body") String body);

    /** 执行失败释放键:允许客户端用同一个键安全重试。 */
    @Delete("DELETE FROM idempotency_keys WHERE idem_key = #{key} AND status = 'PROCESSING'")
    int release(@Param("key") String key);
}
