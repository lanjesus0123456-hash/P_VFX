import unreal
import unity_bridge

if not unity_bridge.register_menu():
    def _unity_bridge_startup_tick(delta_seconds):
        global _unity_bridge_tick_handle
        if unity_bridge.register_menu():
            unreal.unregister_slate_post_tick_callback(_unity_bridge_tick_handle)
    _unity_bridge_tick_handle = unreal.register_slate_post_tick_callback(_unity_bridge_startup_tick)

