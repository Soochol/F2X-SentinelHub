"""
IR Camera Coverage Simulation - Streamlit Web App
배터리 화재 감지용 IR 카메라 배치 시뮬레이션
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
from camera import (
    Camera, CameraSpec,
    calculate_coverage_map,
    calculate_resolution_map,
    auto_tilt_to_center
)

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
tab1, tab2, tab3, tab4 = st.tabs(["📍 커버리지 맵", "🎯 3D 뷰", "📊 해상도 분석", "📋 상세 정보"])

with tab1:
    st.subheader("카메라 커버리지 & 해상도 시각화")

    # 그리드 해상도 설정
    grid_res = st.sidebar.slider("그리드 해상도 (mm)", 20, 100, 50, 10)

    # 두 개의 컬럼 생성 (좌측: 커버리지, 우측: 해상도)
    map_col1, map_col2 = st.columns(2)

    with map_col1:
        st.markdown("#### 커버리지 맵")

        # 커버리지 맵 생성
        fig = go.Figure()

        # 커버리지 그리드 계산
        X, Y, coverage = calculate_coverage_map(
            st.session_state.cameras if st.session_state.cameras else [],
            battery_width,
            battery_height,
            grid_resolution=grid_res
        )

        # Heatmap으로 커버리지 표시
        # 커스텀 컬러스케일: 0=회색, 1=빨강, 2=주황, 3=연두, 4+=초록
        custom_colorscale = [
            [0.0, '#404040'],    # 0: 회색
            [0.2, '#ff6464'],    # 1: 빨강
            [0.4, '#ffc832'],    # 2: 주황
            [0.6, '#64c864'],    # 3: 연두
            [0.8, '#329632'],    # 4: 초록
            [1.0, '#329632'],    # 4+: 초록
        ]

        fig.add_trace(go.Heatmap(
            x=np.arange(0, battery_width + grid_res, grid_res),
            y=np.arange(0, battery_height + grid_res, grid_res),
            z=coverage,
            colorscale=custom_colorscale,
            zmin=0,
            zmax=5,
            showscale=True,
            colorbar=dict(
                title="카메라 수",
                tickvals=[0, 1, 2, 3, 4],
                ticktext=["0", "1", "2", "3", "4+"],
                len=0.5,
            ),
            hovertemplate="위치: (%{x:.0f}, %{y:.0f})mm<br>카메라 수: %{z}<extra></extra>",
            xgap=1,
            ygap=1,
        ))

        # 배터리 외곽선
        fig.add_shape(
            type="rect",
            x0=0, y0=0,
            x1=battery_width, y1=battery_height,
            line=dict(color="white", width=3),
            fillcolor="rgba(0,0,0,0)",
        )

        # 각 카메라 footprint 및 위치 표시
        colors = px.colors.qualitative.Set1
        for i, cam in enumerate(st.session_state.cameras):
            color = colors[i % len(colors)]

            # 커버리지 영역 (다각형)
            polygon = cam.get_coverage_polygon()
            polygon_closed = np.vstack([polygon, polygon[0]])  # 닫힌 다각형

            # FOV 중심점 계산
            fov_center_x, fov_center_y = cam.pixel_to_world(
                (cam.spec.resolution_x - 1) / 2, (cam.spec.resolution_y - 1) / 2
            )

            fig.add_trace(go.Scatter(
                x=polygon_closed[:, 0],
                y=polygon_closed[:, 1],
                mode='lines',
                line=dict(color=color, width=2),
                name=f'CAM {cam.id} 영역',
                hoverinfo='skip'
            ))

            # FOV 중심점 표시
            fig.add_trace(go.Scatter(
                x=[fov_center_x],
                y=[fov_center_y],
                mode='markers',
                marker=dict(size=8, color=color, symbol='x'),
                name=f'CAM {cam.id} FOV중심',
                hovertemplate=f"FOV 중심: ({fov_center_x:.0f}, {fov_center_y:.0f})<extra></extra>"
            ))

            # 카메라 위치
            fig.add_trace(go.Scatter(
                x=[cam.x],
                y=[cam.y],
                mode='markers+text',
                marker=dict(size=15, color=color, symbol='diamond', line=dict(color='black', width=1)),
                text=[f"CAM{cam.id}"],
                textposition="top center",
                name=f'CAM {cam.id}',
                hovertemplate=f"<b>CAM {cam.id}</b><br>위치: ({cam.x:.0f}, {cam.y:.0f})mm<br>틸트: {cam.tilt_angle:.1f}°<br>방향: {cam.tilt_direction:.1f}°<extra></extra>"
            ))

            # 틸트 방향 화살표 (카메라 위치 → FOV 중심 방향)
            if cam.tilt_angle > 0:
                # FOV 중심 방향으로 화살표
                arrow_dx = fov_center_x - cam.x
                arrow_dy = fov_center_y - cam.y
                arrow_dist = np.sqrt(arrow_dx**2 + arrow_dy**2)
                if arrow_dist > 0:
                    # 화살표 길이 정규화 (최소 50, 최대 150)
                    arrow_len = min(150, max(50, arrow_dist * 0.3))
                    norm_dx = arrow_dx / arrow_dist * arrow_len
                    norm_dy = arrow_dy / arrow_dist * arrow_len
                    fig.add_annotation(
                        x=cam.x + norm_dx,
                        y=cam.y + norm_dy,
                        ax=cam.x,
                        ay=cam.y,
                        xref="x",
                        yref="y",
                        axref="x",
                        ayref="y",
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1.5,
                        arrowwidth=2,
                        arrowcolor=color
                    )

        # 여백 계산 (배터리 크기의 5%)
        margin_x = battery_width * 0.05
        margin_y = battery_height * 0.05

        fig.update_layout(
            xaxis=dict(
                title="X (mm)",
                range=[-margin_x, battery_width + margin_x],
                scaleanchor="y",
                scaleratio=1,
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(128,128,128,0.2)',
            ),
            yaxis=dict(
                title="Y (mm)",
                range=[-margin_y, battery_height + margin_y],
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(128,128,128,0.2)',
            ),
            height=600,
            showlegend=False,
            margin=dict(r=20, l=50, t=30, b=50),
            plot_bgcolor='rgba(40,40,40,1)'
        )

        st.plotly_chart(fig, use_container_width=True, key="coverage_chart")

    with map_col2:
        st.markdown("#### 해상도 맵")

        if not st.session_state.cameras:
            st.info("카메라를 배치하면 해상도 맵이 표시됩니다.")
        else:
            # 해상도 맵
            X_res, Y_res, resolution_map = calculate_resolution_map(
                st.session_state.cameras,
                battery_width,
                battery_height,
                grid_resolution=30
            )

            fig_res = go.Figure()

            fig_res.add_trace(go.Heatmap(
                x=X_res[0],
                y=Y_res[:, 0],
                z=resolution_map,
                colorscale='RdYlGn_r',  # 낮을수록 좋음 (초록)
                zmin=15,
                zmax=80,
                showscale=True,
                colorbar=dict(title="해상도<br>(mm/px)"),
                hovertemplate="위치: (%{x:.0f}, %{y:.0f})mm<br>해상도: %{z:.1f} mm/pixel<extra></extra>"
            ))

            # 배터리 외곽선
            fig_res.add_shape(
                type="rect",
                x0=0, y0=0,
                x1=battery_width, y1=battery_height,
                line=dict(color="black", width=2),
            )

            # 카메라 위치 표시
            for cam in st.session_state.cameras:
                fig_res.add_trace(go.Scatter(
                    x=[cam.x],
                    y=[cam.y],
                    mode='markers',
                    marker=dict(size=10, color='white', symbol='diamond', line=dict(color='black', width=2)),
                    showlegend=False,
                    hoverinfo='skip'
                ))

            fig_res.update_layout(
                xaxis=dict(
                    title="X (mm)",
                    range=[-margin_x, battery_width + margin_x],
                    scaleanchor="y",
                    scaleratio=1
                ),
                yaxis=dict(
                    title="Y (mm)",
                    range=[-margin_y, battery_height + margin_y]
                ),
                height=600,
                margin=dict(r=20, l=50, t=30, b=50),
            )

            st.plotly_chart(fig_res, use_container_width=True, key="resolution_chart_main")

            # 해상도 통계 표시
            valid_res = resolution_map[~np.isnan(resolution_map)]
            if len(valid_res) > 0:
                stat_col1, stat_col2, stat_col3 = st.columns(3)
                stat_col1.metric("최소 (최상)", f"{np.min(valid_res):.1f} mm/px")
                stat_col2.metric("평균", f"{np.mean(valid_res):.1f} mm/px")
                stat_col3.metric("최대 (최하)", f"{np.max(valid_res):.1f} mm/px")

    # 마우스 클릭 모드일 때 수동 좌표 입력
    if add_mode == "마우스 클릭":
        st.markdown("---")
        st.markdown("**클릭 위치에 카메라 추가** (그래프에서 좌표 확인 후 입력)")
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        click_x = col1.number_input("클릭 X", value=battery_width//2, min_value=0, max_value=int(battery_width), key="click_x")
        click_y = col2.number_input("클릭 Y", value=battery_height//2, min_value=0, max_value=int(battery_height), key="click_y")
        click_tilt = col3.number_input("틸트 (°)", value=0.0, min_value=0.0, max_value=85.0, key="click_tilt")

        if col4.button("➕ 추가", key="add_click"):
            cam = Camera(
                id=st.session_state.next_camera_id,
                x=click_x,
                y=click_y,
                z=working_distance,
                tilt_angle=click_tilt,
                spec=camera_spec
            )
            _, tilt_dir = auto_tilt_to_center(cam, battery_width, battery_height)
            cam.tilt_direction = tilt_dir
            st.session_state.cameras.append(cam)
            st.session_state.next_camera_id += 1
            st.rerun()

    # 카메라 목록 (카드형 UI)
    st.markdown("---")
    st.markdown(f"### 📷 카메라 목록 ({len(st.session_state.cameras)}개)")

    if st.session_state.cameras:
        # 카드당 4개씩 행으로 배치
        cameras_per_row = 4
        cameras_to_remove = []

        for row_start in range(0, len(st.session_state.cameras), cameras_per_row):
            row_cameras = st.session_state.cameras[row_start:row_start + cameras_per_row]
            cols = st.columns(cameras_per_row)

            for col_idx, cam in enumerate(row_cameras):
                with cols[col_idx]:
                    # 카드 컨테이너
                    colors = px.colors.qualitative.Set1
                    cam_color = colors[(row_start + col_idx) % len(colors)]

                    with st.container(border=True):
                        # 카메라 헤더
                        st.markdown(f"**CAM {cam.id}** <span style='color:{cam_color}'>●</span>", unsafe_allow_html=True)

                        # session_state 키에서 값 읽기 (없으면 카메라 값 사용)
                        key_x = f"card_x_{cam.id}"
                        key_y = f"card_y_{cam.id}"
                        key_tilt = f"card_tilt_{cam.id}"
                        key_dir = f"card_dir_{cam.id}"

                        # 위치 입력
                        c1, c2 = st.columns(2)
                        c1.number_input("X", value=float(cam.x), key=key_x,
                                       min_value=0.0, max_value=float(battery_width), step=10.0, format="%.0f")
                        c2.number_input("Y", value=float(cam.y), key=key_y,
                                       min_value=0.0, max_value=float(battery_height), step=10.0, format="%.0f")

                        # 틸트 입력
                        c3, c4 = st.columns(2)
                        c3.number_input("틸트°", value=float(cam.tilt_angle), key=key_tilt,
                                       min_value=0.0, max_value=85.0, step=5.0, format="%.0f")
                        c4.number_input("방향°", value=float(cam.tilt_direction), key=key_dir,
                                       min_value=-180.0, max_value=180.0, step=15.0, format="%.0f")

                        # session_state에서 값 읽어서 카메라 업데이트
                        if key_x in st.session_state:
                            cam.x = st.session_state[key_x]
                        if key_y in st.session_state:
                            cam.y = st.session_state[key_y]
                        if key_tilt in st.session_state:
                            cam.tilt_angle = st.session_state[key_tilt]
                        if key_dir in st.session_state:
                            cam.tilt_direction = st.session_state[key_dir]
                        cam.z = working_distance
                        cam.spec = camera_spec

                        # 삭제 버튼
                        if st.button("🗑️ 삭제", key=f"card_del_{cam.id}", use_container_width=True):
                            cameras_to_remove.append(row_start + col_idx)

        # 삭제 처리
        for idx in sorted(cameras_to_remove, reverse=True):
            st.session_state.cameras.pop(idx)
        if cameras_to_remove:
            st.rerun()

        # 전체 삭제 버튼
        if st.button("🗑️ 모든 카메라 삭제", key="delete_all_cameras"):
            st.session_state.cameras = []
            st.session_state.next_camera_id = 1
            st.rerun()

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
            # 해상도 맵 계산
            heatmap_res = 50  # 히트맵 그리드 해상도
            X_hm, Y_hm, res_map = calculate_resolution_map(
                st.session_state.cameras,
                battery_width, battery_height,
                grid_resolution=heatmap_res
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

        # 레이아웃 설정 - FOV가 배터리 면을 벗어나도 표시되도록 동적 범위 계산
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

        # 약간의 여백 추가
        margin_x = (x_max - x_min) * 0.1
        margin_y = (y_max - y_min) * 0.1
        x_min -= max(margin_x, 100)
        x_max += max(margin_x, 100)
        y_min -= max(margin_y, 100)
        y_max += max(margin_y, 100)

        fig_3d.update_layout(
            scene=dict(
                xaxis=dict(title='X (mm)', range=[x_min, x_max]),
                yaxis=dict(title='Y (mm)', range=[y_min, y_max]),
                zaxis=dict(title='Z (mm)', range=[-50, working_distance + 100]),
                aspectmode='data',
                bgcolor='rgb(30, 30, 30)'
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

with tab3:
    st.subheader("픽셀 해상도 분석")

    if not st.session_state.cameras:
        st.warning("카메라를 먼저 배치해주세요.")
    else:
        # 해상도 맵
        X, Y, resolution_map = calculate_resolution_map(
            st.session_state.cameras,
            battery_width,
            battery_height,
            grid_resolution=30
        )

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 전체 해상도 맵")
            fig_res = go.Figure()

            fig_res.add_trace(go.Heatmap(
                x=X[0],
                y=Y[:, 0],
                z=resolution_map,
                colorscale='RdYlGn_r',  # 낮을수록 좋음 (초록)
                zmin=15,
                zmax=80,
                showscale=True,
                colorbar=dict(title="해상도<br>(mm/pixel)"),
                hovertemplate="위치: (%{x:.0f}, %{y:.0f})mm<br>해상도: %{z:.1f} mm/pixel<extra></extra>"
            ))

            # 배터리 외곽선
            fig_res.add_shape(
                type="rect",
                x0=0, y0=0,
                x1=battery_width, y1=battery_height,
                line=dict(color="black", width=2),
            )

            # 카메라 위치 표시
            for cam in st.session_state.cameras:
                fig_res.add_trace(go.Scatter(
                    x=[cam.x],
                    y=[cam.y],
                    mode='markers',
                    marker=dict(size=10, color='white', symbol='diamond', line=dict(color='black', width=2)),
                    showlegend=False,
                    hoverinfo='skip'
                ))

            fig_res.update_layout(
                xaxis=dict(title="X (mm)", scaleanchor="y", scaleratio=1),
                yaxis=dict(title="Y (mm)"),
                height=500,
            )

            st.plotly_chart(fig_res, use_container_width=True)

        with col2:
            st.markdown("#### 카메라별 픽셀 해상도")

            # 각 카메라의 픽셀별 해상도 그래프
            selected_cam = st.selectbox(
                "카메라 선택",
                options=range(len(st.session_state.cameras)),
                format_func=lambda i: f"CAM {st.session_state.cameras[i].id}"
            )

            cam = st.session_state.cameras[selected_cam]

            # 픽셀별 해상도 계산 (배터리 영역 내 픽셀만)
            res_grid = np.zeros((cam.spec.resolution_x - 1, cam.spec.resolution_y - 1))
            for px in range(cam.spec.resolution_x - 1):
                for py in range(cam.spec.resolution_y - 1):
                    # 픽셀 위치가 배터리 영역 내인지 확인
                    world_x, world_y = cam.pixel_to_world(px + 0.5, py + 0.5)
                    if world_x is None or not (0 <= world_x <= battery_width and 0 <= world_y <= battery_height):
                        res_grid[px, py] = np.nan
                        continue

                    res_x, res_y = cam.calculate_pixel_resolution(px, py)
                    res_grid[px, py] = (res_x + res_y) / 2 if res_x != float('inf') else np.nan

            fig_cam_res = go.Figure()
            fig_cam_res.add_trace(go.Heatmap(
                z=res_grid.T,  # transpose for correct orientation
                colorscale='RdYlGn_r',
                showscale=True,
                colorbar=dict(title="mm/pixel"),
                hovertemplate="픽셀 (%{x}, %{y})<br>해상도: %{z:.1f} mm/pixel<extra></extra>"
            ))

            fig_cam_res.update_layout(
                title=f"CAM {cam.id} 픽셀별 해상도",
                xaxis=dict(title="픽셀 X (0-31)"),
                yaxis=dict(title="픽셀 Y (0-23)"),
                height=400,
            )

            st.plotly_chart(fig_cam_res, use_container_width=True)

            # 해상도 통계
            valid_res = res_grid[~np.isnan(res_grid)]
            if len(valid_res) > 0:
                st.markdown("##### 해상도 통계")
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("최소 (최상)", f"{np.min(valid_res):.1f} mm/px")
                col_b.metric("평균", f"{np.mean(valid_res):.1f} mm/px")
                col_c.metric("최대 (최하)", f"{np.max(valid_res):.1f} mm/px")

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
