def sanitize_string(string):
    # string needs to be a valid folder name
    import re
    # Remove or replace invalid characters for folder names (Windows, macOS, Linux)
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', string)
    sanitized = sanitized.strip()
    # Optionally, limit length (e.g., 255 chars for most filesystems)
    return sanitized[:255]

    