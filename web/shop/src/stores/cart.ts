/**
 * 购物车状态管理 Store（Pinia）
 *
 * 文件作用：集中管理购物车的全局状态（条目列表、加载状态），
 *      并提供基于"选中项"的合计数量、合计金额等派生计算，
 *      以及获取购物车、增删改、全选/单选等业务动作。
 * 所属模块：前端 shop 商城项目的全局状态层（src/stores）。
 * 对外导出内容：
 *  - useCartStore：购物车 Store 的工厂函数（组件中调用后获得 store 实例），
 *    实例对外暴露：
 *      - 状态：items（购物车条目列表）、loading（加载中标记）
 *      - 计算属性：totalCount（选中数量合计）、totalAmount（选中金额合计）、
 *        selectedItems（选中的条目列表）
 *      - 方法：fetchCart、addItem、updateItem、removeItem、
 *        toggleSelectAll、toggleSelectItem
 *
 * 说明：所有变更动作均先调用 src/api/cart.ts 的接口同步后端，
 *      再更新本地状态，保证前后端数据一致。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCart, addToCart, updateCartItem, removeCartItem, selectAll as apiSelectAll, selectItem, type CartItem } from '@/api/cart'

// 定义并导出购物车 Store（采用 setup 风格的定义方式）
export const useCartStore = defineStore('shop-cart', () => {
  // 购物车条目列表（初始为空，进入页面后由 fetchCart 填充）
  const items = ref<CartItem[]>([])
  // 购物车数据加载中标记，用于页面展示 loading 状态
  const loading = ref(false)

  // 选中条目的商品总件数：过滤出选中项后累加 quantity
  const totalCount = computed(() =>
    items.value.filter((i) => i.selected).reduce((sum, i) => sum + i.quantity, 0),
  )

  // 选中条目的合计金额：过滤出选中项后按"单价 × 数量"累加
  const totalAmount = computed(() =>
    items.value.filter((i) => i.selected).reduce((sum, i) => sum + i.price * i.quantity, 0),
  )

  // 当前被选中的购物车条目列表（用于结算页读取待下单商品）
  const selectedItems = computed(() => items.value.filter((i) => i.selected))

  /**
   * 获取购物车列表
   *
   * 作用：从后端拉取当前用户的购物车条目并更新本地 items；
   *      请求失败时清空本地列表，无论成败都会复位 loading。
   * 参数：无
   * 返回值：无（Promise<void>）
   * 依赖接口：GET /cart（经 src/api/cart.ts 的 getCart 封装）
   */
  async function fetchCart() {
    // 开始请求，置加载标记为 true（触发页面 loading 效果）
    loading.value = true
    try {
      // 调用后端接口获取购物车数据
      const res = await getCart()
      // 兼容后端返回结构，将条目列表写入本地状态（缺省为空数组）
      items.value = res.data.data?.items || []
    } catch {
      // 请求失败时清空购物车列表，避免展示脏数据
      items.value = []
    } finally {
      // 无论成功失败，最终都要复位加载标记
      loading.value = false
    }
  }

  /**
   * 添加商品到购物车
   *
   * 作用：调用接口将指定 SKU 以指定数量加入购物车，
   *      成功后重新拉取购物车列表以同步最新数据。
   * 参数：
   *  - skuId: number 要加入购物车的 SKU id
   *  - quantity: number 加入数量
   * 返回值：无（Promise<void>）
   * 依赖接口：POST /cart（经 src/api/cart.ts 的 addToCart 封装）
   */
  async function addItem(skuId: number, quantity: number) {
    // 先调用后端接口完成"加入购物车"操作
    await addToCart({ sku_id: skuId, quantity })
    // 重新拉取购物车，保证本地列表与后端一致
    await fetchCart()
  }

  /**
   * 更新购物车条目数量
   *
   * 作用：将某一条目的数量修改同步到后端，成功后直接更新本地对应条目，
   *      避免整表刷新。
   * 参数：
   *  - id: number 购物车条目 id
   *  - quantity: number 更新后的目标数量
   * 返回值：无（Promise<void>）
   * 依赖接口：PUT /cart/{id}（经 src/api/cart.ts 的 updateCartItem 封装）
   */
  async function updateItem(id: number, quantity: number) {
    // 先调用后端接口更新数量
    await updateCartItem(id, quantity)
    // 在本地列表中查找对应条目
    const item = items.value.find((i) => i.id === id)
    // 若条目存在则就地更新数量，实现界面即时刷新
    if (item) item.quantity = quantity
  }

  /**
   * 删除购物车条目
   *
   * 作用：将指定条目从购物车删除（同步后端），成功后从本地列表移除。
   * 参数：
   *  - id: number 要删除的购物车条目 id
   * 返回值：无（Promise<void>）
   * 依赖接口：DELETE /cart/{id}（经 src/api/cart.ts 的 removeCartItem 封装）
   */
  async function removeItem(id: number) {
    // 先调用后端接口删除该条目
    await removeCartItem(id)
    // 从本地列表中过滤掉已删除的条目，刷新界面
    items.value = items.value.filter((i) => i.id !== id)
  }

  /**
   * 全选 / 取消全选
   *
   * 作用：将购物车全部条目的选中状态统一置为指定值（同步后端），
   *      成功后同步更新本地所有条目的 selected 标记。
   * 参数：
   *  - selected: boolean true 表示全选，false 表示取消全选
   * 返回值：无（Promise<void>）
   * 依赖接口：PUT /cart/select-all（经 src/api/cart.ts 的 selectAll 封装）
   */
  async function toggleSelectAll(selected: boolean) {
    // 先调用后端接口设置全选状态
    await apiSelectAll(selected)
    // 遍历本地列表，将每个条目的选中状态统一更新
    items.value.forEach((i) => (i.selected = selected))
  }

  /**
   * 选中 / 取消选中某一条目
   *
   * 作用：单独设置购物车中某一条目的选中状态（同步后端），
   *      成功后更新本地对应条目的 selected 标记。
   * 参数：
   *  - id: number 购物车条目 id
   *  - selected: boolean true 表示选中，false 表示取消选中
   * 返回值：无（Promise<void>）
   * 依赖接口：PUT /cart/{id}/select（经 src/api/cart.ts 的 selectItem 封装）
   */
  async function toggleSelectItem(id: number, selected: boolean) {
    // 先调用后端接口设置该条目的选中状态
    await selectItem(id, selected)
    // 在本地列表中查找对应条目
    const item = items.value.find((i) => i.id === id)
    // 若条目存在则就地更新选中标记
    if (item) item.selected = selected
  }

  // 对外暴露状态、计算属性与动作，供组件通过 store 实例调用
  return {
    items,
    loading,
    totalCount,
    totalAmount,
    selectedItems,
    fetchCart,
    addItem,
    updateItem,
    removeItem,
    toggleSelectAll,
    toggleSelectItem,
  }
})
