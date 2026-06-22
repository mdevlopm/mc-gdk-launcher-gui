import os

def wrap_flatpak_cmd(cmd, env=None, cwd=None):
    """Wraps a command with flatpak-spawn --host if running inside flatpak."""
    if not os.path.exists("/.flatpak-info"):
        return cmd
    wrapped = ["flatpak-spawn", "--host"]
    if cwd:
        wrapped.append(f"--directory={cwd}")
    if env:
        skip_vars = {"LD_LIBRARY_PATH", "LD_PRELOAD", "PATH", "PYTHONPATH", "PYTHONHOME", "XDG_DATA_DIRS", "XDG_CONFIG_DIRS", "GI_TYPELIB_PATH", "GST_PLUGIN_SYSTEM_PATH"}
        for k, v in env.items():
            if k not in skip_vars and (k not in os.environ or os.environ[k] != v):
                wrapped.append(f"--env={k}={v}")
    return wrapped + cmd
