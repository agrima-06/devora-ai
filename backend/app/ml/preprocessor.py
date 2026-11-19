"""Preprocessor and normalization engine for raw error logs, tracebacks, and bug descriptions."""
import re
from enum import Enum
from typing import Dict, List, Optional, Set


class BugCategory(str, Enum):
    """Canonical 8 bug categories for Devora AI's ML Classification Engine."""
    SYNTAX_ERROR = "syntax_error"
    IMPORT_DEPENDENCY_ERROR = "import_dependency_error"
    TYPE_ERROR = "type_error"
    ATTRIBUTE_NULL_REFERENCE_ERROR = "attribute_null_reference_error"
    INDEX_KEY_ERROR = "index_key_error"
    RUNTIME_LOGIC_ERROR = "runtime_logic_error"
    DATABASE_NETWORK_ERROR = "database_network_error"
    PERMISSION_SECURITY_ERROR = "permission_security_error"

    @classmethod
    def list_all(cls) -> List[str]:
        return [c.value for c in cls]

    @classmethod
    def is_valid(cls, category: str) -> bool:
        return category in [c.value for c in cls]


# Aliases / legacy taxonomy mappings to canonical 8 categories
LEGACY_CATEGORY_MAPPINGS: Dict[str, str] = {
    # Syntax
    "syntax": BugCategory.SYNTAX_ERROR.value,
    "syntaxerror": BugCategory.SYNTAX_ERROR.value,
    "indentationerror": BugCategory.SYNTAX_ERROR.value,
    "taberror": BugCategory.SYNTAX_ERROR.value,
    # Import / Dependency
    "import": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
    "dependency": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
    "modulenotfounderror": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
    "importerror": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
    # Type
    "type": BugCategory.TYPE_ERROR.value,
    "typeerror": BugCategory.TYPE_ERROR.value,
    # Attribute / Null
    "attribute": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
    "attributeerror": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
    "null": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
    "nonetype": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
    "null_reference": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
    # Index / Key
    "index": BugCategory.INDEX_KEY_ERROR.value,
    "key": BugCategory.INDEX_KEY_ERROR.value,
    "indexerror": BugCategory.INDEX_KEY_ERROR.value,
    "keyerror": BugCategory.INDEX_KEY_ERROR.value,
    # Logic / Runtime
    "logic": BugCategory.RUNTIME_LOGIC_ERROR.value,
    "runtime": BugCategory.RUNTIME_LOGIC_ERROR.value,
    "logicerror": BugCategory.RUNTIME_LOGIC_ERROR.value,
    "runtimeerror": BugCategory.RUNTIME_LOGIC_ERROR.value,
    "zerodivisionerror": BugCategory.RUNTIME_LOGIC_ERROR.value,
    "recursionerror": BugCategory.RUNTIME_LOGIC_ERROR.value,
    "assertionerror": BugCategory.RUNTIME_LOGIC_ERROR.value,
    "valueerror": BugCategory.RUNTIME_LOGIC_ERROR.value,
    # Database / Network
    "database": BugCategory.DATABASE_NETWORK_ERROR.value,
    "network": BugCategory.DATABASE_NETWORK_ERROR.value,
    "operationalerror": BugCategory.DATABASE_NETWORK_ERROR.value,
    "integrityerror": BugCategory.DATABASE_NETWORK_ERROR.value,
    "connectionrefusederror": BugCategory.DATABASE_NETWORK_ERROR.value,
    "timeouterror": BugCategory.DATABASE_NETWORK_ERROR.value,
    # Permission / Security
    "permission": BugCategory.PERMISSION_SECURITY_ERROR.value,
    "security": BugCategory.PERMISSION_SECURITY_ERROR.value,
    "permissionerror": BugCategory.PERMISSION_SECURITY_ERROR.value,
    "unauthorized": BugCategory.PERMISSION_SECURITY_ERROR.value,
    "forbidden": BugCategory.PERMISSION_SECURITY_ERROR.value,
    "authentication": BugCategory.PERMISSION_SECURITY_ERROR.value,
}


class TracebackPreprocessor:
    """Sanitizes, normalizes, and extracts features from raw error messages and tracebacks.
    
    Removes volatile environment noise (hex memory addresses, machine-specific file paths,
    dynamic line numbers, UUIDs, IP addresses) while strictly preserving diagnostic
    exception names, standard tokens, and error phrases.
    """

    # Pre-compiled regex patterns for sanitization
    RE_HEX_ADDR = re.compile(r"0x[0-9a-fA-F]+")
    RE_FILE_PATH = re.compile(r"([A-Za-z]:)?[/\\].+?[/\\]([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9_]+)")
    RE_LINE_NUM = re.compile(r"\bline \d+\b", re.IGNORECASE)
    RE_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
    RE_IP_ADDR = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?\b")
    RE_URL = re.compile(r"https?://\S+")
    RE_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?")

    # Retained exception classes that signal exact error types
    RE_EXCEPTION_CLASS = re.compile(r"\b([A-Z][a-zA-Z0-9]*(?:Error|Exception|Warning|Fault|Interrupt|Violation|Timeout|Denied|Failure))\b")

    def __init__(self):
        pass

    def clean_text(self, text: str) -> str:
        """Apply regex maskers to replace volatile identifiers with canonical placeholder tokens."""
        if not text or not isinstance(text, str):
            return ""

        # Normalize line breaks and tabs
        cleaned = text.replace("\r\n", "\n").replace("\t", " ")

        # Mask timestamps
        cleaned = self.RE_TIMESTAMP.sub(" <TIMESTAMP> ", cleaned)

        # Mask URLs
        cleaned = self.RE_URL.sub(" <URL> ", cleaned)

        # Mask IP addresses
        cleaned = self.RE_IP_ADDR.sub(" <IP_ADDR> ", cleaned)

        # Mask UUIDs
        cleaned = self.RE_UUID.sub(" <UUID> ", cleaned)

        # Mask memory hex addresses
        cleaned = self.RE_HEX_ADDR.sub(" <HEX_ADDR> ", cleaned)

        # Mask file paths while retaining filename
        def replace_file_path(match: re.Match) -> str:
            filename = match.group(2)
            return f" <FILE_PATH>/{filename} "

        cleaned = self.RE_FILE_PATH.sub(replace_file_path, cleaned)

        # Mask line numbers
        cleaned = self.RE_LINE_NUM.sub(" line <LINE_NUM> ", cleaned)

        # Collapse excessive whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def extract_exception_names(self, text: str) -> List[str]:
        """Extract explicit exception classes occurring in the text."""
        if not text:
            return []
        return self.RE_EXCEPTION_CLASS.findall(text)

    def preprocess(self, error_message: str, traceback: Optional[str] = None) -> str:
        """Combine error message and traceback into a single sanitized text representation."""
        parts = []
        if error_message:
            parts.append(self.clean_text(error_message))
        if traceback:
            parts.append(self.clean_text(traceback))

        combined = " ".join(parts).strip()
        return combined

    @classmethod
    def normalize_category(cls, category: str) -> str:
        """Map raw or legacy category names to canonical BugCategory values."""
        if not category:
            return BugCategory.RUNTIME_LOGIC_ERROR.value

        cleaned = category.strip().lower()
        if BugCategory.is_valid(cleaned):
            return cleaned

        # Strip prefixes like "CAT_1_" or "cat_"
        cleaned_no_cat = re.sub(r"^cat_\d+_", "", cleaned)
        if BugCategory.is_valid(cleaned_no_cat):
            return cleaned_no_cat

        if cleaned in LEGACY_CATEGORY_MAPPINGS:
            return LEGACY_CATEGORY_MAPPINGS[cleaned]

        # Key substring matches
        for key, val in LEGACY_CATEGORY_MAPPINGS.items():
            if key in cleaned:
                return val

        return BugCategory.RUNTIME_LOGIC_ERROR.value
