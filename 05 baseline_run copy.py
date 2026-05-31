# -*- coding: mbcs -*- 
import os
import shutil
import math
from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import mesh
import traceback 

# === 配置区域 ===
sat_path = r'C:\Users\Admin\Desktop\polyframe\baseline_model.sat'
job_output_folder = r'C:\Users\Admin\Desktop\polyframe\baseline_output'

if not os.path.exists(job_output_folder):
    os.makedirs(job_output_folder)

executeOnCaeStartup()

print(">>> 开始处理多位置阵列主次梁配筋仿真模型（边界缩进及结果输出修正版）...")

filename = os.path.basename(sat_path)
raw_name = os.path.splitext(filename)[0]
safe_base_name = 'job_' + ''.join([c if c.isalnum() else '_' for c in raw_name])
model_name = 'Model_Rebar_Simulation'
job_name = safe_base_name + '_Full_Results'
part_name = safe_base_name

try:
    if model_name in mdb.models:
        del mdb.models[model_name]
    
    model = mdb.Model(name=model_name)
    
    # --- 1. 几何导入 (混凝土基体 Part) ---
    acis = mdb.openAcis(sat_path, scaleFromFile=OFF)
    model.PartFromGeometryFile(name=part_name, geometryFile=acis, combine=False,
                               dimensionality=THREE_D, type=DEFORMABLE_BODY)
    p_conc = model.parts[part_name]
    
    # --- 2. 材料与截面定义 ---
    model.Material(name='Concrete_Mat')
    model.materials['Concrete_Mat'].Density(table=((2400.0,),))
    model.materials['Concrete_Mat'].Elastic(table=((30000000000.0, 0.2),))
    model.HomogeneousSolidSection(name='Conc_Section', material='Concrete_Mat', thickness=None)
    
    region_conc = p_conc.Set(cells=p_conc.cells, name='Conc_All_Set')
    p_conc.SectionAssignment(region=region_conc, sectionName='Conc_Section', offset=0.0,
                             offsetType=MIDDLE_SURFACE, offsetField='', thicknessAssignment=FROM_SECTION)
    
    model.Material(name='Steel_Mat')
    model.materials['Steel_Mat'].Density(table=((7850.0,),))
    model.materials['Steel_Mat'].Elastic(table=((200000000000.0, 0.3),))
    
    # 截面面积
    area_d25 = math.pi * (0.025 / 2.0)**2  
    area_d20 = math.pi * (0.020 / 2.0)**2  
    area_d12 = math.pi * (0.012 / 2.0)**2  
    area_d22 = math.pi * (0.022 / 2.0)**2  
    area_d10 = math.pi * (0.010 / 2.0)**2  
    area_d8  = math.pi * (0.008 / 2.0)**2  
    
    model.TrussSection(name='Sec_Rebar_BeamM_Main', material='Steel_Mat', area=area_d25)
    model.TrussSection(name='Sec_Rebar_BeamM_Stirrup', material='Steel_Mat', area=area_d10)
    model.TrussSection(name='Sec_Rebar_BeamS_Main', material='Steel_Mat', area=area_d20)
    model.TrussSection(name='Sec_Rebar_BeamS_Stirrup', material='Steel_Mat', area=area_d8)
    model.TrussSection(name='Sec_Rebar_Slab', material='Steel_Mat', area=area_d12)
    model.TrussSection(name='Sec_Rebar_Col_Main', material='Steel_Mat', area=area_d22)
    model.TrussSection(name='Sec_Rebar_Col_Stirrup', material='Steel_Mat', area=area_d10)
    
    # --- 3. 纯网格钢筋 Part 生成 ---
    print(">>> 正在底层直接生成全网格整体钢筋骨架（全阵列配置）...")
    p_rebar = model.Part(name='Rebar_Skeleton_Part', dimensionality=THREE_D, type=DEFORMABLE_BODY)
    
    s_coord = [-3.8, 3.8] 
    mesh_div = 20 
    
    # 3.1 楼板双层双向钢筋网
    start_slab_idx = len(p_rebar.elements)
    slab_z_layers = [4.040, 4.120]
    for z in slab_z_layers:
        y = s_coord[0]
        while y <= s_coord[1]:
            prev_node = None
            for i in range(mesh_div + 1):
                x = s_coord[0] + i * (s_coord[1] - s_coord[0]) / mesh_div
                n = p_rebar.Node(coordinates=(x, y, z))
                if prev_node:
                    p_rebar.Element(nodes=(prev_node, n), elemShape=LINE2)
                prev_node = n
            y += 0.2
        x = s_coord[0]
        while x <= s_coord[1]:
            prev_node = None
            for i in range(mesh_div + 1):
                y = s_coord[0] + i * (s_coord[1] - s_coord[0]) / mesh_div
                n = p_rebar.Node(coordinates=(x, y, z))
                if prev_node:
                    p_rebar.Element(nodes=(prev_node, n), elemShape=LINE2)
                prev_node = n
            x += 0.2
    end_slab_idx = len(p_rebar.elements)
    slab_elements = [p_rebar.elements[i] for i in range(start_slab_idx, end_slab_idx)]

    # 3.2 柱子配筋
    col_min, col_max = -0.3, 0.3
    cover_col = 0.04 
    rebar_cx = [col_min + cover_col, col_max - cover_col]
    rebar_cy = [col_min + cover_col, col_max - cover_col]
    z_max = 4.140
    
    start_col_m_idx = len(p_rebar.elements)
    for cx in rebar_cx:
        for cy in rebar_cy:
            prev_node = None
            for i in range(mesh_div + 1):
                cz = i * z_max / mesh_div
                n = p_rebar.Node(coordinates=(cx, cy, cz))
                if prev_node:
                    p_rebar.Element(nodes=(prev_node, n), elemShape=LINE2)
                prev_node = n
    end_col_m_idx = len(p_rebar.elements)
    col_main_elements = [p_rebar.elements[i] for i in range(start_col_m_idx, end_col_m_idx)]

    start_col_s_idx = len(p_rebar.elements)
    sz = 0.1
    while sz < z_max - 0.1:
        corners = [(rebar_cx[0], rebar_cy[0], sz), (rebar_cx[1], rebar_cy[0], sz),
                   (rebar_cx[1], rebar_cy[1], sz), (rebar_cx[0], rebar_cy[1], sz)]
        c_nodes = [p_rebar.Node(coordinates=pt) for pt in corners]
        for i in range(4):
            p_rebar.Element(nodes=(c_nodes[i], c_nodes[(i+1)%4]), elemShape=LINE2)
        sz += 0.15
    end_col_s_idx = len(p_rebar.elements)
    col_stirrup_elements = [p_rebar.elements[i] for i in range(start_col_s_idx, end_col_s_idx)]

    # 3.3 主梁配筋
    bm_width, bm_height = 0.5, 0.8
    cover_bm = 0.04
    start_bm_main = len(p_rebar.elements)
    
    bm_y = [-bm_width/2 + cover_bm, bm_width/2 - cover_bm]
    bm_z = [4.140 - bm_height + cover_bm, 4.140 - cover_bm]
    for by in bm_y:
        for bz in bm_z:
            prev_node = None
            for i in range(mesh_div + 1):
                bx = s_coord[0] + i * (s_coord[1] - s_coord[0]) / mesh_div
                n = p_rebar.Node(coordinates=(bx, by, bz))
                if prev_node:
                    p_rebar.Element(nodes=(prev_node, n), elemShape=LINE2)
                prev_node = n
    bx_step = s_coord[0] + 0.1
    while bx_step < s_coord[1] - 0.1:
        corners = [(bx_step, bm_y[0], bm_z[0]), (bx_step, bm_y[1], bm_z[0]),
                   (bx_step, bm_y[1], bm_z[1]), (bx_step, bm_y[0], bm_z[1])]
        b_nodes = [p_rebar.Node(coordinates=pt) for pt in corners]
        for i in range(4):
            p_rebar.Element(nodes=(b_nodes[i], b_nodes[(i+1)%4]), elemShape=LINE2)
        bx_step += 0.15

    bm_x_new = [-bm_width/2 + cover_bm, bm_width/2 - cover_bm]
    for bx in bm_x_new:
        for bz in bm_z:
            prev_node = None
            for i in range(mesh_div + 1):
                by = s_coord[0] + i * (s_coord[1] - s_coord[0]) / mesh_div
                n = p_rebar.Node(coordinates=(bx, by, bz))
                if prev_node:
                    p_rebar.Element(nodes=(prev_node, n), elemShape=LINE2)
                prev_node = n
    by_step = s_coord[0] + 0.1
    while by_step < s_coord[1] - 0.1:
        corners = [(bm_x_new[0], by_step, bm_z[0]), (bm_x_new[1], by_step, bm_z[0]),
                   (bm_x_new[1], by_step, bz_z if 'bz_z' in locals() else bm_z[1]), (bm_x_new[0], by_step, bm_z[1])]
        b_nodes = [p_rebar.Node(coordinates=pt) for pt in corners]
        for i in range(4):
            p_rebar.Element(nodes=(b_nodes[i], b_nodes[(i+1)%4]), elemShape=LINE2)
        by_step += 0.15

    end_bm_all = len(p_rebar.elements)
    bm_elements = [p_rebar.elements[i] for i in range(start_bm_main, end_bm_all)]
    bm_main_elements = [el for el in bm_elements if el.getNodes()[0].coordinates[2] in bm_z]
    bm_stirrup_elements = [el for el in bm_elements if el not in bm_main_elements]

    # 3.4 次梁多位置配筋 (引入边界向内微调 0.02m 的安全策略)
    bs_width, bs_height = 0.3, 0.55
    cover_bs = 0.03
    bs_z = [4.140 - bs_height + cover_bs, 4.140 - cover_bs]
    
    start_bs_all = len(p_rebar.elements)

    # 3.4.1 纵向次梁：X = ±4.0 处（向内安全缩进 0.02m）
    for bs_x_center in [-4.0, 4.0]:
        if bs_x_center == 4.0:
            # 基础中心向内微调至 3.98
            c_x = 3.98
            bs_x = [c_x - bs_width/2 + cover_bs, c_x] 
        else:
            # 基础中心向内微调至 -3.98
            c_x = -3.98
            bs_x = [c_x, c_x + bs_width/2 - cover_bs] 
            
        for bx in bs_x:
            for bz in bs_z:
                prev_node = None
                for i in range(mesh_div + 1):
                    by = s_coord[0] + i * (s_coord[1] - s_coord[0]) / mesh_div
                    n = p_rebar.Node(coordinates=(bx, by, bz))
                    if prev_node:
                        p_rebar.Element(nodes=(prev_node, n), elemShape=LINE2)
                    prev_node = n
        by_step = s_coord[0] + 0.1
        while by_step < s_coord[1] - 0.1:
            corners = [(bs_x[0], by_step, bs_z[0]), (bs_x[1], by_step, bs_z[0]),
                       (bs_x[1], by_step, bs_z[1]), (bs_x[0], by_step, bs_z[1])]
            bs_nodes = [p_rebar.Node(coordinates=pt) for pt in corners]
            for i in range(4):
                p_rebar.Element(nodes=(bs_nodes[i], bs_nodes[(i+1)%4]), elemShape=LINE2)
            by_step += 0.20

    # 3.4.2 横向次梁：Y = ±4.0 处（向内安全缩进 0.02m）
    for bs_y_center in [-4.0, 4.0]:
        if bs_y_center == 4.0:
            c_y = 3.98
            bs_y = [c_y - bs_width/2 + cover_bs, c_y]
        else:
            c_y = -3.98
            bs_y = [c_y, c_y + bs_width/2 - cover_bs]
            
        for by in bs_y:
            for bz in bs_z:
                prev_node = None
                for i in range(mesh_div + 1):
                    bx = s_coord[0] + i * (s_coord[1] - s_coord[0]) / mesh_div
                    n = p_rebar.Node(coordinates=(bx, by, bz))
                    if prev_node:
                        p_rebar.Element(nodes=(prev_node, n), elemShape=LINE2)
                    prev_node = n
        bx_step = s_coord[0] + 0.1
        while bx_step < s_coord[1] - 0.1:
            corners = [(bx_step, bs_y[0], bs_z[0]), (bx_step, bs_y[1], bs_z[0]),
                       (bx_step, bs_y[1], bs_z[1]), (bx_step, bs_y[0], bs_z[1])]
            bs_nodes = [p_rebar.Node(coordinates=pt) for pt in corners]
            for i in range(4):
                p_rebar.Element(nodes=(bs_nodes[i], bs_nodes[(i+1)%4]), elemShape=LINE2)
            bx_step += 0.20

    end_bs_all = len(p_rebar.elements)
    bs_elements = [p_rebar.elements[i] for i in range(start_bs_all, end_bs_all)]
    bs_main_elements = [el for el in bs_elements if el.getNodes()[0].coordinates[2] in bs_z]
    bs_stirrup_elements = [el for el in bs_elements if el not in bs_main_elements]

    # 3.5 属性赋予
    print(">>> 正在为纯网格钢筋元素分配对应的截面和钢种...")
    if slab_elements:
        p_rebar.SectionAssignment(region=p_rebar.Set(elements=mesh.MeshElementArray(slab_elements), name='Set_Slab_Mesh'), sectionName='Sec_Rebar_Slab')
    if col_main_elements:
        p_rebar.SectionAssignment(region=p_rebar.Set(elements=mesh.MeshElementArray(col_main_elements), name='Set_Col_Main_Mesh'), sectionName='Sec_Rebar_Col_Main')
    if col_stirrup_elements:
        p_rebar.SectionAssignment(region=p_rebar.Set(elements=mesh.MeshElementArray(col_stirrup_elements), name='Set_Col_Stirrup_Mesh'), sectionName='Sec_Rebar_Col_Stirrup')
    if bm_main_elements:
        p_rebar.SectionAssignment(region=p_rebar.Set(elements=mesh.MeshElementArray(bm_main_elements), name='Set_BeamM_Main_Mesh'), sectionName='Sec_Rebar_BeamM_Main')
    if bm_stirrup_elements:
        p_rebar.SectionAssignment(region=p_rebar.Set(elements=mesh.MeshElementArray(bm_stirrup_elements), name='Set_BeamM_Stirrup_Mesh'), sectionName='Sec_Rebar_BeamM_Stirrup')
    if bs_main_elements:
        p_rebar.SectionAssignment(region=p_rebar.Set(elements=mesh.MeshElementArray(bs_main_elements), name='Set_BeamS_Main_Mesh'), sectionName='Sec_Rebar_BeamS_Main')
    if bs_stirrup_elements:
        p_rebar.SectionAssignment(region=p_rebar.Set(elements=mesh.MeshElementArray(bs_stirrup_elements), name='Set_BeamS_Stirrup_Mesh'), sectionName='Sec_Rebar_BeamS_Stirrup')

    p_rebar.setElementType(regions=(p_rebar.elements,), elemTypes=(mesh.ElemType(elemCode=T3D2, elemLibrary=STANDARD),))

    # --- 4. 装配与内置约束 ---
    print(">>> 组装并建立整体内置区域约束关系...")
    a = model.rootAssembly
    a.DatumCsysByDefault(CARTESIAN)
    
    inst_conc = a.Instance(name='Concrete_Inst', part=p_conc, dependent=ON)
    inst_rebar = a.Instance(name='Rebar_Inst', part=p_rebar, dependent=ON)
    
    rebar_master_set = a.Set(elements=inst_rebar.elements, name='All_Rebars_Mesh_Set')
    host_concrete_set = a.Set(cells=inst_conc.cells, name='Host_Concrete_Set')
    
    model.EmbeddedRegion(name='Constraint-Rebar-Embedded', embeddedRegion=rebar_master_set, hostRegion=host_concrete_set)

    # --- 5. 分析步与核心结果输出修正 ---
    model.StaticStep(name='Step-1', previous='Initial')
    
    # 核心修复点：强力确保场输出对象请求了 S 和 U 变量
    for key in model.fieldOutputRequests.keys():
        model.fieldOutputRequests[key].setValues(variables=('S', 'PE', 'PEEQ', 'U', 'IVOL'))
    
    # --- 6. 载荷与边界条件 ---
    model.Gravity(name='gravity', createStepName='Step-1', comp3=-9.81)
    
    faces_z0 = inst_conc.faces.getByBoundingBox(zMin=-0.01, zMax=0.01)
    model.EncastreBC(name='BC-Encastre', createStepName='Step-1', region=a.Set(faces=faces_z0, name='Set-Encastre'))
    
    faces_xsymm = inst_conc.faces.getByBoundingBox(xMin=-4.01, xMax=-3.99) + \
                  inst_conc.faces.getByBoundingBox(xMin=3.99, xMax=4.01)
    if faces_xsymm:
        model.XsymmBC(name='BC-Xsymm', createStepName='Step-1', region=a.Set(faces=faces_xsymm, name='Set-Xsymm'))
                  
    faces_ysymm = inst_conc.faces.getByBoundingBox(yMin=-4.01, yMax=-3.99) + \
                  inst_conc.faces.getByBoundingBox(yMin=3.99, yMax=4.01)
    if faces_ysymm:
        model.YsymmBC(name='BC-Ysymm', createStepName='Step-1', region=a.Set(faces=faces_ysymm, name='Set-Ysymm'))
    
    faces_load = inst_conc.faces.getByBoundingBox(zMin=4.139, zMax=4.141)
    if faces_load:
        surf = a.Surface(side1Faces=faces_load, name='Surf-Load')
        model.Pressure(name='Load-Top', createStepName='Step-1', region=surf, magnitude=6000.0, distributionType=UNIFORM)
        
    # --- 7. 网格划分 ---
    print(">>> 正在为混凝土基体划分网格...")
    p_conc.setMeshControls(regions=p_conc.cells, elemShape=TET, technique=FREE)
    p_conc.setElementType(regions=(p_conc.cells,), 
                          elemTypes=(mesh.ElemType(elemCode=C3D20R), mesh.ElemType(elemCode=C3D15), mesh.ElemType(elemCode=C3D10)))
    p_conc.seedPart(size=0.2, deviationFactor=0.1, minSizeFactor=0.1)
    p_conc.generateMesh()
    
    a.regenerate()
    
    # --- 8. 提交作业 ---
    print(">>> 正在提交全结构结果修正分析作业...")
    job = mdb.Job(name=job_name, model=model_name, resultsFormat=ODB)
    job.submit(consistencyChecking=OFF)
    job.waitForCompletion()
    
    # 诊断打印：检查作业最终是否成功
    if job.status == COMPLETED:
        print(">>> 作业完美计算成功！")
    else:
        print(f">>> 作业计算状态异常: {job.status}。请前往工作目录检查 .log 或 .msg 文件！")
    
    odb_name = job_name + '.odb'
    default_odb_path = os.path.join(os.getcwd(), odb_name)
    final_odb_path = os.path.join(job_output_folder, odb_name)
    
    if os.path.exists(default_odb_path):
        shutil.move(default_odb_path, final_odb_path)
        print(f'>>> 全结构结果修正仿真通过！有效结果已转至: {final_odb_path}')
        
except Exception as e:
    print(f">>> 建模流程由于异常中断，原因：{e}")
    traceback.print_exc()

print("=== 全流程运行结束 ===")