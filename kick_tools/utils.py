import sys

def parse_time_to_seconds(time_str):
    """
    Parses a time string in formats: 'seconds', 'mm:ss', or 'hh:mm:ss'.
    Returns float seconds.
    """
    if not time_str:
        return 0.0
    if isinstance(time_str, (int, float)):
        return float(time_str)
    if time_str.isdigit():
        return float(time_str)
    
    parts = time_str.replace(',', '.').split(':')
    if len(parts) == 3: # hh:mm:ss
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2: # mm:ss
        return float(parts[0]) * 60 + float(parts[1])
    return 0.0

def format_timestamp(seconds, include_ms=False):
    """
    Formats seconds into hh:mm:ss or hh:mm:ss,ms format.
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if include_ms:
        ms = int(round((seconds - int(seconds)) * 1000))
        if ms >= 1000:
            ms -= 1000
            s += 1
            if s >= 60:
                s -= 60
                m += 1
                if m >= 60:
                    m -= 60
                    h += 1
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return f"{h:02d}:{m:02d}:{s:02d}"

def ensure_package_installed(package_name, import_name=None):
    """
    Checks if a package is installed, otherwise prints an error and exits.
    """
    import_name = import_name or package_name
    try:
        __import__(import_name)
    except ImportError:
        print(f"Error: '{package_name}' is not installed. Run 'pip install {package_name}'.", file=sys.stderr)
        sys.exit(1)
