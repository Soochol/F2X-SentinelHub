"""
MLX90640 4대 최적 배치 탐색
조건: 배터리 평면 70% 이상 커버리지, 해상도 200mm/px 이하
"""

import json
import numpy as np
from camera import Camera, CameraSpec, calculate_resolution_map, calculate_coverage_map

# 배터리 및 카메라 사양
BATTERY_WIDTH = 1700  # mm
BATTERY_HEIGHT = 2800  # mm
WORKING_DISTANCE = 350  # mm
MAX_RESOLUTION = 200  # mm/px
MIN_COVERAGE = 70  # %

camera_spec = CameraSpec(resolution_x=32, resolution_y=24, fov_h=110, fov_v=75)


def evaluate_placement(cameras: list) -> dict:
    """배치 평가"""
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
        }

    coverage_pct = 100 * covered_cells / total_cells
    max_res = np.max(valid_res)
    avg_res = np.mean(valid_res)

    valid = (coverage_pct >= MIN_COVERAGE) and (max_res <= MAX_RESOLUTION)

    return {
        'valid': valid,
        'coverage_pct': coverage_pct,
        'max_resolution': max_res,
        'avg_resolution': avg_res,
    }


def test_4cam_config(positions, tilts, strategy_name):
    """4대 카메라 배치 테스트"""
    cameras = []
    for i, (pos, tilt) in enumerate(zip(positions, tilts)):
        cam = Camera(
            id=i+1,
            x=pos[0], y=pos[1], z=WORKING_DISTANCE,
            tilt_angle=tilt[0], tilt_direction=tilt[1],
            spec=camera_spec
        )
        cameras.append(cam)

    result = evaluate_placement(cameras)
    return {
        'strategy': strategy_name,
        'cameras': [
            {'x': p[0], 'y': p[1], 'tilt_angle': t[0], 'tilt_direction': t[1]}
            for p, t in zip(positions, tilts)
        ],
        **result
    }


def search_optimal_4cam():
    """4대 카메라 최적 배치 탐색"""
    all_configs = []

    print("=== MLX90640 4대 최적 배치 탐색 ===")
    print(f"배터리: {BATTERY_WIDTH} x {BATTERY_HEIGHT} mm")
    print(f"Working Distance: {WORKING_DISTANCE} mm")
    print(f"목표: 커버리지 {MIN_COVERAGE}% 이상, 해상도 {MAX_RESOLUTION} mm/px 이하")
    print()

    cx = BATTERY_WIDTH / 2  # 850
    cy = BATTERY_HEIGHT / 2  # 1400

    # 전략 1: 2x2 그리드 배치 (균등 분할) - 확장 탐색
    print("전략 1: 2x2 그리드 배치...")
    for margin_x in [200, 300, 400, 500, 600]:
        for margin_y in [400, 500, 600, 700, 800, 900, 1000]:
            x1, x2 = margin_x, BATTERY_WIDTH - margin_x
            y1, y2 = margin_y, BATTERY_HEIGHT - margin_y

            positions = [
                (x1, y1), (x2, y1),
                (x1, y2), (x2, y2)
            ]

            for tilt in [0, 10, 20, 30, 40, 50, 60]:
                # 각 카메라가 중앙을 향하도록 틸트
                tilts = [
                    (tilt, 45),    # 좌하 -> 우상
                    (tilt, 135),   # 우하 -> 좌상
                    (tilt, -45),   # 좌상 -> 우하
                    (tilt, -135),  # 우상 -> 좌하
                ]
                cfg = test_4cam_config(positions, tilts, 'grid_2x2')
                all_configs.append(cfg)

    # 전략 2: Y축 4분할 (세로 배치)
    print("전략 2: Y축 4분할...")
    for tilt in [0, 30, 40, 50]:
        y_positions = [400, 1000, 1800, 2400]
        positions = [(cx, y) for y in y_positions]
        tilts = [
            (tilt, 90),   # 아래쪽
            (tilt, 90),
            (tilt, -90),  # 위쪽
            (tilt, -90),
        ]
        cfg = test_4cam_config(positions, tilts, 'vertical_4split')
        all_configs.append(cfg)

    # 전략 3: 마름모 배치
    print("전략 3: 마름모 배치...")
    for offset in [300, 400, 500]:
        positions = [
            (cx, offset),              # 하단
            (offset, cy),              # 좌측
            (BATTERY_WIDTH - offset, cy),  # 우측
            (cx, BATTERY_HEIGHT - offset), # 상단
        ]
        for tilt in [30, 40, 50]:
            tilts = [
                (tilt, 90),    # 위로
                (tilt, 0),     # 오른쪽으로
                (tilt, 180),   # 왼쪽으로
                (tilt, -90),   # 아래로
            ]
            cfg = test_4cam_config(positions, tilts, 'diamond')
            all_configs.append(cfg)

    # 전략 4: 코너 배치 (틸트 중앙향)
    print("전략 4: 코너 배치...")
    for margin in [100, 200, 300]:
        positions = [
            (margin, margin),
            (BATTERY_WIDTH - margin, margin),
            (margin, BATTERY_HEIGHT - margin),
            (BATTERY_WIDTH - margin, BATTERY_HEIGHT - margin),
        ]
        for tilt in [30, 40, 50, 60]:
            tilts = [
                (tilt, 45),
                (tilt, 135),
                (tilt, -45),
                (tilt, -135),
            ]
            cfg = test_4cam_config(positions, tilts, 'corner')
            all_configs.append(cfg)

    # 전략 5: 수직 배치 (틸트 없음)
    print("전략 5: 수직 배치 (틸트 0)...")
    for margin_x in [300, 400, 500]:
        for margin_y in [400, 600, 800]:
            x1, x2 = margin_x, BATTERY_WIDTH - margin_x
            y1, y2 = margin_y, BATTERY_HEIGHT - margin_y
            positions = [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]
            tilts = [(0, 0), (0, 0), (0, 0), (0, 0)]
            cfg = test_4cam_config(positions, tilts, 'vertical_no_tilt')
            all_configs.append(cfg)

    return all_configs


def main():
    configs = search_optimal_4cam()

    valid_configs = [c for c in configs if c['valid']]
    valid_configs.sort(key=lambda x: (-x['coverage_pct'], x['avg_resolution']))

    print(f"\n=== 결과 ===")
    print(f"전체 테스트: {len(configs)}개")
    print(f"조건 만족: {len(valid_configs)}개")

    if valid_configs:
        print(f"\n=== 최적 배치 TOP 5 ===")
        for i, cfg in enumerate(valid_configs[:5]):
            print(f"\n[{i+1}] {cfg['strategy']}")
            for j, cam in enumerate(cfg['cameras']):
                print(f"    CAM{j+1}: x={cam['x']:.0f}, y={cam['y']:.0f}, "
                      f"tilt={cam['tilt_angle']:.0f}, dir={cam['tilt_direction']:.0f}")
            print(f"    커버리지: {cfg['coverage_pct']:.1f}%")
            print(f"    최대 해상도: {cfg['max_resolution']:.0f} mm/px")

        # 최적 배치 JSON
        best = valid_configs[0]
        print("\n=== 최적 배치 JSON ===")
        json_out = {
            "battery": {"width": BATTERY_WIDTH, "height": BATTERY_HEIGHT},
            "camera_spec": {
                "model": "MLX90640",
                "resolution_x": 32, "resolution_y": 24,
                "fov_h": 110, "fov_v": 75,
                "working_distance": WORKING_DISTANCE
            },
            "cameras": [
                {"id": i+1, **cam} for i, cam in enumerate(best['cameras'])
            ],
            "result": {
                "coverage_pct": round(best['coverage_pct'], 1),
                "max_resolution_mm_px": round(best['max_resolution'], 1)
            }
        }
        print(json.dumps(json_out, indent=2))
    else:
        print("\n조건을 만족하는 배치를 찾지 못했습니다.")
        # 가장 근접한 배치 출력
        configs.sort(key=lambda x: (-x['coverage_pct'], x['max_resolution']))
        best = configs[0]
        print(f"\n가장 근접한 배치:")
        print(f"  전략: {best['strategy']}")
        print(f"  커버리지: {best['coverage_pct']:.1f}%")
        print(f"  최대 해상도: {best['max_resolution']:.0f} mm/px")


if __name__ == "__main__":
    main()
