from typing import List, Optional, Any
from core.types.lexer_types import TokenType, Token, LexerMode, SubState
from .str_stream import StrStream
from core.support.diagnostics.issue_tracker import IssueTracker
from core.support.diagnostics.codes import *
from core.types.diagnostic_types import Severity
from core.support.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger

# Components
from .indent_processor import IndentProcessor
from .core_scanner import CoreTokenScanner
from .llm_scanner import LLMScanner

class Lexer:
    """
    IBC-Inter Lexer.
    Responsible for converting source code into Token stream, handling indentation, line continuation, and LLM block boundaries.
    
    Refactored to use modular components:
    - IndentProcessor: Handles indentation logic.
    - CoreTokenScanner: Handles standard code tokenization.
    - LLMScanner: Handles LLM block tokenization.
    """
    def __init__(self, source_code: str, issue_tracker: Optional[IssueTracker] = None, debugger: Optional[Any] = None):
        self.scanner = StrStream(source_code)
        self.tokens: List[Token] = []
        self.issue_tracker = issue_tracker or IssueTracker(source_code)
        self.debugger = debugger or core_debugger
        
        # State Management
        self.mode_stack: List[LexerMode] = [LexerMode.NORMAL]
        self.is_new_line = True
        
        # Initialize Components
        self.indent_processor = IndentProcessor(self.scanner, self.issue_tracker)
        self.core_scanner = CoreTokenScanner(self.scanner, self.issue_tracker)
        self.llm_scanner = LLMScanner(self.scanner)

    def tokenize(self) -> List[Token]:
        self.debugger.trace(CoreModule.LEXER, DebugLevel.BASIC, "Starting tokenization...")
        try:
            while not self.scanner.is_at_end():
                self._process_line()
                
            # Check residual state (defensive check)
            self.core_scanner.check_eof_state()
            
            # Handle remaining indentation at EOF
            dedents = self.indent_processor.handle_eof()
            self.tokens.extend(dedents)
                
            self.tokens.append(Token(TokenType.EOF, "", self.scanner.line, 0))
            
            self.debugger.trace(CoreModule.LEXER, DebugLevel.BASIC, f"Tokenization complete. Total tokens: {len(self.tokens)}")
            self.debugger.trace(CoreModule.LEXER, DebugLevel.DATA, "Token stream:", data=self.tokens)
            
            # Throw exception if errors exist
            self.issue_tracker.check_errors()
            
            return self.tokens
        except Exception as e:
            # Ensure non-Diagnostic exceptions are propagated
            # If it's CompilerError, raise directly
            raise e

    def _process_line(self):
        """Process single line, including indentation and mode dispatch."""
        current_mode = self.mode_stack[-1]
        
        # 1. Handle indentation (Only in NORMAL mode)
        should_handle_indent = (
            current_mode == LexerMode.NORMAL and 
            not self.core_scanner.continuation_mode and 
            self.core_scanner.paren_level == 0 and 
            self.core_scanner.sub_state == SubState.NORMAL and
            self.is_new_line
        )

        if should_handle_indent:
            indent_res = self.indent_processor.process()
            if indent_res[0] is not None:
                # Line has content, and we got indentation tokens
                self.tokens.extend(indent_res[1])
                # We processed indentation, so we are still at the start of the "content" of the line
                # But indent_processor consumes whitespace.
            else:
                # Line was empty or comment-only, and newline was consumed.
                # So we are effectively done with this "line" from Lexer's perspective loop.
                # self.is_new_line remains True for the next iteration.
                return 

        # 2. Delegate content scanning
        if current_mode == LexerMode.NORMAL:
            # Check if we should skip whitespace if we didn't run indent processor
            # (e.g. continuation line)
            if not should_handle_indent:
                self._skip_whitespace()
                if self.core_scanner.continuation_mode:
                    self.core_scanner.continuation_mode = False
            
            new_tokens, is_newline_done, enter_llm = self.core_scanner.scan_line()
            self.tokens.extend(new_tokens)
            
            if is_newline_done:
                self.is_new_line = True
            else:
                self.is_new_line = False
                
            if enter_llm:
                self.mode_stack.append(LexerMode.LLM_BLOCK)
                
        elif current_mode == LexerMode.LLM_BLOCK:
            new_tokens, should_exit = self.llm_scanner.scan_chunk()
            self.tokens.extend(new_tokens)
            
            if should_exit:
                self.mode_stack.pop()
                # LLM block ends with 'llmend', usually followed by newline which will be picked up by next scan

    def _skip_whitespace(self):
        """Skip spaces and tabs, but not newlines."""
        while self.scanner.peek() in ' \t':
            self.scanner.advance()
