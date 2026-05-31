# -*- coding: utf-8 -*-
import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs
import Grasshopper
import System
import os
import traceback
import Grasshopper.Kernel.Special as gh_special
import csv
from Rhino.Display import DisplayBitmap
import clr
clr.AddReference("System")
from System.IO import StreamWriter, File, FileMode

# ===============================
# 配置区 可自由选择运行区间
# ===============================
export_root = r"D:\\code202410\\Skeleton_Concrete_Slab\\04_formal\\A-S\\A-S_sat"
thumbnail_folder = r"D:\\code202410\\Skeleton_Concrete_Slab\\04_formal\\A-S\\A-S_pic"
csv_path = r"D:\\code202410\\Skeleton_Concrete_Slab\\04_formal\\A-S\\model_volume.csv"
slider_names = ["parameterA", "parameterB", "parameterC"]

# 修改了范围和数量 (起始值, 终止值, 数量)
slider_ranges = {
    "parameterA": (0, 4, 5),     # 0, 1, 2, 3, 4 共5个值
    "parameterB": (-50, -30, 6), # -50 到 -30，差值为4，共6个值
    "parameterC": (2, 4, 3),     # 2, 3, 4 共3个值
}
export_layer_name = "ExportTemp"
bake_toggle_nickname = "bakeToggle"
start_index = 0  # 从0开始计数，故从第N+1个组合开始导出

# ===============================
# 状态变量
# ===============================
params_queue = []
current_index = 0
is_processing = False
bake_done = False
prev_obj_count = 0
ghdoc = Grasshopper.Instances.ActiveCanvas.Document

# ===============================
# 构造参数组合队列
# ===============================
def build_param_queue():
    global params_queue
    a_vals = [slider_ranges["parameterA"][0] + i*(slider_ranges["parameterA"][1] - slider_ranges["parameterA"][0])/(slider_ranges["parameterA"][2]-1) for i in range(slider_ranges["parameterA"][2])]
    b_vals = [slider_ranges["parameterB"][0] + i*(slider_ranges["parameterB"][1] - slider_ranges["parameterB"][0])/(slider_ranges["parameterB"][2]-1) for i in range(slider_ranges["parameterB"][2])]
    c_vals = [slider_ranges["parameterC"][0] + i*(slider_ranges["parameterC"][1] - slider_ranges["parameterC"][0])/(slider_ranges["parameterC"][2]-1) for i in range(slider_ranges["parameterC"][2])]
    
    # 将原来的itertools.product改为嵌套循环，确保遍历顺序为A→B→C
    params_queue = []
    for c in c_vals:
        for b in b_vals:
            for a in a_vals:
                # 转换为整数判断，避免浮点精度导致的遗漏
                a_int = int(round(a))
                c_int = int(round(c))
                
                # 新增逻辑：当parameterA取值为1或3时，parameterC不能为3、4
                if a_int in [1, 3] and c_int in [3, 4]:
                    continue
                    
                params_queue.append((a, b, c))
    
    params_queue = params_queue[:90]  # 测试时可限制数量，正式导出时请注释掉此行

# ===============================
# 设置滑块值
# ===============================
def set_slider_value(slider_nickname, value):
    for obj in ghdoc.Objects:
        if isinstance(obj, gh_special.GH_NumberSlider) and obj.NickName == slider_nickname:
            obj.SetSliderValue(float(value))
            obj.ExpireSolution(True)
            return

# ===============================
# 设置 Bake Toggle
# ===============================
def set_bake_toggle(state):
    for obj in ghdoc.Objects:
        if isinstance(obj, gh_special.GH_BooleanToggle) and obj.NickName == bake_toggle_nickname:
            if obj.Value != state:
                obj.Value = state
                obj.ExpireSolution(True)
                ghdoc.ScheduleSolution(1, None)
            return

# ===============================
# 清空导出图层
# ===============================
def clear_export_layer():
    if rs.IsLayer(export_layer_name):
        objs = rs.ObjectsByLayer(export_layer_name)
        if objs:
            rs.DeleteObjects(objs)

# ===============================
# 导出当前模型
# ===============================
def capture_thumbnail(file_name):
    # 使用 RhinoDoc.ActiveDoc.Views.ActiveView.CaptureToBitmap 生成缩略图
    view = Rhino.RhinoDoc.ActiveDoc.Views.ActiveView
    rs.UnselectAllObjects()
    bmp = view.CaptureToBitmap(System.Drawing.Size(300, 300), True, True, True)
    if bmp:
        if not os.path.exists(thumbnail_folder):
            os.makedirs(thumbnail_folder)
        bmp.Save(os.path.join(thumbnail_folder, file_name))

def compute_volume(objs):
    total_volume = 0.0
    for obj_id in objs:
        brep = rs.coercebrep(obj_id)
        if brep:
            volume = Rhino.Geometry.VolumeMassProperties.Compute(brep)
            if volume:
                total_volume += volume.Volume
    return total_volume

def write_volume_to_csv(a, b, c, volume):
    header = 'A,B,C,Volume\n'
    new_row = '{:.2f},{:.2f},{:.2f},{:.6f}\n'.format(a, b, c, volume)

    file_exists = os.path.exists(csv_path)

    mode = FileMode.Append if file_exists else FileMode.Create
    sw = StreamWriter(File.Open(csv_path, mode))

    try:
        if not file_exists:
            sw.Write(header)
        sw.Write(new_row)
    finally:
        sw.Close()

def export_current_model(a, b, c):
    objs = rs.ObjectsByLayer(export_layer_name)
    if not objs:
        print("未找到导出对象，跳过导出")
        return

    rs.UnselectAllObjects()
    rs.SelectObjects(objs)
    file_name = "A{:.2f}_B{:.2f}_C{:.2f}.sat".format(a, b, c)
    export_file = os.path.join(export_root, file_name)
    export_cmd = '-_Export "{}" _Enter'.format(export_file)
    result = rs.Command(export_cmd, True)
    if result:
        print("导出成功: {}".format(export_file))

        # 生成缩略图
        image_name = file_name.replace(".sat", ".png")
        capture_thumbnail(image_name)

        # 计算体积并写入CSV
        volume = compute_volume(objs)
        print("体积:", volume)  # 添加此调试输出
        write_volume_to_csv(a, b, c, volume)

    else:
        print("导出失败: {}".format(export_cmd))

    rs.DeleteObjects(objs)

# ===============================
# 跳过当前组合，准备下一个
# ===============================
def skip_current(a, b, c, err=None):
    global current_index, is_processing, bake_done
    print("跳过参数组合 A={:.2f}, B={:.2f}, C={:.2f}".format(a, b, c))
    if err is not None:
        print("错误信息：\n{}".format(err))
    # 确保关闭 Bake
    try:
        set_bake_toggle(False)
    except:
        pass
    # 清理残留
    clear_export_layer()
    # 前进到下一组
    current_index += 1
    is_processing = False
    bake_done = False
    # 继续调度
    if current_index < len(params_queue):
        Rhino.RhinoApp.Idle += on_idle
    else:
        print("全部导出完成，共 {} 个".format(len(params_queue)))
        ghdoc.SolutionEnd -= on_solution_end

# ===============================
# 主处理逻辑（空闲帧触发）
# ===============================
def on_idle(sender, e):
    global is_processing, bake_done, current_index, prev_obj_count
    Rhino.RhinoApp.Idle -= on_idle

    # 如果参数用尽，退出
    if current_index >= len(params_queue):
        print("所有参数已处理完毕")
        ghdoc.SolutionEnd -= on_solution_end
        return

    a, b, c = params_queue[current_index]

    try:
        if not is_processing:
            # 第一次进入，设置参数并触发 Bake
            print("处理参数: A={:.2f}, B={:.2f}, C={:.2f}".format(a, b, c))
            clear_export_layer()
            prev_obj_count = 0

            set_slider_value("parameterA", a)
            set_slider_value("parameterB", b)
            set_slider_value("parameterC", c)

            bake_done = False
            is_processing = True
            set_bake_toggle(True)  # 触发 Bake
            Rhino.RhinoApp.Idle += on_idle
            return

        # 监测 Bake 生成对象
        objs = rs.ObjectsByLayer(export_layer_name)
        if not bake_done and objs and len(objs) > prev_obj_count:
            prev_obj_count = len(objs)
            # 导出
            export_current_model(a, b, c)
            # 停止 Bake
            set_bake_toggle(False)
            bake_done = True
            Rhino.RhinoApp.Idle += on_idle
            return

        # Bake 完成，切换到下一组
        if bake_done:
            current_index += 1
            is_processing = False
            if current_index < len(params_queue):
                Rhino.RhinoApp.Idle += on_idle
            else:
                print("全部导出完成，共 {} 个".format(len(params_queue)))
                ghdoc.SolutionEnd -= on_solution_end

    except Exception:
        # 捕获任何异常，跳过当前参数组合
        err = traceback.format_exc()
        skip_current(a, b, c, err)

# ===============================
# 空函数（解决解算监听占位）
# ===============================
def on_solution_end(sender, e):
    pass

# ===============================
# 启动批处理导出
# ===============================
def start_batch_export():
    if not os.path.exists(export_root):
        os.makedirs(export_root)
    build_param_queue()
    if len(params_queue) == 0:
        print("没有参数组合")
        return
    global current_index
    current_index = start_index  # 设置开始索引
    if current_index >= len(params_queue):
        print("起始索引超出参数总数，总数为 {}，起始索引为 {}".format(len(params_queue), current_index))
        return
    if ghdoc:
        ghdoc.SolutionEnd += on_solution_end
    Rhino.RhinoApp.Idle += on_idle

# ===============================
# 运行
# ===============================
start_batch_export()