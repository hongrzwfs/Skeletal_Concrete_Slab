# -*- coding: mbcs -*- 
import os
import time
import shutil
import csv   # 新增：用于读取CSV文件
import re    # 新增：用于解析文件名中的参数
from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import regionToolset
import mesh
import traceback 

# === 配置区域 ===
# 1. 更新后的 sat 文件目录
sat_folder = r'D:\code202410\Skeletal_Concrete_Slab\data_base\A-S\A-S_sat'
# 新增：CSV 文件路径
csv_path = r'D:\code202410\Skeletal_Concrete_Slab\data_base\A-S\model_volume.csv'

job_output_folder = r'D:\code202410\Skeletal_Concrete_Slab\data_base\A-S\A-S_odb'
record_file = os.path.join(job_output_folder, 'last_index.txt')

batch_size = 1000

if not os.path.exists(job_output_folder):
    os.makedirs(job_output_folder)

# --- 新增：预先读取 CSV 文件并建立 H2 索引字典 ---
h2_dict = {}
if os.path.exists(csv_path):
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # 将 A, B, C, D 转为 float 作为键，消除字符串格式差异（如 0.00 和 0）
                key = (float(row['A']), float(row['B']), float(row['C']), float(row['D']))
                h2_dict[key] = float(row['H2'])
            except (ValueError, KeyError):
                continue
    print(">>> 成功加载 csv 数据，共记录 {} 条参数组合。".format(len(h2_dict)))
else:
    print(">>> 警告：未找到 csv 文件 {}，程序可能无法正常获取 H2!".format(csv_path))

start_time = time.time()
executeOnCaeStartup()

sat_files = sorted([f for f in os.listdir(sat_folder) if f.endswith('.sat')])

if os.path.exists(record_file):
    with open(record_file, 'r') as f:
        start_index = int(f.read().strip())
else:
    start_index = 0

end_index = min(start_index + batch_size, len(sat_files))
print(f">>>> 本次运行处理文件：{start_index} 到 {end_index - 1}")

for i in range(start_index, end_index):
    filename = sat_files[i]
    raw_name = os.path.splitext(filename)[0]
    safe_base_name = 'job_' + ''.join([c if c.isalnum() else '_' for c in raw_name])
    model_name = 'Model_' + safe_base_name
    job_name = safe_base_name
    part_name = safe_base_name
    sat_path = os.path.join(sat_folder, filename)
    
    try:
        # --- 2. 解析文件名提取 A, B, C, D 并匹配 H2 ---
        match = re.match(r'A([\d\.\-]+)_B([\d\.\-]+)_C([\d\.\-]+)_D([\d\.\-]+)', raw_name)
        if not match:
            raise ValueError(f"文件名格式不匹配，无法解析参数: {filename}")
        
        a_val = float(match.group(1))
        b_val = float(match.group(2))
        c_val = float(match.group(3))
        d_val = float(match.group(4))
        current_key = (a_val, b_val, c_val, d_val)
        
        if current_key not in h2_dict:
            raise ValueError(f"在 CSV 中未找到对应的参数组合: {current_key}")
            
        h2_val = h2_dict[current_key]
        
        # 取前三位小数并设定适当的上下容差（这里给定上下 0.02 范围，可根据具体几何微调）
        h2_rounded = round(h2_val, 3)
        z_min_dynamic = h2_rounded - 0.02
        z_max_dynamic = h2_rounded + 0.02
        
        # ----------------------------------------------
        
        if model_name in mdb.models:
            del mdb.models[model_name]
        
        model = mdb.Model(name=model_name)
        acis = mdb.openAcis(sat_path, scaleFromFile=OFF)
        model.PartFromGeometryFile(name=part_name, geometryFile=acis, combine=False,
                                   dimensionality=THREE_D, type=DEFORMABLE_BODY)
        
        p = model.parts[part_name]
        model.Material(name='concrete')
        model.materials['concrete'].Density(table=((2500.0,),))
        model.materials['concrete'].Elastic(table=((30000000000.0, 0.2),))
        model.HomogeneousSolidSection(name='Section-1', material='concrete', thickness=None)
        
        region = p.Set(cells=p.cells, name='Set-1')
        p.SectionAssignment(region=region, sectionName='Section-1', offset=0.0,
                            offsetType=MIDDLE_SURFACE, offsetField='', thicknessAssignment=FROM_SECTION)
        
        a = model.rootAssembly
        a.DatumCsysByDefault(CARTESIAN)
        a.Instance(name=part_name, part=p, dependent=ON)
        
        # --- 定义分析步 ---
        model.StaticStep(name='Step-1', previous='Initial')
        
        # 强制请求 IVOL 输出，以便后处理脚本计算体积权重指标
        model.fieldOutputRequests['F-Output-1'].setValues(variables=('S', 'U', 'IVOL'))
        
        model.Gravity(name='gravity', createStepName='Step-1', comp3=-9.81)
        inst = a.instances[part_name]
        
        # 固定面
        faces_z0 = inst.faces.getByBoundingBox(zMin=-0.01, zMax=0.01)
        model.EncastreBC(name='BC-Encastre', createStepName='Step-1',
                         region=a.Set(faces=faces_z0, name='Set-Encastre'))
        
        # 对称面 (8.0m 跨度，中心对称)
        faces_xsymm = inst.faces.getByBoundingBox(xMin=-4.01, xMax=-3.99) + \
                      inst.faces.getByBoundingBox(xMin=3.99, xMax=4.01)
        model.XsymmBC(name='BC-Xsymm', createStepName='Step-1',
                      region=a.Set(faces=faces_xsymm, name='Set-Xsymm'))
                      
        faces_ysymm = inst.faces.getByBoundingBox(yMin=-4.01, yMax=-3.99) + \
                      inst.faces.getByBoundingBox(yMin=3.99, yMax=4.01)
        model.YsymmBC(name='BC-Ysymm', createStepName='Step-1',
                      region=a.Set(faces=faces_ysymm, name='Set-Ysymm'))
        
        # 载荷面 —— 修改为从 CSV 动态获取的高度和容差范围
        faces_load = inst.faces.getByBoundingBox(zMin=z_min_dynamic, zMax=z_max_dynamic)
        if faces_load:
            surf = a.Surface(side1Faces=faces_load, name='Surf-Load')
            model.Pressure(
                name='Load-Top',
                createStepName='Step-1',
                region=surf,
                magnitude=6000.0, # 已修正：恒载3.0 + 活载3.0
                distributionType=UNIFORM
            )
        else:
            print(f">>> 警告：文件 {filename} 未识别到高度在 [{z_min_dynamic}, {z_max_dynamic}] 范围内的载荷面！")
            
        # --- 网格划分 ---
        a.makeIndependent(instances=(inst,))
        pickedRegions = inst.cells
        a.setMeshControls(regions=pickedRegions, elemShape=TET, technique=FREE)
        a.setElementType(
            regions=(pickedRegions,),
            elemTypes=(mesh.ElemType(elemCode=C3D20R),
                       mesh.ElemType(elemCode=C3D15),
                       mesh.ElemType(elemCode=C3D10))
        )
        a.seedPartInstance(regions=(inst,), size=0.2, deviationFactor=0.1, minSizeFactor=0.1)
        a.generateMesh(regions=(inst,))
        
        # --- 提交作业 ---
        job = mdb.Job(name=job_name, model=model_name, resultsFormat=ODB)
        job.submit(consistencyChecking=OFF)
        job.waitForCompletion()
        
        # --- 移动 ODB ---
        odb_name = job_name + '.odb'
        default_odb_path = os.path.join(os.getcwd(), odb_name)
        final_odb_path = os.path.join(job_output_folder, odb_name)
        if os.path.exists(default_odb_path):
            shutil.move(default_odb_path, final_odb_path)
            print(f'>>> 处理完成: {filename} (H2={h2_rounded})')
            
    except Exception as e:
        print(f">>> 跳过文件 [{i}] {filename}，原因：{e}")
        # traceback.print_exc() # 如果调试时想看具体哪行报错，可以取消本行注释
        if model_name in mdb.models:
            del mdb.models[model_name]
        continue

with open(record_file, 'w') as f:
    f.write(str(end_index))

print("=== 批次处理结束 ===")