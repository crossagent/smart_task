
import pkgutil
import importlib
import google.adk

def find_class_in_package(package, class_name):
    path = package.__path__
    prefix = package.__name__ + "."

    for _, name, ispkg in pkgutil.walk_packages(path, prefix):
        try:
            module = importlib.import_module(name)
            if hasattr(module, class_name):
                print(f"Found {class_name} in module: {name}")
                return
        except Exception as e:
            # print(f"Could not import {name}: {e}")
            pass
    print(f"Could not find {class_name} in package {package.__name__}")

print("Searching for ToolContext in google.adk...")
find_class_in_package(google.adk, "ToolContext")
