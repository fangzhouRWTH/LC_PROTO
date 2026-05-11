# scripts/minimal_isaac_start.py

def main():
    # Isaac Sim 5.x 推荐路径
    try:
        from isaacsim.simulation_app import SimulationApp
    except ImportError:
        # 兼容旧版本 Isaac Sim
        from omni.isaac.kit import SimulationApp

    # 启动 Isaac Sim / Omniverse Kit
    simulation_app = SimulationApp({
        "headless": False,   # False = 打开 GUI；True = 无界面运行
        "width": 1280,
        "height": 720,
    })

    print("[OK] Isaac Sim started.")

    # SimulationApp 启动之后，才能安全 import omni / pxr 相关模块
    import omni.usd
    from pxr import UsdGeom

    # 获取当前 stage
    context = omni.usd.get_context()
    stage = context.get_stage()

    if stage is None:
        raise RuntimeError("Failed to get USD stage.")

    # 创建一个最小测试 prim
    UsdGeom.Xform.Define(stage, "/World/TestXform")

    print("[OK] USD stage is available.")
    print("[OK] Created /World/TestXform.")

    # 让 Isaac Sim 更新一段时间，方便确认窗口正常打开
    for _ in range(120):
        simulation_app.update()

    print("[OK] Closing Isaac Sim.")

    simulation_app.close()


if __name__ == "__main__":
    main()