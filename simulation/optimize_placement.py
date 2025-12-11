"""
카메라 2대 최적 배치 탐색
조건: 배터리 평면 전체에서 픽셀 해상도 200mm/px 이하
"""

import json
import numpy as np
from camera import Camera, CameraSpec, calculate_resolution_map, calculate_coverage_map

# 배터리 및 카메라 사양
BATTERY_WIDTH = 1700  # mm
BATTERY_HEIGHT = 2800  # mm
WORKING_DISTANCE = 350  # mm
MAX_RESOLUTION = 200  # mm/px (이하여야 함)
MIN_COVERAGE = 70  # % (이상이어야 함)

# MLX90640: 32x24 픽셀, 110° x 75° 화각
camera_spec = CameraSpec(resolution_x=32, resolution_y=24, fov_h=110, fov_v=75)


def evaluate_placement(cameras: list) -> dict:
    """배치 평가: 커버리지와 해상도 계산"""
    _, _, res_map = calculate_resolution_map(
        cameras, BATTERY_WIDTH, BATTERY_HEIGHT, grid_resolution=50
    )
    _, _, coverage = calculate_coverage_map(
        cameras, BATTERY_WIDTH, BATTERY_HEIGHT, grid_resolution=50
    )

    valid_res = res_map[~np.isnan(res_map)]
    total_cells = coverage.size
    covered_cells = np.sum(coverage > 0)

    if len(valid_res) == 0:
        return {
            'valid': False,
            'coverage_pct': 0,
            'max_resolution': float('inf'),
            'avg_resolution': float('inf'),
            'min_resolution': float('inf'),
        }

    coverage_pct = 100 * covered_cells / total_cells
    max_res = np.max(valid_res)
    avg_res = np.mean(valid_res)
    min_res = np.min(valid_res)

    valid = (coverage_pct >= MIN_COVERAGE) and (max_res <= MAX_RESOLUTION)

    return {
        'valid': valid,
        'coverage_pct': coverage_pct,
        'max_resolution': max_res,
        'avg_resolution': avg_res,
        'min_resolution': min_res,
    }


def test_config(cam1_params, cam2_params, strategy_name):
    """단일 배치 테스트"""
    cam1 = Camera(id=1, z=WORKING_DISTANCE, spec=camera_spec, **cam1_params)
    cam2 = Camera(id=2, z=WORKING_DISTANCE, spec=camera_spec, **cam2_params)
    result = evaluate_placement([cam1, cam2])
    return {
        'strategy': strategy_name,
        'cam1': cam1_params,
        'cam2': cam2_params,
        **result
    }


def search_optimal_placement():
    """그리드 탐색으로 최적 배치 찾기"""
    all_configs = []

    print("=== 카메라 2대 최적 배치 탐색 ===")
    print(f"배터리: {BATTERY_WIDTH} x {BATTERY_HEIGHT} mm")
    print(f"Working Distance: {WORKING_DISTANCE} mm")
    print(f"목표: 해상도 {MAX_RESOLUTION} mm/px 이하, 커버리지 95% 이상")
    print()

    # 전략 1: Y축 2분할 (상/하 배치) - 더 넓은 범위
    print("전략 1: 상/하 2분할 배치...")
    cx = BATTERY_WIDTH / 2
    for y1 in np.arange(300, 900, 100):
        for y2 in np.arange(1900, 2500, 100):
            for tilt in np.arange(0, 70, 10):
                cfg = test_config(
                    {'x': cx, 'y': y1, 'tilt_angle': tilt, 'tilt_direction': 90},
                    {'x': cx, 'y': y2, 'tilt_angle': tilt, 'tilt_direction': -90},
                    'vertical_split'
                )
                all_configs.append(cfg)

    # 전략 2: 대각선 배치
    print("전략 2: 대각선 배치...")
    for margin in [50, 100, 200, 300]:
        for tilt in np.arange(20, 70, 5):
            cfg = test_config(
                {'x': margin, 'y': margin, 'tilt_angle': tilt, 'tilt_direction': 45},
                {'x': BATTERY_WIDTH-margin, 'y': BATTERY_HEIGHT-margin,
                 'tilt_angle': tilt, 'tilt_direction': -135},
                'diagonal'
            )
            all_configs.append(cfg)

    # 전략 3: X축 양쪽 배치 (Y 중앙)
    print("전략 3: 좌/우 배치...")
    cy = BATTERY_HEIGHT / 2
    for x1 in np.arange(50, 500, 50):
        x2 = BATTERY_WIDTH - x1
        for tilt in np.arange(0, 70, 10):
            cfg = test_config(
                {'x': x1, 'y': cy, 'tilt_angle': tilt, 'tilt_direction': 0},
                {'x': x2, 'y': cy, 'tilt_angle': tilt, 'tilt_direction': 180},
                'horizontal_split'
            )
            all_configs.append(cfg)

    # 전략 4: 수직 (틸트 0) - Y 위치 다양화
    print("전략 4: 수직 배치 (틸트 0)...")
    for y1 in np.arange(300, 1000, 100):
        for y2 in np.arange(1800, 2500, 100):
            cfg = test_config(
                {'x': cx, 'y': y1, 'tilt_angle': 0, 'tilt_direction': 0},
                {'x': cx, 'y': y2, 'tilt_angle': 0, 'tilt_direction': 0},
                'vertical_no_tilt'
            )
            all_configs.append(cfg)

    # 전략 5: 4분할 위치 (대각선 반대)
    print("전략 5: 반대 대각선...")
    for margin in [50, 100, 200, 300]:
        for tilt in np.arange(20, 70, 5):
            cfg = test_config(
                {'x': BATTERY_WIDTH-margin, 'y': margin,
                 'tilt_angle': tilt, 'tilt_direction': 135},
                {'x': margin, 'y': BATTERY_HEIGHT-margin,
                 'tilt_angle': tilt, 'tilt_direction': -45},
                'diagonal_reverse'
            )
            all_configs.append(cfg)

    return all_configs


def main():
    configs = search_optimal_placement()

    # 유효한 배치와 근접 배치 분리
    valid_configs = [c for c in configs if c['valid']]
    near_configs = [c for c in configs
                    if not c['valid'] and c['coverage_pct'] >= 50]

    print(f"\n=== 결과 ===")
    print(f"전체 테스트: {len(configs)}개")
    print(f"조건 만족: {len(valid_configs)}개")
    print(f"근접 (커버리지 50%+): {len(near_configs)}개")

    if valid_configs:
        valid_configs.sort(key=lambda x: x['avg_resolution'])
        print(f"\n=== 조건 만족 배치 TOP 5 ===")
        for i, cfg in enumerate(valid_configs[:5]):
            print(f"\n[{i+1}] {cfg['strategy']}")
            print(f"    CAM1: x={cfg['cam1']['x']:.0f}, y={cfg['cam1']['y']:.0f}, "
                  f"tilt={cfg['cam1']['tilt_angle']:.0f}, dir={cfg['cam1']['tilt_direction']:.0f}")
            print(f"    CAM2: x={cfg['cam2']['x']:.0f}, y={cfg['cam2']['y']:.0f}, "
                  f"tilt={cfg['cam2']['tilt_angle']:.0f}, dir={cfg['cam2']['tilt_direction']:.0f}")
            print(f"    커버리지: {cfg['coverage_pct']:.1f}%")
            print(f"    해상도: {cfg['min_resolution']:.0f} ~ {cfg['max_resolution']:.0f} mm/px "
                  f"(avg: {cfg['avg_resolution']:.0f})")
    else:
        # 근접 배치 중 최고 출력
        near_configs.sort(key=lambda x: (-x['coverage_pct'], x['max_resolution']))
        print(f"\n=== 근접 배치 TOP 5 (조건 미달) ===")
        for i, cfg in enumerate(near_configs[:5]):
            print(f"\n[{i+1}] {cfg['strategy']}")
            print(f"    CAM1: x={cfg['cam1']['x']:.0f}, y={cfg['cam1']['y']:.0f}, "
                  f"tilt={cfg['cam1']['tilt_angle']:.0f}, dir={cfg['cam1']['tilt_direction']:.0f}")
            print(f"    CAM2: x={cfg['cam2']['x']:.0f}, y={cfg['cam2']['y']:.0f}, "
                  f"tilt={cfg['cam2']['tilt_angle']:.0f}, dir={cfg['cam2']['tilt_direction']:.0f}")
            print(f"    커버리지: {cfg['coverage_pct']:.1f}%")
            print(f"    해상도: {cfg['min_resolution']:.0f} ~ {cfg['max_resolution']:.0f} mm/px")

        print("\n카메라 2대로는 조건을 만족하기 어렵습니다.")
        print("권장: 카메라 3~4대 사용 또는 Working Distance 증가")

    # 최고 배치 JSON 출력
    if not valid_configs and not near_configs:
        print("\n배치를 찾지 못했습니다.")
        return
    best = valid_configs[0] if valid_configs else near_configs[0]
    print("\n=== 최적 배치 JSON ===")
    json_out = {
        "battery": {"width": BATTERY_WIDTH, "height": BATTERY_HEIGHT},
        "camera_spec": {
            "resolution_x": 32, "resolution_y": 24,
            "fov_h": 110, "fov_v": 75,
            "working_distance": WORKING_DISTANCE
        },
        "cameras": [
            {"id": 1, "x": float(best['cam1']['x']), "y": float(best['cam1']['y']),
             "tilt_angle": float(best['cam1']['tilt_angle']),
             "tilt_direction": float(best['cam1']['tilt_direction'])},
            {"id": 2, "x": float(best['cam2']['x']), "y": float(best['cam2']['y']),
             "tilt_angle": float(best['cam2']['tilt_angle']),
             "tilt_direction": float(best['cam2']['tilt_direction'])},
        ]
    }
    print(json.dumps(json_out, indent=2))


if __name__ == "__main__":
    main()
