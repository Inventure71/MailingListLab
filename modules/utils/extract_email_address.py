import re


def extract_email_address(sender_string):
    """
    Extract email address from sender string.
    
    Args:
        sender_string (str): Full sender like "Display Name <email@domain.com>" or just "email@domain.com"
    
    Returns:
        str: Just the email address part
    
    Examples:
        extract_email_address("Matteo Giorgetti <matteo.giorgetti.05@gmail.com>") -> "matteo.giorgetti.05@gmail.com"
        extract_email_address("matteo.giorgetti.05@gmail.com") -> "matteo.giorgetti.05@gmail.com"
    """
    if not sender_string:
        return ""
    
    # Check if it contains angle brackets indicating "Display Name <email>"
    if "<" in sender_string and ">" in sender_string:
        # Extract email between < and >
        match = re.search(r'<([^>]+)>', sender_string)
        if match:
            return match.group(1).strip()
    
    # If no angle brackets, assume it's already just an email address
    return sender_string.strip()

    