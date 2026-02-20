from typing import List
from typedef.diagnostic_types import Diagnostic, Severity, Location

class DiagnosticFormatter:
    """
    Formats diagnostics for console output.
    """
    
    COLORS = {
        Severity.HINT: "\033[94m",    # Blue
        Severity.INFO: "\033[92m",    # Green
        Severity.WARNING: "\033[93m", # Yellow
        Severity.ERROR: "\033[91m",   # Red
        Severity.FATAL: "\033[95m",   # Magenta
        "RESET": "\033[0m",
        "BOLD": "\033[1m"
    }

    @staticmethod
    def format(diagnostic: Diagnostic, use_color: bool = True) -> str:
        severity_label = diagnostic.severity.name
        color_start = DiagnosticFormatter.COLORS.get(diagnostic.severity, "") if use_color else ""
        color_reset = DiagnosticFormatter.COLORS["RESET"] if use_color else ""
        bold = DiagnosticFormatter.COLORS["BOLD"] if use_color else ""
        
        # Header: [ERROR] E1001: Invalid character
        header = f"{color_start}[{severity_label}] {diagnostic.code}: {diagnostic.message}{color_reset}"
        
        # Location info
        loc_str = ""
        context_str = ""
        
        if diagnostic.location:
            loc = diagnostic.location
            loc_str = f"\n  --> {loc.file_path}:{loc.line}:{loc.column}"
            
            if loc.context_line:
                line_num_str = str(loc.line).rjust(4)
                context_str = f"\n{line_num_str} | {loc.context_line}\n     | {' ' * (loc.column - 1)}{'^' * loc.length}"
        
        hint_str = ""
        if diagnostic.hint:
            hint_str = f"\n  {bold}Hint:{color_reset} {diagnostic.hint}"
            
        return f"{header}{loc_str}{context_str}{hint_str}"

    @staticmethod
    def format_all(diagnostics: List[Diagnostic], use_color: bool = True) -> str:
        return "\n\n".join([DiagnosticFormatter.format(d, use_color) for d in diagnostics])
