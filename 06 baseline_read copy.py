# -*- coding: mbcs -*-
from odbAccess import openOdb
from abaqusConstants import *
import os
import time
import csv
import numpy as np

# === 科研参数配置 (显式配筋模型评估) ===
L_SPAN = 8.0         
F_ALLOW = (L_SPAN / 400.0) * 1000.0  # 容许挠度 (mm)

# 以下两个常数您可以根据配筋模型的最终实际总重和ALLIE进行替换
G_BASE = 44555.84
ALLIE_MIN = 318.7806
W1, W2, W3 = 0.33, 0.33, 0.33  

# 注意：由于钢筋和混凝土已经显式分离，混凝土密度统一取 2400.0 即可
DENSITY_CONC = 2400.0 

def iqr_filter(data, k=1.5):
    arr = np.array(data)
    if len(arr) == 0: return np.array([])
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    return arr[(arr >= q1 - k*iqr) & (arr <= q3 + k*iqr)]

def format_stress(stress):
    return round(stress / 1e6, 3) if stress is not None else None

# === 设置路径 (直接指向包含配筋的最新 ODB 输出路径) ===
output_folder = r'C:\Users\Admin\Desktop\polyframe\baseline_output'
odb_file_name = r'job_baseline_model_Full_Results.odb' # 与仿真计算输出的文件名对齐
odb_path = os.path.join(output_folder, odb_file_name)
csv_output_path = os.path.join(output_folder, 'reinforced_results_summary.csv')

print(">>> 开始读取配筋模型 ODB 并提取核心指标...")

results = []
odb = None

try:
    if not os.path.exists(odb_path):
        raise Exception("找不到 ODB 文件，请确认仿真作业是否运行成功。路径: " + odb_path)

    odb = openOdb(path=odb_path)
    
    if not odb.steps.keys():
        raise Exception("ODB 文件中没有分析步数据。")
        
    step_name = odb.steps.keys()[-1]
    step = odb.steps[step_name]
    
    if len(step.frames) == 0:
        raise Exception("分析步中没有帧数据。")
        
    frame = step.frames[-1]

    # --- 1. 提取全局位移 ---
    u_field = frame.fieldOutputs['U']
    max_disp_mm = max([v.magnitude for v in u_field.values]) * 1000 if u_field.values else 0.0

    # --- 2. 核心修正：精准定位并隔离混凝土基体实例 ---
    # 定义混凝土实例名，与建模脚本中的 inst_conc 名字 'Concrete_Inst' 强制锁定
    conc_instance_name = 'CONCRETE_INST' 
    
    # 寻找匹配的 Instance 对象（忽略大小写差异）
    target_inst = None
    for inst_key in odb.rootAssembly.instances.keys():
        if inst_key.upper() == conc_instance_name:
            target_inst = odb.rootAssembly.instances[inst_key]
            break
            
    if target_inst is None:
        raise Exception("在 ODB 装配体中未发现名为 'Concrete_Inst' 的混凝土实例，请检查建模名称！")

    # 仅过滤属于混凝土主体的应力场与体积场
    s_field_conc = frame.fieldOutputs['S'].getSubset(region=target_inst)
    max_p_conc = s_field_conc.getScalarField(invariant=MAX_PRINCIPAL)
    min_p_conc = s_field_conc.getScalarField(invariant=MIN_PRINCIPAL)
    
    s1_values = [v.data for v in max_p_conc.values]
    s3_values = [v.data for v in min_p_conc.values]

    # 提取混凝土单元真实的物理体积
    has_ivol = 'IVOL' in frame.fieldOutputs.keys()
    if has_ivol:
        ivol_field_conc = frame.fieldOutputs['IVOL'].getSubset(region=target_inst)
        ivols = [v.data for v in ivol_field_conc.values]
    else:
        ivols = [1.0] * len(s1_values)
        
    total_volume = sum(ivols)
    # 基于显式混凝土体积计算其宏观自重
    current_weight = total_volume * DENSITY_CONC if has_ivol else 1.0

    # --- 3. 核心科研子项计算 ---
    # (1) 混凝土基体纯压占比 Phi_comp
    v_pure_compression = sum([ivols[i] for i in range(len(ivols)) if s1_values[i] <= 0])
    phi_comp = v_pure_compression / total_volume if total_volume > 0 else 0
    
    # (2) 比刚度权重 Omega_stiff
    omega_stiff = (F_ALLOW / max_disp_mm) * (G_BASE / current_weight) if max_disp_mm > 0 else 0

    # --- 4. ALLIE 全局内能能量提取 ---
    max_allie = 0.0
    for r_name in ['Assembly ASSEMBLY', 'Whole Model', 'Assembly  ASSEMBLY']:
        if r_name in step.historyRegions:
            hr = step.historyRegions[r_name]
            if 'ALLIE' in hr.historyOutputs:
                max_allie = hr.historyOutputs['ALLIE'].data[-1][1]
                break
    
    # (3) 全局能量效能因子 Gamma_allie
    gamma_allie = ALLIE_MIN / max_allie if max_allie > 0 else 0

    # --- 5. 综合效率指数 J 计算 ---
    stiff_val = omega_stiff if isinstance(omega_stiff, (int, float)) else 0
    j_index = W1 * phi_comp + W2 * gamma_allie + W3 * stiff_val

    # 仅针对混凝土主应力进行过滤清洗，避免杂乱的线单元轴向力参与
    compression_list = [s for s in s3_values if s < 0]
    tension_list = [s for s in s1_values if s > 0]
    clean_max_C = min(iqr_filter(compression_list)) if compression_list else 0
    clean_max_T = max(iqr_filter(tension_list)) if tension_list else 0

    results.append([
        odb_file_name,
        format_stress(clean_max_C), format_stress(clean_max_T),
        round(max_disp_mm, 3), 
        round(phi_comp, 4), 
        round(gamma_allie, 4),
        round(omega_stiff, 4) if has_ivol else "N/A",
        round(max_allie, 4),
        round(j_index, 4),
        round(total_volume, 3),
        round(current_weight, 2)
    ])
    
    print("\n" + "="*50)
    print("【显式配筋模型评估结果核心指标】")
    print("="*50)
    print("混凝土总体积 (m^3):     %.3f" % total_volume)
    print("混凝土总结构自重 (kg):  %.2f" % current_weight)
    print("全结构最大挠度 (mm):     %.3f" % max_disp_mm)
    print("总内能 ALLIE (J):       %.4f" % max_allie)
    print("纯压体积占比 Phi:       %.4f" % phi_comp)
    print("最大受压主应力 (MPa):   %.3f (混凝土基体)" % format_stress(clean_max_C))
    print("最大受拉主应力 (MPa):   %.3f (混凝土基体)" % format_stress(clean_max_T))
    print("="*50 + "\n")

except Exception as e:
    print(">>> 处理出错: %s" % str(e))
    traceback.print_exc()
finally:
    if odb: odb.close()

# === 写入 CSV 汇总文件 ===
header = [
    'FileName', 'Clean_Comp_MPa', 'Clean_Tens_MPa', 'Max_Disp_mm', 
    'Phi_Comp', 'Gamma_Allie', 'Omega_Stiff', 'ALLIE', 'SEI_J_Index',
    'Total_Volume_m3', 'Total_Weight_kg'
]

if results:
    try:
        with open(csv_output_path, mode='w') as f:
            writer = csv.writer(f, lineterminator='\n')
            writer.writerow(header)
            writer.writerows(results)
    except TypeError:
        with open(csv_output_path, mode='wb') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(results)
    print("[完成] 隔离配筋后的核心提取数据已保存至: %s" % csv_output_path)