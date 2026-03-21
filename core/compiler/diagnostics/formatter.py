from typing import List, Optional, TYPE_CHECKING
from core.kernel.issue import Diagnostic
from core.base.source_atomic import Location, Severity

if TYPE_CHECKING:
    from core.base.source.source_manager import SourceManager

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
    def format(diagnostic: Diagnostic, use_color: bool = True, source_manager: Optional['SourceManager'] = None) -> str:
        severity_label = diagnostic.severity.name
        color_start = DiagnosticFormatter.COLORS.get(diagnostic.severity, "") if use_color else ""
        color_reset = DiagnosticFormatter.COLORS["RESET"] if use_color else ""
        bold = DiagnosticFormatter.COLORS["BOLD"] if use_color else ""
        
        # Header: [ERROR] SEM_001: Variable 'x' is not defined
        header = f"{color_start}[{severity_label}] {diagnostic.code}: {diagnostic.message}{color_reset}"
        
        # Location info
        loc_str = ""
        context_str = ""
        
        if diagnostic.location:
            loc = diagnostic.location
            loc_str = f"\n  --> {loc.file_path}:{loc.line}:{loc.column}"
            
            # Try to get context line from Location first, then SourceManager
            context_line = loc.context_line
            if not context_line and source_manager:
                context_line = source_manager.get_line(loc.file_path, loc.line)
            
            if context_line:
                line_num_str = str(loc.line).rjust(4)
                
                # Determine highlight length
                highlight_len = loc.length
                if loc.end_line == loc.line and loc.end_column is not None:
                    highlight_len = max(1, loc.end_column - loc.column)
                
                context_str = f"\n{line_num_str} | {context_line}\n     | {' ' * (loc.column - 1)}{'^' * highlight_len}"
        
        hint_str = ""
        if diagnostic.hint:
            hint_str = f"\n  {bold}Hint:{color_reset} {diagnostic.hint}"
            
        return f"{header}{loc_str}{context_str}{hint_str}"

    @staticmethod
    def format_all(diagnostics: List[Diagnostic], use_color: bool = True, source_manager: Optional['SourceManager'] = None) -> str:
        return "\n\n".join([DiagnosticFormatter.format(d, use_color, source_manager) for d in diagnostics])
