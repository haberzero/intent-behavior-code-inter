from core.runtime.module_system.discovery import ModuleDiscoveryService
import os

builtin_path = os.path.join(os.getcwd(), "ibc_modules")
discovery = ModuleDiscoveryService([builtin_path])
host = discovery.discover_all()

ai_metadata = host.get_module_type("ai")
print(f"AI Metadata name: {ai_metadata.name}")
print(f"AI Metadata members: {list(ai_metadata.members.keys())}")

host_metadata = host.get_module_type("host")
print(f"Host Metadata name: {host_metadata.name}")
print(f"Host Metadata members: {list(host_metadata.members.keys())}")
