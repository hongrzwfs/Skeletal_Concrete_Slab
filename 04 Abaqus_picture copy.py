# -*- coding: utf-8 -*-
from abaqus import *
from abaqusConstants import *
import visualization
import os

# ==========================================
# 1. 路径与全局配置
# ==========================================
WORK_DIR = r"D:\code202410\Skeleton_Concrete_Slab\04_formal\A_2\A_2_odb_new"
OUTPUT_DIR = os.path.join(WORK_DIR, "image")

# ==========================================
# 2. 视觉显示控制逻辑
# ==========================================
DEBUG_MODE = False  # 已关闭调试，进行全量处理
VIEWPORT_VIEW = 'Top' 
DEFORM_MODE = UNIFORM
DEFORM_FACTOR = 1.0 

# ==========================================
# 主程序逻辑
# ==========================================
def process_odbs_final_v3():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    odb_files = [f for f in os.listdir(WORK_DIR) if f.endswith('.odb')]
    if not odb_files: 
        print("No ODB files found.")
        return
    vpName = session.currentViewportName
    vp = session.viewports[vpName]
    # --- 1. 背景与全局设置 ---
    session.graphicsOptions.setValues(backgroundStyle=SOLID, backgroundColor='#FFFFFF')
    session.printOptions.setValues(vpDecorations=OFF, vpBackground=ON, rendition=COLOR)
    # --- 2. 修正图注位置与隐藏冗余信息 ---
    # legendPosition: (x, y) 坐标，范围 0-100。原点在左下角。
    # (80, 15) 大约在右下角位置
    vp.viewportAnnotationOptions.setValues(
        legend=ON,
        legendPosition=(80, 45), 
        state=OFF,   # 修正点：stateInfo 改为 state
        title=OFF,   # 修正点：titleBlock 改为 title
        compass=OFF  # 关闭坐标轴指南针
    )
    for idx, file_name in enumerate(odb_files):
        odb_path = os.path.join(WORK_DIR, file_name)
        base_name = os.path.splitext(file_name)[0]
        image_path = os.path.join(OUTPUT_DIR, base_name) 
        try:
            # 打开 ODB
            odb = session.openOdb(name=odb_path, readOnly=True)
            vp.setValues(displayedObject=odb)
            # 云图与变量设置
            vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF, ))
            vp.odbDisplay.setPrimaryVariable(
                variableLabel='S', outputPosition=INTEGRATION_POINT, 
                refinement=(INVARIANT, 'Mises')
            )
            # 变形缩放
            vp.odbDisplay.commonOptions.setValues(
                deformationScaling=DEFORM_MODE, 
                uniformScaleFactor=DEFORM_FACTOR
            )
            # 视角调整 (Top + Y轴旋转180度)
            if isinstance(VIEWPORT_VIEW, str) and VIEWPORT_VIEW in session.views.keys():
                vp.view.setValues(session.views[VIEWPORT_VIEW])
                vp.view.rotate(xAngle=0, yAngle=180, zAngle=0)
            vp.view.fitView()
            # 导出图片
            session.printToFile(fileName=image_path, format=PNG, canvasObjects=(vp,))
            odb.close()
            print("[{}/{}] Success: {}".format(idx + 1, len(odb_files), base_name))
        except Exception as e:
            print("[{}/{}] ERROR: {} - {}".format(idx + 1, len(odb_files), file_name, str(e)))

if __name__ == "__main__":
    process_odbs_final_v3()
    print("-" * 30)
    print("Batch processing completed. Check: {}".format(OUTPUT_DIR))