"""
Discovery script — run on Day 1 (A3.3) to resolve all open Decision Log items.

Usage:
    cd backend/
    source .venv/bin/activate
    python discovery.py

Paste ALL output into docs/meta.md Decisions Log before proceeding.
"""
import inspect
import sys


def discover_genblaze_google():
    print("=" * 60)
    print("genblaze_google — Provider Class Discovery")
    print("=" * 60)

    try:
        import genblaze_google
    except ImportError:
        print("ERROR: genblaze_google not installed.")
        print("Run: pip install genblaze-google")
        sys.exit(1)

    print(f"\nPackage version: {getattr(genblaze_google, '__version__', 'unknown')}")
    print(f"\nAll exports:\n{dir(genblaze_google)}\n")

    # Probe common provider class names
    candidate_names = [
        "GoogleImageProvider", "GoogleVideoProvider",
        "ImagenProvider", "VeoProvider",
        "GoogleProvider", "GoogleMediaProvider",
        "ImageProvider", "VideoProvider",
    ]
    found = []
    for name in candidate_names:
        if hasattr(genblaze_google, name):
            cls = getattr(genblaze_google, name)
            print(f"✓ Found class: {name}")
            print(f"  Module: {cls.__module__}")
            # Probe for model registry
            for attr in ["MODEL_REGISTRY", "model_registry", "MODELS", "models", "DEFAULT_MODEL"]:
                if hasattr(cls, attr):
                    val = getattr(cls, attr)
                    print(f"  {attr}: {val}")
            # Probe constructor signature
            try:
                sig = inspect.signature(cls.__init__)
                print(f"  __init__ signature: {sig}")
            except Exception:
                pass
            found.append(name)
            print()

    if not found:
        print("⚠ No known provider class names found. Full dir() above — look manually.")

    # Discover exception classes
    print("\n" + "=" * 60)
    print("Exception classes (needed for MultiKeyGoogleProvider catch clause)")
    print("=" * 60)
    exc_found = []
    for name, obj in inspect.getmembers(genblaze_google):
        try:
            if inspect.isclass(obj) and issubclass(obj, Exception):
                print(f"  ⚠ Exception: {name} — {obj.__module__}.{obj.__qualname__}")
                exc_found.append(name)
        except TypeError:
            pass

    if not exc_found:
        print("  None found in genblaze_google — check genblaze_core for base exceptions")
        try:
            import genblaze_core
            for name, obj in inspect.getmembers(genblaze_core):
                try:
                    if inspect.isclass(obj) and issubclass(obj, Exception):
                        print(f"  ⚠ genblaze_core Exception: {name}")
                except TypeError:
                    pass
        except ImportError:
            pass


def discover_genblaze_core():
    print("\n" + "=" * 60)
    print("genblaze_core — Modality / KeyStrategy / Sink Discovery")
    print("=" * 60)
    try:
        import genblaze_core
        print(f"Version: {getattr(genblaze_core, '__version__', 'unknown')}")
        for name in ["Pipeline", "Modality", "ObjectStorageSink", "KeyStrategy"]:
            if hasattr(genblaze_core, name):
                obj = getattr(genblaze_core, name)
                print(f"  ✓ {name}: {obj}")
                if name == "Modality":
                    try:
                        print(f"    Values: {list(obj)}")
                    except Exception:
                        pass
            else:
                print(f"  ✗ {name}: NOT FOUND")
    except ImportError as e:
        print(f"ERROR: {e}")


def discover_media_handlers():
    print("\n" + "=" * 60)
    print("Media Handlers — embed handler name for images")
    print("(Mp4Handler confirmed for video — need image equivalent)")
    print("=" * 60)
    for pkg_name in ["genblaze_core", "genblaze_google"]:
        try:
            pkg = __import__(pkg_name)
            for name, obj in inspect.getmembers(pkg):
                if "handler" in name.lower() or "Handler" in name:
                    print(f"  {pkg_name}.{name}: {obj}")
        except ImportError:
            pass


if __name__ == "__main__":
    discover_genblaze_google()
    discover_genblaze_core()
    discover_media_handlers()

    print("\n" + "=" * 60)
    print("ACTION REQUIRED:")
    print("Paste this entire output into docs/meta.md Decisions Log.")
    print("Update pipeline.py with the correct class names and model IDs.")
    print("=" * 60)
