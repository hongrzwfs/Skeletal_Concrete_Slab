# -*- coding: mbcs -*-
from odbAccess import openOdb
from abaqusConstants import *
import os
import time
import csv
import numpy as np

# === 科研参数配置 ===
L_SPAN = 8.0         
F_ALLOW = (L_SPAN / 400.0) * 1000.0
G_BASE = 44555.84
DENSITY = 2500.0

# --- 目标函数参数 ---
ALLIE_MIN = 318.7806    # 能量基准值 (J)
W1, W2, W3 = 0.33, 0.33, 0.33  # 综合工程导向权重分配

def iqr_filter(data, k=1.5):
    arr = np.array(data)
    if len(arr) == 0: return np.array([])
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    return arr[(arr >= q1 - k*iqr) & (arr <= q3 + k*iqr)]

def format_stress(stress):
    return round(stress / 1e6, 3) if stress is not None else None

# === 设置路径 ===
odb_folder = r'D:\code202410\Skeletal_Concrete_Slab\data_base\A-S\A-S_odb'
output_folder = r'D:\code202410\Skeletal_Concrete_Slab\data_base\A-S'
csv_output_path = os.path.join(output_folder, 'results_summary_SEI_ture.csv')

start_time = time.time()
odb_files = sorted([f for f in os.listdir(odb_folder) if f.endswith('.odb')])
results = []

print("开始提取 ODB 核心指标并计算结构综合效率指数 (J)...")

for odb_file in odb_files:
    odb_path = os.path.join(odb_folder, odb_file)
    odb = None
    try:
        odb = openOdb(path=odb_path)
        
        if not odb.steps.keys():
            continue
            
        step_name = odb.steps.keys()[-1]
        step = odb.steps[step_name]
        
        if len(step.frames) == 0:
            continue
            
        frame = step.frames[-1]

        # --- 1. 提取位移 ---
        u_field = frame.fieldOutputs['U']
        max_disp_mm = max([v.magnitude for v in u_field.values]) * 1000 if u_field.values else 0.0

        # --- 2. 提取应力场与体积 ---
        s_field = frame.fieldOutputs['S']
        max_p = s_field.getScalarField(invariant=MAX_PRINCIPAL)
        min_p = s_field.getScalarField(invariant=MIN_PRINCIPAL)
        
        s1_values = [v.data for v in max_p.values]
        s3_values = [v.data for v in min_p.values]

        has_ivol = 'IVOL' in frame.fieldOutputs.keys()
        ivols = [v.data for v in frame.fieldOutputs['IVOL'].values] if has_ivol else [1.0] * len(s1_values)
        total_volume = sum(ivols)

        # --- 3. 核心子项计算 ---
        # (1) 纯压占比 Phi_comp
        v_pure_compression = sum([ivols[i] for i in range(len(ivols)) if s1_values[i] <= 0])
        phi_comp = v_pure_compression / total_volume if total_volume > 0 else 0
        
        # (2) 比刚度权重 Omega_stiff
        current_weight = total_volume * DENSITY if has_ivol else 1.0
        omega_stiff = (F_ALLOW / max_disp_mm) * (G_BASE / current_weight) if max_disp_mm > 0 else 0

        # --- 4. ALLIE 提取与 Gamma_allie 计算 ---
        max_allie = 0.0
        for r_name in ['Assembly ASSEMBLY', 'Whole Model', 'Assembly  ASSEMBLY']:
            if r_name in step.historyRegions:
                hr = step.historyRegions[r_name]
                if 'ALLIE' in hr.historyOutputs:
                    max_allie = hr.historyOutputs['ALLIE'].data[-1][1]
                    break
        
        # (3) 全局能量效能因子 Gamma_allie (能量越低效能越高)
        gamma_allie = ALLIE_MIN / max_allie if max_allie > 0 else 0

        # --- 5. 综合效率指数 J 计算 ---
        # 确保参与计算的 omega_stiff 是数值
        stiff_val = omega_stiff if isinstance(omega_stiff, (int, float)) else 0
        j_index = W1 * phi_comp + W2 * gamma_allie + W3 * stiff_val

        # 整理应力 (供参考)
        compression_list = [s for s in s3_values if s < 0]
        tension_list = [s for s in s1_values if s > 0]
        clean_max_C = min(iqr_filter(compression_list)) if compression_list else 0
        clean_max_T = max(iqr_filter(tension_list)) if tension_list else 0

        results.append([
            odb_file,
            format_stress(clean_max_C), format_stress(clean_max_T),
            round(max_disp_mm, 3), 
            round(phi_comp, 4), 
            round(gamma_allie, 4),
            round(omega_stiff, 4) if has_ivol else "N/A",
            round(max_allie, 4),
            round(j_index, 4)
        ])
        print("处理成功: %s | J: %.4f" % (odb_file, j_index))

    except Exception as e:
        print("处理 %s 出错: %s" % (odb_file, str(e)))
    finally:
        if odb: odb.close()

# === 写入 CSV ===
header = [
    'FileName', 'Clean_Comp_MPa', 'Clean_Tens_MPa', 'Max_Disp_mm', 
    'Phi_Comp', 'Gamma_Allie', 'Omega_Stiff', 'ALLIE', 'SEI_J_Index'
]

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

print("\n[完成] 结构综合效率指数已保存至: %s" % csv_output_path)