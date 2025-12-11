"""
IR Camera Coverage Simulation - Camera Module
MLX90640 카메라의 FOV, 커버리지, 해상도 계산
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class CameraSpec:
    """MLX90640 카메라 사양"""
    resolution_x: int = 32  # 픽셀
    resolution_y: int = 24  # 픽셀
    fov_h: float = 110.0    # 수평 FOV (도)
    fov_v: float = 75.0     # 수직 FOV (도)


@dataclass
class Camera:
    """카메라 인스턴스"""
    id: int
    x: float  # 카메라 X 위치 (mm)
    y: float  # 카메라 Y 위치 (mm)
    z: float  # Working Distance (mm)
    tilt_angle: float = 0.0  # 틸트 각도 (도, 0=수직 아래)
    tilt_direction: float = 0.0  # 틸트 방향 (도, 0=+X방향, 90=+Y방향)
    spec: CameraSpec = None

    def __post_init__(self):
        if self.spec is None:
            self.spec = CameraSpec()

    def calculate_footprint(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        카메라 footprint (배터리 면에서의 커버 영역) 계산

        Returns:
            corners: 4개 모서리 좌표 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
            center: 중심 좌표
            width: 수평 커버 크기 (mm)
            height: 수직 커버 크기 (mm)
        """
        # FOV를 라디안으로 변환
        fov_h_rad = np.radians(self.spec.fov_h)
        fov_v_rad = np.radians(self.spec.fov_v)
        tilt_rad = np.radians(self.tilt_angle)
        dir_rad = np.radians(self.tilt_direction)

        # 틸트가 없을 때의 기본 커버 영역
        half_h = self.z * np.tan(fov_h_rad / 2)
        half_v = self.z * np.tan(fov_v_rad / 2)

        if self.tilt_angle == 0:
            # 수직 아래를 볼 때 - FOV 사각형을 틸트 방향으로 회전
            # 기본 모서리 (회전 전)
            base_corners = np.array([
                [-half_h, -half_v],
                [half_h, -half_v],
                [half_h, half_v],
                [-half_h, half_v],
            ])

            # 틸트 방향으로 회전 (Z축 기준)
            cos_d = np.cos(dir_rad)
            sin_d = np.sin(dir_rad)
            rotation_matrix = np.array([
                [cos_d, -sin_d],
                [sin_d, cos_d]
            ])

            # 회전 적용 후 카메라 위치로 이동
            rotated_corners = (rotation_matrix @ base_corners.T).T
            corners = rotated_corners + np.array([self.x, self.y])

            center = np.array([self.x, self.y])
            return corners, center, half_h * 2, half_v * 2

        # 틸트가 있을 때 - 광선 추적으로 계산
        # 카메라 중심에서 배터리 면까지의 광선
        corners = []

        # 4개 모서리 픽셀에 대해 계산 (0,0), (31,0), (31,23), (0,23)
        corner_pixels = [
            (0, 0),
            (self.spec.resolution_x - 1, 0),
            (self.spec.resolution_x - 1, self.spec.resolution_y - 1),
            (0, self.spec.resolution_y - 1),
        ]

        for px, py in corner_pixels:
            world_x, world_y = self.pixel_to_world(px, py)
            corners.append([world_x, world_y])

        corners = np.array(corners)

        # 중심점 (픽셀 중심)
        center_x, center_y = self.pixel_to_world(
            self.spec.resolution_x / 2 - 0.5,
            self.spec.resolution_y / 2 - 0.5
        )
        center = np.array([center_x, center_y])

        # 대략적인 크기 계산
        width = np.max(corners[:, 0]) - np.min(corners[:, 0])
        height = np.max(corners[:, 1]) - np.min(corners[:, 1])

        return corners, center, width, height

    def pixel_to_world(self, px: float, py: float) -> Tuple[Optional[float], Optional[float]]:
        """
        픽셀 좌표를 월드 좌표 (배터리 면)로 변환

        Args:
            px: 픽셀 X (0~31)
            py: 픽셀 Y (0~23)

        Returns:
            (world_x, world_y) 또는 (None, None) if 배터리 면에 닿지 않음
        """
        # 픽셀 위치를 각도로 변환
        fov_h_rad = np.radians(self.spec.fov_h)
        fov_v_rad = np.radians(self.spec.fov_v)

        # 픽셀 중심 기준 각도
        angle_h = (px - (self.spec.resolution_x - 1) / 2) / (self.spec.resolution_x - 1) * fov_h_rad
        angle_v = (py - (self.spec.resolution_y - 1) / 2) / (self.spec.resolution_y - 1) * fov_v_rad

        # 광선 방향 벡터 (카메라 로컬 좌표계)
        # 카메라는 -Z 방향을 바라봄 (아래)
        ray_local = np.array([
            np.tan(angle_h),
            np.tan(angle_v),
            -1.0
        ])
        ray_local = ray_local / np.linalg.norm(ray_local)

        # 틸트 적용 (카메라 기울임)
        # 틸트 방향: 0° = +X 방향, 90° = +Y 방향
        tilt_rad = np.radians(self.tilt_angle)
        dir_rad = np.radians(self.tilt_direction)

        cos_t = np.cos(tilt_rad)
        sin_t = np.sin(tilt_rad)
        cos_d = np.cos(dir_rad)
        sin_d = np.sin(dir_rad)

        # 틸트 방향 축을 기준으로 회전
        # 틸트 방향이 0°(+X)일 때: Y축 기준 회전 (카메라가 +X 방향으로 기울어짐)
        # 틸트 방향이 90°(+Y)일 때: X축 기준 회전 (카메라가 +Y 방향으로 기울어짐)
        #
        # 임의의 틸트 방향에 대해:
        # 1. 먼저 Z축 기준으로 -dir_rad 회전하여 틸트 방향을 +X로 정렬
        # 2. Y축 기준으로 tilt_rad 회전 (카메라가 +X로 기울어짐)
        # 3. Z축 기준으로 +dir_rad 회전하여 원래 방향으로 복원

        # Z축 기준 회전 행렬 (틸트 방향 정렬용)
        Rz_neg = np.array([
            [cos_d, sin_d, 0],
            [-sin_d, cos_d, 0],
            [0, 0, 1]
        ])
        Rz_pos = np.array([
            [cos_d, -sin_d, 0],
            [sin_d, cos_d, 0],
            [0, 0, 1]
        ])

        # Y축 기준 회전 (틸트)
        Ry = np.array([
            [cos_t, 0, sin_t],
            [0, 1, 0],
            [-sin_t, 0, cos_t]
        ])

        # 복합 회전: Rz(+dir) @ Ry(tilt) @ Rz(-dir)
        R_combined = Rz_pos @ Ry @ Rz_neg

        # 광선 회전 적용
        ray_tilted = R_combined @ ray_local

        # 광선-평면 교차 (배터리 면 Z=0)
        if ray_tilted[2] >= -0.001:
            # 광선이 위로 가거나 거의 수평 -> 매우 먼 거리로 투영
            far_distance = 10000  # 10m
            world_x = self.x + far_distance * ray_tilted[0]
            world_y = self.y + far_distance * ray_tilted[1]
        else:
            t = -self.z / ray_tilted[2]
            world_x = self.x + t * ray_tilted[0]
            world_y = self.y + t * ray_tilted[1]

        return world_x, world_y

    def calculate_pixel_resolution(self, px: float, py: float) -> Tuple[float, float]:
        """
        특정 픽셀 위치에서의 해상도 (mm/pixel) 계산

        Returns:
            (resolution_x, resolution_y) in mm/pixel
        """
        # 현재 픽셀과 인접 픽셀의 월드 좌표 비교
        x1, y1 = self.pixel_to_world(px, py)
        x2, y2 = self.pixel_to_world(px + 1, py)
        x3, y3 = self.pixel_to_world(px, py + 1)

        if any(v is None for v in [x1, y1, x2, y2, x3, y3]):
            return float('inf'), float('inf')

        res_x = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        res_y = np.sqrt((x3 - x1)**2 + (y3 - y1)**2)

        return res_x, res_y

    def get_coverage_polygon(self) -> np.ndarray:
        """커버리지 영역을 다각형으로 반환"""
        corners, _, _, _ = self.calculate_footprint()
        return corners

    def get_fov_pyramid_vertices(self) -> dict:
        """
        3D 시각화용 FOV 피라미드 꼭지점 반환

        Returns:
            {
                'camera_pos': [x, y, z],  # 카메라 위치 (3D)
                'corners_3d': [[x,y,z], ...],  # 4개 모서리의 3D 좌표 (배터리 면, z=0)
                'center_3d': [x, y, z],  # FOV 중심점 (배터리 면, z=0)
            }
        """
        # 카메라 위치 (Z = working distance)
        camera_pos = [self.x, self.y, self.z]

        # 배터리 면에서의 4개 모서리 (z=0)
        corners_2d = self.get_coverage_polygon()
        corners_3d = [[c[0], c[1], 0] for c in corners_2d]

        # FOV 중심점
        center_x, center_y = self.pixel_to_world(
            (self.spec.resolution_x - 1) / 2,
            (self.spec.resolution_y - 1) / 2
        )
        center_3d = [center_x, center_y, 0]

        return {
            'camera_pos': camera_pos,
            'corners_3d': corners_3d,
            'center_3d': center_3d,
        }

    def get_all_pixel_positions(self) -> np.ndarray:
        """모든 픽셀의 월드 좌표 반환 (32x24 배열)"""
        positions = np.zeros((self.spec.resolution_x, self.spec.resolution_y, 2))

        for px in range(self.spec.resolution_x):
            for py in range(self.spec.resolution_y):
                x, y = self.pixel_to_world(px, py)
                if x is not None:
                    positions[px, py] = [x, y]
                else:
                    positions[px, py] = [np.nan, np.nan]

        return positions


def calculate_coverage_map(
    cameras: List[Camera],
    battery_width: float,
    battery_height: float,
    grid_resolution: float = 10.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    전체 배터리 영역에 대한 커버리지 맵 계산

    Args:
        cameras: 카메라 리스트
        battery_width: 배터리 폭 (mm)
        battery_height: 배터리 높이 (mm)
        grid_resolution: 그리드 해상도 (mm)

    Returns:
        X, Y: 그리드 좌표
        coverage_count: 각 그리드 셀을 보는 카메라 수
    """
    # 그리드 생성
    x = np.arange(0, battery_width + grid_resolution, grid_resolution)
    y = np.arange(0, battery_height + grid_resolution, grid_resolution)
    X, Y = np.meshgrid(x, y)

    coverage_count = np.zeros_like(X, dtype=int)

    for camera in cameras:
        polygon = camera.get_coverage_polygon()

        # 각 그리드 포인트가 다각형 내부인지 확인
        for i in range(X.shape[0]):
            for j in range(X.shape[1]):
                if point_in_polygon(X[i, j], Y[i, j], polygon):
                    coverage_count[i, j] += 1

    return X, Y, coverage_count


def calculate_resolution_map(
    cameras: List[Camera],
    battery_width: float,
    battery_height: float,
    grid_resolution: float = 20.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    전체 배터리 영역에 대한 해상도 맵 계산 (최적 해상도)

    Returns:
        X, Y: 그리드 좌표
        best_resolution: 각 위치에서의 최적 해상도 (mm/pixel)
    """
    x = np.arange(0, battery_width + grid_resolution, grid_resolution)
    y = np.arange(0, battery_height + grid_resolution, grid_resolution)
    X, Y = np.meshgrid(x, y)

    best_resolution = np.full_like(X, np.inf, dtype=float)

    for camera in cameras:
        positions = camera.get_all_pixel_positions()

        # 각 픽셀의 해상도 계산
        for px in range(camera.spec.resolution_x - 1):
            for py in range(camera.spec.resolution_y - 1):
                if np.isnan(positions[px, py, 0]):
                    continue

                res_x, res_y = camera.calculate_pixel_resolution(px, py)
                avg_res = (res_x + res_y) / 2

                # 해당 픽셀 위치 근처의 그리드 셀 업데이트
                world_x, world_y = positions[px, py]

                # 가장 가까운 그리드 셀 찾기
                gi = int(round(world_y / grid_resolution))
                gj = int(round(world_x / grid_resolution))

                if 0 <= gi < best_resolution.shape[0] and 0 <= gj < best_resolution.shape[1]:
                    best_resolution[gi, gj] = min(best_resolution[gi, gj], avg_res)

    # 무한대 값을 NaN으로 변환 (커버되지 않는 영역)
    best_resolution[np.isinf(best_resolution)] = np.nan

    return X, Y, best_resolution


def point_in_polygon(x: float, y: float, polygon: np.ndarray) -> bool:
    """점이 다각형 내부에 있는지 확인 (Ray casting algorithm)"""
    n = len(polygon)
    inside = False

    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i

    return inside


def auto_tilt_to_center(camera: Camera, battery_width: float, battery_height: float) -> Tuple[float, float]:
    """
    카메라가 배터리 중앙을 향하도록 틸트 각도와 방향 계산

    Returns:
        (tilt_angle, tilt_direction)
    """
    center_x = battery_width / 2
    center_y = battery_height / 2

    dx = center_x - camera.x
    dy = center_y - camera.y

    # 수평 거리
    horizontal_dist = np.sqrt(dx**2 + dy**2)

    if horizontal_dist < 1:  # 이미 중앙에 있음
        return 0.0, 0.0

    # 틸트 각도 (수직에서 기울어진 각도)
    tilt_angle = np.degrees(np.arctan2(horizontal_dist, camera.z))

    # 틸트 방향 (중앙을 향하는 방향)
    tilt_direction = np.degrees(np.arctan2(dy, dx))

    return tilt_angle, tilt_direction
