# -*- coding: mbcs -*- 
import os
import time
import shutil
from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import regionToolset
import mesh
import traceback 

# === 配置区域 ===
sat_folder = r'D:\code202410\Skeleton_Concrete_Slab\04_formal\A-S\A-S_sat'
job_output_folder = r'D:\code202410\Skeleton_Concrete_Slab\04_formal\A-S\A-S_odb_ture'
record_file = os.path.join(job_output_folder, 'last_index.txt')

batch_size = 65

if not os.path.exists(job_output_folder):
    os.makedirs(job_output_folder)

start_time = time.time()
executeOnCaeStartup()

sat_files = sorted([f for f in os.listdir(sat_folder) if f.endswith('.sat')])

if os.path.exists(record_file):
    with open(record_file, 'r') as f:
        start_index = int(f.read().strip())
else:
    start_index = 0

end_index = min(start_index + batch_size, len(sat_files))
print(f">>> 本次运行处理文件：{start_index} 到 {end_index - 1}")

for i in range(start_index, end_index):
    filename = sat_files[i]
    raw_name = os.path.splitext(filename)[0]
    safe_base_name = 'job_' + ''.join([c if c.isalnum() else '_' for c in raw_name])
    model_name = 'Model_' + safe_base_name
    job_name = safe_base_name
    part_name = safe_base_name
    sat_path = os.path.join(sat_folder, filename)
    
    try:
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
        
        # 【新增】强制请求 IVOL 输出，以便后处理脚本计算体积权重指标
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
        
        # 载荷面 (统一修正为 6000 Pa = 6.0 kN/m2)
        faces_load = inst.faces.getByBoundingBox(zMin=4.300, zMax=4.350)
        if faces_load:
            surf = a.Surface(side1Faces=faces_load, name='Surf-Load')
            model.Pressure(
                name='Load-Top',
                createStepName='Step-1',
                region=surf,
                magnitude=6000.0, # 已修正：恒载3.0 + 活载3.0
                distributionType=UNIFORM
            )
            
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
            print(f'>>> 处理完成: {filename}')
            
    except Exception as e:
        print(f">>> 跳过文件 [{i}] {filename}，原因：{e}")
        if model_name in mdb.models:
            del mdb.models[model_name]
        continue

with open(record_file, 'w') as f:
    f.write(str(end_index))

print("=== 批次处理结束 ===")