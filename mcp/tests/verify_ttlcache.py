#!/usr/bin/env python3
"""Verify TTLCache behavior - does it refresh on access?"""

import time
from cachetools import TTLCache

print("=" * 70)
print("验证 TTLCache 行为测试")
print("=" * 70)

print("\n【测试】TTLCache 访问时是否刷新过期时间？")
cache = TTLCache(maxsize=100, ttl=10)

# Add item
cache["test"] = "value"
print(f"✓ 添加项目 'test'，TTL=10秒")
print(f"  当前时间: 0秒")

# Wait 6 seconds and access
time.sleep(6)
print(f"\n✓ 6秒后访问项目...")
value = cache.get("test")
print(f"  访问结果: {value}")
print(f"  是否存在: {'test' in cache}")

# Wait another 6 seconds (total 12 seconds)
time.sleep(6)
print(f"\n✓ 再等 6秒（总共12秒）...")
print(f"  是否存在: {'test' in cache}")
print(f"  预期: 如果访问刷新TTL，应该存在；否则不存在")

if "test" in cache:
    print("\n结论: ❌ TTLCache 在访问时会刷新过期时间")
else:
    print("\n结论: ✅ TTLCache 在访问时**不会**刷新过期时间")
    print("       TTL 是从最初插入时刻开始计算的（固定过期时间）")

print("\n" + "=" * 70)
print("TTLCache 特性说明")
print("=" * 70)
print("• TTL (Time To Live): 从插入时刻开始计算")
print("• 访问（get/[key]）不会重置过期时间")
print("• 只有重新赋值才会重置过期时间")
print("• 适用场景: 固定时间后必须过期的缓存")
print("\n如果需要 '访问时刷新' 的行为，需要:")
print("  1. 使用其他库（如 expiringdict）")
print("  2. 自己实现（重新赋值来刷新）")
print("  3. 使用原来的自定义实现")
