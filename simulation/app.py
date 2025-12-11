"""
IR Camera Coverage Simulation - Streamlit Web App
배터리 화재 감지용 IR 카메라 배치 시뮬레이션
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd
import json
import hashlib
from camera import (
    Camera, CameraSpec,
    calculate_coverage_map,
    calculate_resolution_map,
    auto_tilt_to_center
)


@st.cache_data
def cached_resolution_map(_cameras_hash, battery_width, battery_height, grid_res, cameras_data):
    """캐시된 해상도 맵 계산"""
    cameras = []
    for cam_data in cameras_data:
        spec = CameraSpec(
            resolution_x=cam_data['spec_rx'],
            resolution_y=cam_data['spec_ry'],
            fov_h=cam_data['spec_fov_h'],
            fov_v=cam_data['spec_fov_v']
        )
        cam = Camera(
            id=cam_data['id'],
            x=cam_data['x'],
            y=cam_data['y'],
            z=cam_data['z'],
            tilt_angle=cam_data['tilt_angle'],
            tilt_direction=cam_data['tilt_direction'],
            spec=spec
        )
        cameras.append(cam)
    return calculate_resolution_map(cameras, battery_width, battery_height, grid_resolution=grid_res)


def get_cameras_hash(cameras):
    """카메라 설정의 해시값 생성"""
    data = str([(c.id, c.x, c.y, c.z, c.tilt_angle, c.tilt_direction) for c in cameras])
    return hashlib.md5(data.encode()).hexdigest()


def cameras_to_data(cameras):
    """카메라 객체를 직렬화 가능한 데이터로 변환"""
    return [
        {
            'id': c.id, 'x': c.x, 'y': c.y, 'z': c.z,
            'tilt_angle': c.tilt_angle, 'tilt_direction': c.tilt_direction,
            'spec_rx': c.spec.resolution_x, 'spec_ry': c.spec.resolution_y,
            'spec_fov_h': c.spec.fov_h, 'spec_fov_v': c.spec.fov_v
        }
        for c in cameras
    ]

# 페이지 설정
st.set_page_config(
    page_title="IR Camera Coverage Simulator",
    page_icon="📷",
    layout="wide"
)

# 세션 상태 초기화
if 'cameras' not in st.session_state:
    st.session_state.cameras = []
if 'next_camera_id' not in st.session_state:
    st.session_state.next_camera_id = 1
if 'working_distance' not in st.session_state:
    st.session_state.working_distance = 250

# 사이드바 - 설정
st.sidebar.title("⚙️ 설정")

st.sidebar.header("배터리 사양")
battery_width = st.sidebar.number_input("배터리 X (mm)", value=1700, min_value=100, max_value=5000, step=10)
battery_height = st.sidebar.number_input("배터리 Y (mm)", value=2800, min_value=100, max_value=5000, step=10)

st.sidebar.header("카메라 사양 (MLX90640)")
working_distance = st.sidebar.number_input("Working Distance (mm)", value=250, min_value=50, max_value=1000, step=10)
res_col1, res_col2 = st.sidebar.columns(2)
resolution_x = res_col1.number_input("수평 픽셀", value=32, min_value=1, max_value=128, step=1)
resolution_y = res_col2.number_input("수직 픽셀", value=24, min_value=1, max_value=128, step=1)
fov_h = st.sidebar.number_input("수평 FOV (°)", value=110.0, min_value=30.0, max_value=180.0, step=5.0)
fov_v = st.sidebar.number_input("수직 FOV (°)", value=75.0, min_value=30.0, max_value=180.0, step=5.0)

camera_spec = CameraSpec(resolution_x=resolution_x, resolution_y=resolution_y, fov_h=fov_h, fov_v=fov_v)

# 최대 안전 틸트 각도 (참고용)
max_safe_tilt = 90 - max(fov_h, fov_v) / 2
st.sidebar.caption(f"ℹ️ 틸트 {max_safe_tilt:.0f}° 초과 시 FOV가 크게 확장됨")

st.sidebar.divider()

# 카메라 추가 모드
st.sidebar.header("카메라 배치")
add_mode = st.sidebar.radio(
    "배치 모드",
    ["마우스 클릭", "좌표 입력", "프리셋"]
)

if add_mode == "좌표 입력":
    col1, col2 = st.sidebar.columns(2)
    new_cam_x = col1.number_input("X (mm)", value=0, min_value=0, max_value=int(battery_width))
    new_cam_y = col2.number_input("Y (mm)", value=0, min_value=0, max_value=int(battery_height))
    new_cam_tilt = st.sidebar.number_input("틸트 각도 (°)", value=0.0, min_value=0.0, max_value=85.0, step=5.0)
    auto_direction = st.sidebar.checkbox("자동 중앙 방향", value=True)

    if st.sidebar.button("➕ 카메라 추가", use_container_width=True):
        cam = Camera(
            id=st.session_state.next_camera_id,
            x=new_cam_x,
            y=new_cam_y,
            z=working_distance,
            tilt_angle=new_cam_tilt,
            spec=camera_spec
        )
        if auto_direction:
            _, tilt_dir = auto_tilt_to_center(cam, battery_width, battery_height)
            cam.tilt_direction = tilt_dir
        st.session_state.cameras.append(cam)
        st.session_state.next_camera_id += 1
        st.rerun()

elif add_mode == "프리셋":
    preset = st.sidebar.selectbox(
        "프리셋 선택",
        ["4모서리 (45° 틸트)", "4모서리 (수직)", "2×3 그리드", "3×4 그리드", "사용자 정의"]
    )

    default_tilt = 45.0 if "45°" in preset else 0.0
    preset_tilt = st.sidebar.number_input("틸트 각도 (°)", value=default_tilt, min_value=0.0, max_value=85.0, step=5.0)

    if st.sidebar.button("🎯 프리셋 적용", use_container_width=True):
        st.session_state.cameras = []
        st.session_state.next_camera_id = 1

        positions = []
        if "4모서리" in preset:
            margin = 50  # 모서리에서 약간 안쪽
            positions = [
                (margin, margin),
                (battery_width - margin, margin),
                (margin, battery_height - margin),
                (battery_width - margin, battery_height - margin),
            ]
        elif "2×3" in preset:
            for i in range(2):
                for j in range(3):
                    x = battery_width * (i + 0.5) / 2
                    y = battery_height * (j + 0.5) / 3
                    positions.append((x, y))
        elif "3×4" in preset:
            for i in range(3):
                for j in range(4):
                    x = battery_width * (i + 0.5) / 3
                    y = battery_height * (j + 0.5) / 4
                    positions.append((x, y))

        for x, y in positions:
            cam = Camera(
                id=st.session_state.next_camera_id,
                x=x,
                y=y,
                z=working_distance,
                tilt_angle=preset_tilt,
                spec=camera_spec
            )
            _, tilt_dir = auto_tilt_to_center(cam, battery_width, battery_height)
            cam.tilt_direction = tilt_dir
            st.session_state.cameras.append(cam)
            st.session_state.next_camera_id += 1

        st.rerun()

# 메인 영역
st.title("🔥 IR 카메라 커버리지 시뮬레이터")
st.caption("배터리 화재 감지용 MLX90640 카메라 배치 최적화")

# 탭 구성
tab2, tab4 = st.tabs(["🎯 3D 뷰", "📋 상세 정보"])

with tab2:
    st.subheader("3D FOV 시각화")

    # 3D 뷰와 카메라 컨트롤을 나란히 배치
    view_col, control_col = st.columns([3, 1])

    with control_col:
        st.markdown("#### 카메라 컨트롤")

        # 새 카메라 추가
        with st.expander("➕ 새 카메라 추가", expanded=not st.session_state.cameras):
            cam3d_x = st.number_input("X (mm)", value=int(battery_width//2), min_value=0, max_value=int(battery_width), step=50, key="cam3d_x")
            cam3d_y = st.number_input("Y (mm)", value=int(battery_height//2), min_value=0, max_value=int(battery_height), step=50, key="cam3d_y")
            cam3d_tilt = st.number_input("틸트 (°)", value=0.0, min_value=0.0, max_value=85.0, step=5.0, key="cam3d_tilt")
            cam3d_dir = st.number_input("방향 (°)", value=0.0, min_value=-180.0, max_value=180.0, step=15.0, key="cam3d_dir")
            if st.button("➕ 추가", key="add_cam_3d", use_container_width=True):
                cam = Camera(
                    id=st.session_state.next_camera_id,
                    x=cam3d_x,
                    y=cam3d_y,
                    z=working_distance,
                    tilt_angle=cam3d_tilt,
                    tilt_direction=cam3d_dir,
                    spec=camera_spec
                )
                st.session_state.cameras.append(cam)
                st.session_state.next_camera_id += 1
                st.rerun()

        # 빠른 프리셋
        st.markdown("##### 프리셋")
        preset_col1, preset_col2 = st.columns(2)
        with preset_col1:
            if st.button("🎯 4모서리", key="preset_4corner_3d", use_container_width=True):
                st.session_state.cameras = []
                st.session_state.next_camera_id = 1
                margin = 50
                positions = [
                    (margin, margin, 45, 45),
                    (battery_width - margin, margin, 45, 135),
                    (margin, battery_height - margin, 45, -45),
                    (battery_width - margin, battery_height - margin, 45, -135),
                ]
                for x, y, tilt, direction in positions:
                    cam = Camera(id=st.session_state.next_camera_id, x=x, y=y, z=working_distance,
                               tilt_angle=tilt, tilt_direction=direction, spec=camera_spec)
                    st.session_state.cameras.append(cam)
                    st.session_state.next_camera_id += 1
                st.rerun()
        with preset_col2:
            if st.button("📐 중앙 1대", key="preset_center_3d", use_container_width=True):
                st.session_state.cameras = []
                st.session_state.next_camera_id = 1
                cam = Camera(id=1, x=battery_width/2, y=battery_height/2, z=working_distance,
                           tilt_angle=0, tilt_direction=0, spec=camera_spec)
                st.session_state.cameras.append(cam)
                st.session_state.next_camera_id = 2
                st.rerun()

        if st.button("🗑️ 모두 삭제", key="clear_all_3d", use_container_width=True):
            st.session_state.cameras = []
            st.session_state.next_camera_id = 1
            st.rerun()

        st.divider()

        # JSON 저장/불러오기
        st.markdown("##### 설정 저장/불러오기")

        # 저장 버튼
        if st.session_state.cameras:
            camera_data = {
                "battery": {
                    "width": battery_width,
                    "height": battery_height
                },
                "camera_spec": {
                    "resolution_x": resolution_x,
                    "resolution_y": resolution_y,
                    "fov_h": fov_h,
                    "fov_v": fov_v,
                    "working_distance": working_distance
                },
                "cameras": [
                    {
                        "id": cam.id,
                        "x": cam.x,
                        "y": cam.y,
                        "tilt_angle": cam.tilt_angle,
                        "tilt_direction": cam.tilt_direction
                    }
                    for cam in st.session_state.cameras
                ]
            }
            json_str = json.dumps(camera_data, indent=2, ensure_ascii=False)
            st.download_button(
                label="💾 JSON 저장",
                data=json_str,
                file_name="camera_config.json",
                mime="application/json",
                use_container_width=True
            )

        # 불러오기
        uploaded_file = st.file_uploader("📂 JSON 불러오기", type=["json"], key="json_upload")

        # 파일 처리 상태 추적
        if 'last_uploaded_file' not in st.session_state:
            st.session_state.last_uploaded_file = None

        if uploaded_file is not None and uploaded_file.name != st.session_state.last_uploaded_file:
            try:
                loaded_data = json.load(uploaded_file)
                st.session_state.cameras = []
                st.session_state.next_camera_id = 1
                st.session_state.last_uploaded_file = uploaded_file.name

                # JSON에서 working_distance 읽기
                loaded_wd = loaded_data.get("camera_spec", {}).get("working_distance", working_distance)
                st.session_state.working_distance = loaded_wd

                for cam_data in loaded_data.get("cameras", []):
                    cam = Camera(
                        id=st.session_state.next_camera_id,
                        x=cam_data["x"],
                        y=cam_data["y"],
                        z=loaded_wd,
                        tilt_angle=cam_data.get("tilt_angle", 0),
                        tilt_direction=cam_data.get("tilt_direction", 0),
                        spec=camera_spec
                    )
                    st.session_state.cameras.append(cam)
                    st.session_state.next_camera_id += 1

                st.success(f"✅ {len(st.session_state.cameras)}개 카메라 로드됨 (WD: {loaded_wd}mm)")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 파일 로드 실패: {e}")

        st.divider()

        # 카메라 카드 목록
        st.markdown(f"##### 카메라 목록 ({len(st.session_state.cameras)}대)")

        cameras_to_remove_3d = []
        for idx, cam in enumerate(st.session_state.cameras):
            color = px.colors.qualitative.Set1[idx % len(px.colors.qualitative.Set1)]
            with st.container(border=True):
                st.markdown(f"<span style='color:{color}'>●</span> **CAM {cam.id}**", unsafe_allow_html=True)

                # X, Y 위치
                col_xy1, col_xy2 = st.columns(2)
                new_x = col_xy1.number_input("X", value=float(cam.x), min_value=0.0, max_value=float(battery_width),
                                            step=50.0, format="%.0f", key=f"cam3d_x_{cam.id}")
                new_y = col_xy2.number_input("Y", value=float(cam.y), min_value=0.0, max_value=float(battery_height),
                                            step=50.0, format="%.0f", key=f"cam3d_y_{cam.id}")

                # 틸트, 방향
                col_td1, col_td2 = st.columns(2)
                new_tilt = col_td1.number_input("틸트°", value=float(cam.tilt_angle), min_value=0.0, max_value=85.0,
                                               step=5.0, format="%.0f", key=f"cam3d_tilt_{cam.id}")
                new_dir = col_td2.number_input("방향°", value=float(cam.tilt_direction), min_value=-180.0, max_value=180.0,
                                              step=15.0, format="%.0f", key=f"cam3d_dir_{cam.id}")

                # 값 업데이트
                cam.x = new_x
                cam.y = new_y
                cam.tilt_angle = new_tilt
                cam.tilt_direction = new_dir
                cam.z = working_distance
                cam.spec = camera_spec

                # 삭제 버튼
                if st.button("🗑️ 삭제", key=f"del_cam3d_{cam.id}", use_container_width=True):
                    cameras_to_remove_3d.append(idx)

        # 삭제 처리
        for idx in sorted(cameras_to_remove_3d, reverse=True):
            st.session_state.cameras.pop(idx)
        if cameras_to_remove_3d:
            st.rerun()

    with view_col:
        # 3D 뷰 렌더링
        # 3D Figure 생성
        fig_3d = go.Figure()

        # 1) 배터리 면 (Z=0 평면) - 반투명 사각형
        fig_3d.add_trace(go.Mesh3d(
            x=[0, battery_width, battery_width, 0],
            y=[0, 0, battery_height, battery_height],
            z=[0, 0, 0, 0],
            i=[0, 0],
            j=[1, 2],
            k=[2, 3],
            color='gray',
            opacity=0.3,
            name='배터리 면',
            hoverinfo='skip'
        ))

        # 배터리 외곽선
        fig_3d.add_trace(go.Scatter3d(
            x=[0, battery_width, battery_width, 0, 0],
            y=[0, 0, battery_height, battery_height, 0],
            z=[0, 0, 0, 0, 0],
            mode='lines',
            line=dict(color='white', width=4),
            name='배터리 경계',
            hoverinfo='skip'
        ))

        # 해상도 히트맵 (Z=0 평면)
        if st.session_state.cameras:
            # 해상도 맵 계산 (캐시 사용, 15=빠름)
            heatmap_res = 15
            cam_hash = get_cameras_hash(st.session_state.cameras)
            cam_data = cameras_to_data(st.session_state.cameras)
            X_hm, Y_hm, res_map = cached_resolution_map(
                cam_hash, battery_width, battery_height, heatmap_res, cam_data
            )

            # NaN을 큰 값으로 대체 (커버되지 않는 영역)
            res_map_clean = np.where(np.isnan(res_map), 0, res_map)

            # Surface plot으로 해상도 히트맵 표시 (투명하게)
            fig_3d.add_trace(go.Surface(
                x=X_hm[0, :],  # X 좌표 (1D)
                y=Y_hm[:, 0],  # Y 좌표 (1D)
                z=np.zeros_like(res_map_clean) + 1,  # Z=1 (약간 위에 표시)
                surfacecolor=res_map_clean,
                colorscale='RdYlGn_r',  # 빨강(높음=나쁨) → 녹색(낮음=좋음)
                cmin=10,
                cmax=300,
                opacity=0.3,  # 더 투명하게
                showscale=True,
                colorbar=dict(
                    title=dict(text='해상도<br>(mm/px)', font=dict(color='white')),
                    x=1.02,
                    len=0.5,
                    tickfont=dict(color='white')
                ),
                name='해상도 맵',
                hovertemplate='X: %{x:.0f}mm<br>Y: %{y:.0f}mm<br>해상도: %{surfacecolor:.1f}mm/px<extra></extra>'
            ))

        # 그리드 라인 (Z=0 평면) - 회색
        grid_spacing = 100  # 100mm 간격
        grid_color = 'rgba(128, 128, 128, 0.5)'  # 회색

        # X 방향 그리드 라인
        for x in range(0, int(battery_width) + 1, grid_spacing):
            fig_3d.add_trace(go.Scatter3d(
                x=[x, x],
                y=[0, battery_height],
                z=[2, 2],  # 히트맵 위에 표시
                mode='lines',
                line=dict(color=grid_color, width=1),
                showlegend=False,
                hoverinfo='skip'
            ))

        # Y 방향 그리드 라인
        for y in range(0, int(battery_height) + 1, grid_spacing):
            fig_3d.add_trace(go.Scatter3d(
                x=[0, battery_width],
                y=[y, y],
                z=[2, 2],  # 히트맵 위에 표시
                mode='lines',
                line=dict(color=grid_color, width=1),
                showlegend=False,
                hoverinfo='skip'
            ))

        # 2) 각 카메라별 FOV 피라미드
        if st.session_state.cameras:
            colors_3d = px.colors.qualitative.Set1
            for i, cam in enumerate(st.session_state.cameras):
                color = colors_3d[i % len(colors_3d)]
                pyramid = cam.get_fov_pyramid_vertices()

                cam_pos = pyramid['camera_pos']
                corners = pyramid['corners_3d']
                center = pyramid['center_3d']

                # 카메라 위치 마커
                fig_3d.add_trace(go.Scatter3d(
                    x=[cam_pos[0]],
                    y=[cam_pos[1]],
                    z=[cam_pos[2]],
                    mode='markers+text',
                    marker=dict(size=8, color=color, symbol='diamond'),
                    text=[f"CAM{cam.id}"],
                    textposition="top center",
                    name=f'CAM {cam.id}',
                    hovertemplate=f"<b>CAM {cam.id}</b><br>위치: ({cam_pos[0]:.0f}, {cam_pos[1]:.0f}, {cam_pos[2]:.0f})<br>틸트: {cam.tilt_angle:.1f}°<extra></extra>"
                ))

                # FOV 피라미드 모서리 선 (카메라 → 4개 모서리)
                for j, corner in enumerate(corners):
                    fig_3d.add_trace(go.Scatter3d(
                        x=[cam_pos[0], corner[0]],
                        y=[cam_pos[1], corner[1]],
                        z=[cam_pos[2], corner[2]],
                        mode='lines',
                        line=dict(color=color, width=2),
                        showlegend=False,
                        hoverinfo='skip'
                    ))

                # FOV 중심선 (카메라 → FOV 중심)
                fig_3d.add_trace(go.Scatter3d(
                    x=[cam_pos[0], center[0]],
                    y=[cam_pos[1], center[1]],
                    z=[cam_pos[2], center[2]],
                    mode='lines',
                    line=dict(color=color, width=3, dash='dash'),
                    showlegend=False,
                    hoverinfo='skip'
                ))

                # 배터리 면의 FOV 영역 (폴리곤)
                corners_x = [c[0] for c in corners] + [corners[0][0]]
                corners_y = [c[1] for c in corners] + [corners[0][1]]
                corners_z = [c[2] for c in corners] + [corners[0][2]]

                fig_3d.add_trace(go.Scatter3d(
                    x=corners_x,
                    y=corners_y,
                    z=corners_z,
                    mode='lines',
                    line=dict(color=color, width=3),
                    showlegend=False,
                    hoverinfo='skip'
                ))

                # FOV 영역 채우기 (Mesh3d)
                if len(corners) == 4:
                    fig_3d.add_trace(go.Mesh3d(
                        x=[c[0] for c in corners],
                        y=[c[1] for c in corners],
                        z=[c[2] for c in corners],
                        i=[0, 0],
                        j=[1, 2],
                        k=[2, 3],
                        color=color,
                        opacity=0.2,
                        showlegend=False,
                        hoverinfo='skip'
                    ))

        # 레이아웃 설정 - 원점 (0,0)에서 시작, FOV가 배터리 면을 벗어나도 표시
        x_min, x_max = 0, battery_width
        y_min, y_max = 0, battery_height

        # 모든 카메라의 FOV 꼭지점을 포함하도록 범위 확장
        if st.session_state.cameras:
            for cam in st.session_state.cameras:
                pyramid = cam.get_fov_pyramid_vertices()
                for corner in pyramid['corners_3d']:
                    x_min = min(x_min, corner[0])
                    x_max = max(x_max, corner[0])
                    y_min = min(y_min, corner[1])
                    y_max = max(y_max, corner[1])

        # 여백 추가 (음수 방향도 포함)
        x_min = min(0, x_min - 100)
        x_max += 100
        y_min = min(0, y_min - 100)
        y_max += 100

        fig_3d.update_layout(
            scene=dict(
                xaxis=dict(title='X (mm)', range=[x_min, x_max]),
                yaxis=dict(title='Y (mm)', range=[y_min, y_max]),
                zaxis=dict(title='Z (mm)', range=[0, working_distance + 100]),
                aspectmode='data',
                bgcolor='rgb(30, 30, 30)',
                camera=dict(
                    eye=dict(x=1.5, y=-1.5, z=1.2),
                    center=dict(x=0, y=0, z=-0.1)
                ),
                dragmode='turntable'
            ),
            height=700,
            margin=dict(r=20, l=20, t=40, b=20),
            paper_bgcolor='rgb(30, 30, 30)',
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(50, 50, 50, 0.8)',
                font=dict(color='white')
            ),
            uirevision='3d_view_constant'  # 카메라 시점 유지
        )

        st.plotly_chart(fig_3d, use_container_width=True, key="3d_view")

        # 3D 뷰 설명
        st.caption("마우스 드래그: 회전 | 스크롤: 줌 | 더블클릭: 리셋")

        # 해상도 통계 표시
        if st.session_state.cameras:
            valid_res = res_map[~np.isnan(res_map)]
            if len(valid_res) > 0:
                stat_cols = st.columns(3)
                stat_cols[0].metric("최소 해상도 (최상)", f"{np.min(valid_res):.1f} mm/px")
                stat_cols[1].metric("평균 해상도", f"{np.mean(valid_res):.1f} mm/px")
                stat_cols[2].metric("최대 해상도 (최하)", f"{np.max(valid_res):.1f} mm/px")

with tab4:
    st.subheader("상세 정보")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 배터리 사양")
        st.markdown(f"""
        - **크기**: {battery_width} × {battery_height} mm
        - **면적**: {battery_width * battery_height / 1e6:.2f} m²
        """)

        st.markdown("#### 카메라 사양 (MLX90640)")
        st.markdown(f"""
        - **해상도**: 32 × 24 픽셀
        - **FOV**: {fov_h}° × {fov_v}°
        - **Working Distance**: {working_distance} mm
        """)

        # WD에서의 기본 커버 영역 계산
        base_cover_h = 2 * working_distance * np.tan(np.radians(fov_h/2))
        base_cover_v = 2 * working_distance * np.tan(np.radians(fov_v/2))
        base_res_h = base_cover_h / 32
        base_res_v = base_cover_v / 24

        st.markdown(f"""
        **WD {working_distance}mm 기준 (수직 시)**:
        - 커버 영역: {base_cover_h:.0f} × {base_cover_v:.0f} mm
        - 해상도: {base_res_h:.1f} × {base_res_v:.1f} mm/pixel
        """)

    with col2:
        st.markdown("#### 카메라 배치 정보")

        if st.session_state.cameras:
            cam_data = []
            for cam in st.session_state.cameras:
                corners, center, width, height = cam.calculate_footprint()
                cam_data.append({
                    "ID": f"CAM {cam.id}",
                    "위치 X (mm)": f"{cam.x:.0f}",
                    "위치 Y (mm)": f"{cam.y:.0f}",
                    "틸트 (°)": f"{cam.tilt_angle:.1f}",
                    "방향 (°)": f"{cam.tilt_direction:.1f}",
                    "커버 폭 (mm)": f"{width:.0f}",
                    "커버 높이 (mm)": f"{height:.0f}",
                })

            df = pd.DataFrame(cam_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # 전체 커버리지 통계
            if len(st.session_state.cameras) > 0:
                X, Y, coverage = calculate_coverage_map(
                    st.session_state.cameras,
                    battery_width,
                    battery_height,
                    grid_resolution=20
                )

                total_cells = coverage.size
                covered_cells = np.sum(coverage > 0)
                multi_covered = np.sum(coverage >= 2)

                st.markdown("#### 커버리지 통계")
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("전체 커버율", f"{100 * covered_cells / total_cells:.1f}%")
                col_b.metric("중복 커버율", f"{100 * multi_covered / total_cells:.1f}%")
                col_c.metric("최대 중복 수", f"{np.max(coverage)}개")
        else:
            st.info("카메라를 배치해주세요.")

    # 디버그 정보
    if st.session_state.cameras:
        st.divider()
        st.markdown("### 디버그 로그")

        for cam in st.session_state.cameras:
            with st.expander(f"CAM {cam.id} 상세 계산"):
                # 기본 정보
                st.markdown(f"""
                **입력 파라미터:**
                - 카메라 위치: ({cam.x:.1f}, {cam.y:.1f}) mm
                - Working Distance: {cam.z:.1f} mm
                - 틸트 각도: {cam.tilt_angle:.1f}°
                - 틸트 방향: {cam.tilt_direction:.1f}°
                - FOV: {cam.spec.fov_h}° x {cam.spec.fov_v}°
                """)

                # FOV 모서리 계산
                polygon = cam.get_coverage_polygon()
                fov_center_x, fov_center_y = cam.pixel_to_world(
                (cam.spec.resolution_x - 1) / 2, (cam.spec.resolution_y - 1) / 2
            )

                st.markdown(f"""
                **FOV 계산 결과:**
                - FOV 중심: ({fov_center_x:.1f}, {fov_center_y:.1f}) mm
                - 모서리 0 (픽셀 0,0): ({polygon[0][0]:.1f}, {polygon[0][1]:.1f})
                - 모서리 1 (픽셀 31,0): ({polygon[1][0]:.1f}, {polygon[1][1]:.1f})
                - 모서리 2 (픽셀 31,23): ({polygon[2][0]:.1f}, {polygon[2][1]:.1f})
                - 모서리 3 (픽셀 0,23): ({polygon[3][0]:.1f}, {polygon[3][1]:.1f})
                """)

                # 틸트 효과 검증
                if cam.tilt_angle > 0:
                    # 틸트 방향으로 이동한 거리
                    shift_x = fov_center_x - cam.x
                    shift_y = fov_center_y - cam.y
                    shift_dist = np.sqrt(shift_x**2 + shift_y**2)
                    shift_angle = np.degrees(np.arctan2(shift_y, shift_x))

                    # 예상 이동 거리 (tan(tilt) * WD)
                    expected_shift = cam.z * np.tan(np.radians(cam.tilt_angle))

                    st.markdown(f"""
                    **틸트 효과 검증:**
                    - FOV 중심 이동: ({shift_x:.1f}, {shift_y:.1f}) mm
                    - 이동 거리: {shift_dist:.1f} mm (예상: {expected_shift:.1f} mm)
                    - 이동 방향: {shift_angle:.1f}° (설정: {cam.tilt_direction:.1f}°)
                    """)

                    # 일치 여부
                    dist_ok = abs(shift_dist - expected_shift) < 10
                    angle_ok = abs(shift_angle - cam.tilt_direction) < 5 or abs(abs(shift_angle - cam.tilt_direction) - 360) < 5

                    if dist_ok and angle_ok:
                        st.success("틸트 계산 정상")
                    else:
                        st.warning(f"틸트 계산 불일치 - 거리: {'OK' if dist_ok else 'NG'}, 방향: {'OK' if angle_ok else 'NG'}")

                # FOV 크기
                width = np.max(polygon[:, 0]) - np.min(polygon[:, 0])
                height = np.max(polygon[:, 1]) - np.min(polygon[:, 1])

                st.markdown(f"""
                **FOV 크기:**
                - 가로: {width:.1f} mm
                - 세로: {height:.1f} mm
                """)

# Footer
st.divider()
st.caption("SentinelHub - IR Camera Coverage Simulator | MLX90640 기반 배터리 화재 감지 시스템")
