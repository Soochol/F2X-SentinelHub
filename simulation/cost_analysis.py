"""MLX90614 vs MLX90640 가성비 분석"""
import numpy as np

# 배터리 사양
battery_w = 1700  # mm
battery_h = 2800  # mm
battery_area = battery_w * battery_h
target_coverage = 0.70

# MLX90614 90도 FOV, WD=350mm
wd = 350
fov = 90
fov_diameter = 2 * wd * np.tan(np.radians(fov/2))
fov_radius = fov_diameter / 2
fov_area = np.pi * fov_radius**2

print("=== MLX90614 90도 FOV 가성비 분석 ===")
print(f"배터리: {battery_w} x {battery_h} mm = {battery_area/1e6:.2f} m2")
print(f"FOV 지름: {fov_diameter:.0f} mm (반경 {fov_radius:.0f} mm)")
print(f"목표 커버리지: {target_coverage*100:.0f}%")
print()

# 그리드 계산 (정사각형 패킹, 10% 오버랩)
grid_spacing = fov_diameter * 0.9
cols = int(np.ceil(battery_w / grid_spacing))
rows = int(np.ceil(battery_h / grid_spacing))
total_grid = cols * rows

print("=== 그리드 배치 (10% 오버랩) ===")
print(f"간격: {grid_spacing:.0f} mm")
print(f"X축: {cols}개, Y축: {rows}개")
print(f"총 센서 수: {total_grid}개")
print()

# 이론적 최소
min_sensors = int(np.ceil(battery_area * target_coverage / fov_area))
print(f"이론적 최소 (70%): {min_sensors}개")
print()

# 가격 비교
mlx90614_price = 5.0   # USD
mlx90640_price = 35.0  # USD

print("=== 단가 ===")
print(f"MLX90614: ~${mlx90614_price:.0f}")
print(f"MLX90640: ~${mlx90640_price:.0f}")
print()

# 총 비용
mlx90614_count = total_grid
mlx90614_total = mlx90614_count * mlx90614_price

mlx90640_count = 4  # 4대로 70%+ 커버리지
mlx90640_total = mlx90640_count * mlx90640_price

print("=== 70% 커버리지 총 비용 ===")
print(f"MLX90614 ({mlx90614_count}개): ${mlx90614_total:.0f}")
print(f"MLX90640 ({mlx90640_count}개): ${mlx90640_total:.0f}")
print()

print("=== 결론 ===")
if mlx90614_total < mlx90640_total:
    print(f"MLX90614가 ${mlx90640_total - mlx90614_total:.0f} 저렴")
else:
    print(f"MLX90640이 ${mlx90614_total - mlx90640_total:.0f} 저렴")
print()
print("MLX90614 단점:")
print("  - 점 온도만 측정 (화재 위치 특정 불가)")
print("  - 센서 수 많음 -> 배선 복잡")
print("  - I2C 주소 충돌 (멀티플렉서 필요)")
print()
print("MLX90640 장점:")
print("  - 32x24 열화상 이미지")
print("  - 화재 위치 정확히 특정 가능")
print("  - 센서 수 적음 -> 배선 간단")
