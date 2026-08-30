# 前端企业级重构进度

> 分支：`refactor/frontend-enterprise`  
> 状态：进行中

## 已完成

### 共享前端基础包

- `web/shared/`：
  - types：`ApiResponse`、`PaginatedData`、用户、订单、商品、地址、购物车类型；
  - auth：`TokenStorage`，默认 `sessionStorage`，可切换 `localStorage`；
  - api：`createApiClient()`，统一请求/响应、401 刷新队列、错误提示；
  - ui：`showToast()`；
  - components：`AppErrorBoundary`、`AsyncState`、`PageContainer`、`DataTable`；
  - permissions：`PermissionDirective`、`usePermission()`；
- 两个应用通过 `@shared` 引入共享代码；
- vite / vitest / tsconfig 均配置 `@shared` 和对 `vue`、`axios`、`element-plus` 的解析路径。

### Token 存储与刷新

- Shop 和 Admin 改用 `TokenStorage`；
- Admin 保留 refresh token 自动刷新；
- Shop 增加 refresh token 保存，后续可由 `createApiClient` 自动刷新；
- 路由守卫改为读取统一 `TokenStorage`，不再直接访问 `localStorage`。

### 消除 `any`

- API 层查询参数改为 `Record<string, unknown>` 或明确接口；
- API 返回类型统一使用 `ApiResponse<T>` / `PaginatedData<T>`；
- 组件中的 `as any` / `ref<any>` 已移除；
- 当前 `web/shop`、`web/admin`、`web/shared` 源码中已无 `: any`、`as any`、`<any>`。

### 组件测试

- `web/shop/src/__tests__/api.test.ts`：API 错误分类；
- `web/shop/src/__tests__/shared.test.ts`：TokenStorage、AsyncState、ErrorBoundary。

### Playwright E2E

- `web/e2e/`：
  - `playwright.config.ts`；
  - `e2e/smoke.spec.ts`；
  - CI 新增 `e2e` job；
- 当前仅首页 smoke 测试，后续扩展到登录、下单、管理端关键流程。

## 尚未完成

- `HomeView`、`ChatWidget`、`ProductDetailView` 等大页面仍未拆分到 feature components/hooks；
- `DataTable` 等共享组件尚未全面替换各业务页面；
- 管理端报表 chunk 超过 1 MB，需要进一步代码分包；
- Playwright 本地未安装/未执行；
- 可访问性、i18n、主题 tokens 未完成；
- 前端 OpenAPI 自动生成类型尚未接入。

## 验证

```bash
cd web/shop && npm run build
cd web/admin && npm run build
cd web/shop && npm test -- --run
```

当前两个应用 `vue-tsc` 和 production build 均通过。
