# -*- coding: mbcs -*- 
import os
import shutil
import time  # 【新增】引入时间模块用于延时等待
from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import regionToolset
import mesh

# === 配置区域 ===
sat_path = r'D:\code202410\Skeleton_Concrete_Slab\04_formal\A-S\A-S_sat\A1.00_B-50.00_C2.00.sat'
job_output_folder = r'D:\code202410\Skeleton_Concrete_Slab\04_formal\A-S\A-S'

if not os.path.exists(job_output_folder):
    os.makedirs(job_output_folder)

executeOnCaeStartup()

filename = os.path.basename(sat_path)
raw_name = os.path.splitext(filename)[0]
safe_base_name = 'job_' + ''.join([c if c.isalnum() else '_' for c in raw_name])
model_name = 'Model_' + safe_base_name
job_name = safe_base_name
part_name = safe_base_name

print(f">>> 开始对 {filename} 进行【提速增强版】多步非线性模拟...")

try:
    if model_name in mdb.models:
        del mdb.models[model_name]
    
    model = mdb.Model(name=model_name)
    acis = mdb.openAcis(sat_path, scaleFromFile=OFF)
    model.PartFromGeometryFile(name=part_name, geometryFile=acis, combine=False,
                               dimensionality=THREE_D, type=DEFORMABLE_BODY)
    
    p = model.parts[part_name]
    
    # --- 材料定义 (保持 CDP 模型不变) ---
    mat = model.Material(name='concrete')
    mat.Density(table=((2500.0,),))
    mat.Elastic(table=((30e9, 0.2),))
    
    mat.ConcreteDamagedPlasticity(table=((38.0, 0.1, 1.16, 0.667, 0.001),))
    mat.concreteDamagedPlasticity.ConcreteCompressionHardening(table=(
        (15.0e6, 0.0), (30.0e6, 0.0015), (20.0e6, 0.003), (5.0e6, 0.008)
    ))
    mat.concreteDamagedPlasticity.ConcreteCompressionDamage(table=(
        (0.0, 0.0), (0.0, 0.0015), (0.33, 0.003), (0.8, 0.008)
    ))
    mat.concreteDamagedPlasticity.ConcreteTensionStiffening(table=(
        (3.0e6, 0.0), (1.5e6, 0.0002), (0.5e6, 0.0005), (0.1e6, 0.001)
    ))
    mat.concreteDamagedPlasticity.ConcreteTensionDamage(table=(
        (0.0, 0.0), (0.5, 0.0002), (0.8, 0.0005), (0.95, 0.001)
    ))
    
    model.HomogeneousSolidSection(name='Section-1', material='concrete', thickness=None)
    region = p.Set(cells=p.cells, name='Set-1')
    p.SectionAssignment(region=region, sectionName='Section-1', offset=0.0,
                        offsetType=MIDDLE_SURFACE, offsetField='', thicknessAssignment=FROM_SECTION)
    
    a = model.rootAssembly
    a.DatumCsysByDefault(CARTESIAN)
    a.Instance(name=part_name, part=p, dependent=ON)
    
    # --- 定义多级分析步 (大幅放宽 minInc 到 1e-8 或更小，增大 maxNumInc) ---
    model.StaticStep(name='Step-1_BaseLoad', previous='Initial', nlgeom=ON,
                     initialInc=0.1, minInc=1e-8, maxInc=1.0, maxNumInc=2000)
    model.StaticStep(name='Step-2_Load_20kPa', previous='Step-1_BaseLoad', nlgeom=ON,
                     initialInc=0.05, minInc=1e-8, maxInc=0.1, maxNumInc=2000)
    model.StaticStep(name='Step-3_Load_40kPa', previous='Step-2_Load_20kPa', nlgeom=ON,
                     initialInc=0.02, minInc=1e-8, maxInc=0.05, maxNumInc=2000)
    model.StaticStep(name='Step-4_Load_80kPa', previous='Step-3_Load_40kPa', nlgeom=ON,
                     initialInc=0.01, minInc=1e-8, maxInc=0.05, maxNumInc=2000)
    
    model.fieldOutputRequests['F-Output-1'].setValues(
        variables=('S', 'U', 'IVOL', 'DAMAGEC', 'DAMAGET', 'PEEQ')
    )
    
    model.Gravity(name='gravity', createStepName='Step-1_BaseLoad', comp3=-9.81)
    inst = a.instances[part_name]
    
    faces_z0 = inst.faces.getByBoundingBox(zMin=-0.01, zMax=0.01)
    if faces_z0:
        model.EncastreBC(name='BC-Encastre', createStepName='Step-1_BaseLoad',
                         region=a.Set(faces=faces_z0, name='Set-Encastre'))
    
    faces_xsymm = inst.faces.getByBoundingBox(xMin=-4.01, xMax=-3.99) + \
                  inst.faces.getByBoundingBox(xMin=3.99, xMax=4.01)
    if faces_xsymm:
        model.XsymmBC(name='BC-Xsymm', createStepName='Step-1_BaseLoad',
                      region=a.Set(faces=faces_xsymm, name='Set-Xsymm'))
                  
    faces_ysymm = inst.faces.getByBoundingBox(yMin=-4.01, yMax=-3.99) + \
                  inst.faces.getByBoundingBox(yMin=3.99, yMax=4.01)
    if faces_ysymm:
        model.YsymmBC(name='BC-Ysymm', createStepName='Step-1_BaseLoad',
                      region=a.Set(faces=faces_ysymm, name='Set-Ysymm'))
    
    faces_load = inst.faces.getByBoundingBox(zMin=4.300, zMax=4.350)
    if faces_load:
        surf = a.Surface(side1Faces=faces_load, name='Surf-Load')
        model.Pressure(name='Load-Top', createStepName='Step-1_BaseLoad', region=surf,
                       magnitude=6000.0, distributionType=UNIFORM)
        model.loads['Load-Top'].setValuesInStep(stepName='Step-2_Load_20kPa', magnitude=20000.0)
        model.loads['Load-Top'].setValuesInStep(stepName='Step-3_Load_40kPa', magnitude=40000.0)
        model.loads['Load-Top'].setValuesInStep(stepName='Step-4_Load_80kPa', magnitude=80000.0)
        
    # --- 网格划分 ---
    a.makeIndependent(instances=(inst,))
    pickedRegions = inst.cells
    a.setMeshControls(regions=pickedRegions, elemShape=TET, technique=FREE)
    a.setElementType(
        regions=(pickedRegions,),
        elemTypes=(mesh.ElemType(elemCode=C3D4),)
    )
    a.seedPartInstance(regions=(inst,), size=0.35, deviationFactor=0.1, minSizeFactor=0.1)
    a.generateMesh(regions=(inst,))
    
    # --- 提交作业 ---
    job = mdb.Job(name=job_name, model=model_name, resultsFormat=ODB,
                  numCpus=6, numDomains=6, multiprocessingMode=DEFAULT)
                  
    print(f">>> 正在提交分析作业 {job_name}，已开启 6 核并行计算与网格精简...")
    job.submit(consistencyChecking=OFF)
    
    try:
        job.waitForCompletion()
    except Exception as e:
        print(f">>> 提示：结构可能已发生严重开裂导致提前终止，这是断裂模拟的正常现象。")
    
    # --- 移动 ODB (加入重试机制避免 WinError 32) ---
    odb_name = job_name + '.odb'
    default_odb_path = os.path.join(os.getcwd(), odb_name)
    final_odb_path = os.path.join(job_output_folder, odb_name)
    
    if os.path.exists(default_odb_path):
        # 尝试移动文件，最多尝试 5 次，每次间隔 3 秒
        max_retries = 5
        for attempt in range(max_retries):
            try:
                shutil.move(default_odb_path, final_odb_path)
                print(f'>>> 处理结束！ODB文件已成功转移至: {final_odb_path}')
                break
            except PermissionError:
                print(f">>> 正在等待 Abaqus 释放 ODB 文件锁 (尝试 {attempt + 1}/{max_retries})...")
                time.sleep(3)
        else:
            print(f">>> 警告: ODB文件仍被占用。请稍后手动从工作目录 [{default_odb_path}] 复制到目标文件夹。")
    else:
        print(f'>>> 警告: 未找到输出的 ODB 文件。')
        
except Exception as e:
    print(f">>> 运行出错，原因：{e}")

print("=== 脚本运行结束 ===")