"""Dataset loader, curator, and stratified partitioner for Bug Classification ML Engine."""
import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from app.ml.preprocessor import BugCategory


DATA_DIR = Path(__file__).parent
DATASET_JSONL = DATA_DIR / "bug_tracebacks.jsonl"
DATASET_CSV = DATA_DIR / "bug_tracebacks.csv"


# Comprehensive curated seed examples for all 8 canonical categories
SEED_DATA: List[Dict[str, str]] = [
    # -------------------------------------------------------------------------
    # 1. syntax_error
    # -------------------------------------------------------------------------
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: invalid syntax",
        "traceback": '  File "/workspace/app/services/parser.py", line 42\n    def parse_item(data):\n                        ^\nSyntaxError: invalid syntax',
        "context": "Missing colon or illegal character at function declaration",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "IndentationError: unexpected indent",
        "traceback": '  File "/workspace/app/core/config.py", line 18\n        self.timeout = 30\nIndentationError: unexpected indent',
        "context": "Misaligned indentation block in class definition",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: unexpected EOF while parsing",
        "traceback": '  File "/workspace/app/utils/helpers.py", line 105\n    if not items:\n                 ^\nSyntaxError: unexpected EOF while parsing',
        "context": "File ended with open parenthesis or incomplete statement",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: closing parenthesis ')' does not match opening parenthesis '['",
        "traceback": '  File "/workspace/app/models/schema.py", line 64\n    items = [x for x in data)\n                            ^\nSyntaxError: closing parenthesis \')\' does not match opening parenthesis \'[\'',
        "context": "Mismatched bracket/parenthesis syntax",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: cannot assign to expression here. Maybe you meant '==' instead of '='?",
        "traceback": '  File "/workspace/app/auth/validator.py", line 29\n    if user.status = "ACTIVE":\n       ^^^^^^^^^^^^^^^^^^^^^^\nSyntaxError: cannot assign to expression here. Maybe you meant \'==\' instead of \'=\'?',
        "context": "Assignment used in conditional expression",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "IndentationError: expected an indented block after 'for' statement on line 55",
        "traceback": '  File "/workspace/app/pipelines/runner.py", line 56\n    print("done")\nIndentationError: expected an indented block after \'for\' statement on line 55',
        "context": "Empty loop body without pass statement",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: f-string: unmatched '{'",
        "traceback": '  File "/workspace/app/views/templates.py", line 83\n    msg = f"User {user.name has joined"\n                                      ^\nSyntaxError: f-string: unmatched \'{\'',
        "context": "Unclosed f-string expression",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: positional argument follows keyword argument",
        "traceback": '  File "/workspace/app/clients/http.py", line 37\n    fetch(url="https://api.internal", headers, timeout=10)\n                                      ^^^^^^^\nSyntaxError: positional argument follows keyword argument',
        "context": "Invalid function call argument order",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: non-default argument follows default argument",
        "traceback": '  File "/workspace/app/services/calculator.py", line 12\n    def compute(base=10, multiplier, offset=0):\n                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\nSyntaxError: non-default argument follows default argument',
        "context": "Invalid signature default parameter positioning",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "TabError: inconsistent use of tabs and spaces in indentation",
        "traceback": '  File "/workspace/app/legacy/worker.py", line 91\n    return results\nTabError: inconsistent use of tabs and spaces in indentation',
        "context": "Mixed tab and space characters in code block",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: invalid decimal literal",
        "traceback": '  File "/workspace/app/utils/format.py", line 5\n    v = 0123\n        ^\nSyntaxError: leading zeros in decimal integer literals are not permitted; use an 0o prefix for octal integers',
        "context": "Invalid octal integer literal",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: unmatched ')'",
        "traceback": '  File "/workspace/app/metrics/timer.py", line 22\n    return (a + b))\n                  ^\nSyntaxError: unmatched \')\'',
        "context": "Extra closing parenthesis in return statement",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: 'return' outside function",
        "traceback": '  File "/workspace/app/scripts/setup.py", line 14\n    return False\n    ^^^^^^^^^^^^\nSyntaxError: \'return\' outside function',
        "context": "Top-level return statement outside callable body",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: 'break' outside loop",
        "traceback": '  File "/workspace/app/dispatch/event.py", line 47\n    if not event:\n        break\n        ^^^^^\nSyntaxError: \'break\' outside loop',
        "context": "Break statement placed inside if branch not in a loop",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: trailing comma not allowed without surrounding parentheses in type annotation",
        "traceback": '  File "/workspace/app/types/defs.py", line 33\n    x: int, str = 1\n          ^\nSyntaxError: invalid syntax',
        "context": "Malformed type annotation declaration",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: Generator expression must be parenthesized",
        "traceback": '  File "/workspace/app/handlers/stream.py", line 19\n    consume(x * 2 for x in items, True)\n            ^^^^^^^^^^^^^^^^^^^^\nSyntaxError: Generator expression must be parenthesized',
        "context": "Unparenthesized generator passed to multi-argument function",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: duplicate argument 'user_id' in function definition",
        "traceback": '  File "/workspace/app/routes/users.py", line 8\n    def get_user(user_id: int, user_id: str):\n                                ^^^^^^^\nSyntaxError: duplicate argument \'user_id\' in function definition',
        "context": "Duplicate parameter name in definition signature",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: invalid syntax at EOF in string literal",
        "traceback": '  File "/workspace/app/templates/email.py", line 44\n    body = """Welcome to Devora AI\n                                  ^\nSyntaxError: unterminated triple-quoted string literal (detected at line 44)',
        "context": "Unclosed multi-line triple quoted string",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: cannot use 'yield' inside async generator expression",
        "traceback": '  File "/workspace/app/async_tools/iter.py", line 77\n    res = (yield x async for x in stream)\n           ^^^^^^^\nSyntaxError: \'yield\' inside generator expression',
        "context": "Invalid yield keyword placement",
    },
    {
        "category": BugCategory.SYNTAX_ERROR.value,
        "error_message": "SyntaxError: 'continue' not properly in loop",
        "traceback": '  File "/workspace/app/logic/filter.py", line 29\n    try:\n        continue\n        ^^^^^^^^\nSyntaxError: \'continue\' not properly in loop',
        "context": "Continue statement invalidly scoped outside iteration loop",
    },

    # -------------------------------------------------------------------------
    # 2. import_dependency_error
    # -------------------------------------------------------------------------
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ModuleNotFoundError: No module named 'fastapi'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/main.py", line 3, in <module>\n    import fastapi\nModuleNotFoundError: No module named \'fastapi\'',
        "context": "Missing top-level framework dependency in virtualenv",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ImportError: cannot import name 'AsyncSession' from 'sqlalchemy.orm'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/session.py", line 4, in <module>\n    from sqlalchemy.orm import AsyncSession\nImportError: cannot import name \'AsyncSession\' from \'sqlalchemy.orm\'',
        "context": "Wrong submodule path or out-of-date library version",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ModuleNotFoundError: No module named 'pgvector.sqlalchemy'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/models/memory.py", line 8, in <module>\n    from pgvector.sqlalchemy import Vector\nModuleNotFoundError: No module named \'pgvector.sqlalchemy\'',
        "context": "Uninstalled pgvector extension package",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ImportError: cannot import name 'Settings' from partially initialized module 'app.config' (most likely due to a circular import)",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/main.py", line 5, in <module>\n    from app.config import Settings\n  File "/workspace/app/config.py", line 2, in <module>\n    from app.main import app\nImportError: cannot import name \'Settings\' from partially initialized module \'app.config\' (most likely due to a circular import)',
        "context": "Circular dependency deadlock during module evaluation",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ModuleNotFoundError: No module named 'scipy'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/ml/classifier.py", line 2, in <module>\n    import scipy.sparse\nModuleNotFoundError: No module named \'scipy\'',
        "context": "Missing scientific compute dependency",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ImportError: cannot import name 'BaseModel' from 'pydantic'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/schemas/task.py", line 1, in <module>\n    from pydantic import BaseModel\nImportError: cannot import name \'BaseModel\' from \'pydantic\'',
        "context": "Pydantic version conflict or shadowed local file named pydantic.py",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ModuleNotFoundError: No module named 'tree_sitter_python'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/ast.py", line 6, in <module>\n    import tree_sitter_python\nModuleNotFoundError: No module named \'tree_sitter_python\'',
        "context": "Missing grammar parser dependency",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ImportError: libgomp.so.1: cannot open shared object file: No such file or directory",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/ml/engine.py", line 4, in <module>\n    import sklearn\n  File "/workspace/.venv/lib/python3.11/site-packages/sklearn/__init__.py", line 82, in <module>\n    from . import _distributor_init\nImportError: libgomp.so.1: cannot open shared object file: No such file or directory',
        "context": "Missing shared system native library for compiled C extension",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ModuleNotFoundError: No module named 'langgraph.checkpoint.base'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/agents/graph.py", line 3, in <module>\n    from langgraph.checkpoint.base import BaseCheckpointSaver\nModuleNotFoundError: No module named \'langgraph.checkpoint.base\'',
        "context": "LangGraph subpackage reorganized or missing version upgrade",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ImportError: cannot import name 'field_validator' from 'pydantic' (did you mean 'validator'?)",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/schemas/project.py", line 3, in <module>\n    from pydantic import field_validator\nImportError: cannot import name \'field_validator\' from \'pydantic\'',
        "context": "Using Pydantic v2 field_validator on older Pydantic v1 install",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ModuleNotFoundError: No module named 'google.genai'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/agents/gateway.py", line 5, in <module>\n    import google.genai as genai\nModuleNotFoundError: No module named \'google.genai\'',
        "context": "Google GenAI SDK package uninstalled",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ImportError: cannot import name 'urllib3' from 'requests.packages'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/tools/fetcher.py", line 7, in <module>\n    from requests.packages import urllib3\nImportError: cannot import name \'urllib3\' from \'requests.packages\'',
        "context": "Vendored urllib3 removal in newer requests versions",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ModuleNotFoundError: No module named 'alembic.migration'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/migrate.py", line 2, in <module>\n    from alembic.migration import MigrationContext\nModuleNotFoundError: No module named \'alembic.migration\'',
        "context": "Missing database migration toolchain",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ImportError: dynamic module does not define module export function (PyInit__rust)",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/core/crypto.py", line 4, in <module>\n    import cryptography.hazmat.bindings._rust\nImportError: dynamic module does not define module export function',
        "context": "Binary architecture mismatch in compiled C/Rust extension",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ModuleNotFoundError: No module named 'structlog'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/core/logging.py", line 4, in <module>\n    import structlog\nModuleNotFoundError: No module named \'structlog\'',
        "context": "Structured logging library absent from environment",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ImportError: cannot import name 'HTTP_200_OK' from 'starlette.status'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/api/endpoints.py", line 5, in <module>\n    from starlette.status import HTTP_200_OK\nImportError: cannot import name \'HTTP_200_OK\' from \'starlette.status\'',
        "context": "Deprecated or shadowed starlette module",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ModuleNotFoundError: No module named 'pytest_asyncio'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/tests/conftest.py", line 3, in <module>\n    import pytest_asyncio\nModuleNotFoundError: No module named \'pytest_asyncio\'',
        "context": "Asynchronous test runner plugin missing",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ImportError: attempted relative import with no known parent package",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/models/user.py", line 2, in <module>\n    from ..core.base import Base\nImportError: attempted relative import with no known parent package',
        "context": "Executing submodule directly as script breaking relative imports",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ModuleNotFoundError: No module named 'asyncpg.pgproto'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/connection.py", line 6, in <module>\n    import asyncpg.pgproto.types\nModuleNotFoundError: No module named \'asyncpg.pgproto\'',
        "context": "Corrupted or missing asyncpg binary wheels",
    },
    {
        "category": BugCategory.IMPORT_DEPENDENCY_ERROR.value,
        "error_message": "ImportError: version conflict: package 'tenacity>=9.0.0' required but 8.2.3 is installed",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/retry.py", line 1, in <module>\n    import tenacity\nImportError: version conflict: package \'tenacity>=9.0.0\' required but 8.2.3 is installed',
        "context": "Incompatible dependency version skew",
    },

    # -------------------------------------------------------------------------
    # 3. type_error
    # -------------------------------------------------------------------------
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: unsupported operand type(s) for +: 'int' and 'str'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/billing.py", line 45, in calculate_total\n    total = price + tax_rate\nTypeError: unsupported operand type(s) for +: \'int\' and \'str\'',
        "context": "Concatenation or arithmetic across incompatible integer and string types",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: get_project() missing 1 required positional argument: 'db'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/api/v1/projects.py", line 32, in handle_request\n    return await get_project(project_id)\nTypeError: get_project() missing 1 required positional argument: \'db\'',
        "context": "Missing required dependency injection parameter",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: 'int' object is not iterable",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/utils/batch.py", line 14, in process_all\n    for item in total_count:\nTypeError: \'int\' object is not iterable',
        "context": "Attempting to iterate over numeric integer value",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: object of type 'NoneType' has no len()",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/validator.py", line 22, in validate_payload\n    if len(payload) == 0:\nTypeError: object of type \'NoneType\' has no len()',
        "context": "Invoking len() on None",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: can only concatenate list (not 'tuple') to list",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/routes/items.py", line 58, in merge_results\n    combined = first_batch + second_batch\nTypeError: can only concatenate list (not \'tuple\') to list',
        "context": "Combining list and tuple via + operator without conversion",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: 'str' object cannot be interpreted as an integer",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/utils/pagination.py", line 11, in get_page\n    return items[slice_start:page_size]\nTypeError: \'str\' object cannot be interpreted as an integer',
        "context": "Passing string index slice into sequence",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: cannot unpack non-iterable int object",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/agents/eval.py", line 40, in evaluate\n    status, code = result\nTypeError: cannot unpack non-iterable int object',
        "context": "Destructuring assignment against single integer",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: issubclass() arg 1 must be a class",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/core/factory.py", line 19, in register_type\n    if issubclass(target, BaseService):\nTypeError: issubclass() arg 1 must be a class',
        "context": "Passing instance or primitive rather than type class",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: unhashable type: 'dict'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/cache/memo.py", line 15, in store_cache\n    seen_keys.add(filter_params)\nTypeError: unhashable type: \'dict\'',
        "context": "Using mutable dict inside set or as dictionary key",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: format() argument 1 must be string, not float",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/log.py", line 51, in log_stat\n    output = template.format(score)\nTypeError: format() argument 1 must be string, not float',
        "context": "Type mismatch in format parameter expectation",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: 'Coroutine' object is not subscriptable",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/handlers/async_task.py", line 63, in dispatch\n    item = fetch_data()["id"]\nTypeError: \'coroutine\' object is not subscriptable',
        "context": "Forgot to await async coroutine before subscripting result",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: json.dumps() argument must be a serializable type, got set",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/export.py", line 29, in to_json\n    return json.dumps(data)\nTypeError: Object of type set is not JSON serializable',
        "context": "JSON serializer encountered unhandled python set object",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: unhashable type: 'list'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/utils/dedup.py", line 8, in unique_items\n    return list(set(items_with_lists))\nTypeError: unhashable type: \'list\'',
        "context": "Attempting to create set from list containing nested lists",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/guards/check.py", line 14, in check_valid\n    if isinstance(val, [int, str]):\nTypeError: isinstance() arg 2 must be a type, a tuple of types, or a union',
        "context": "Passed a list instead of a tuple to isinstance()",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: not all arguments converted during string formatting",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/legacy/printer.py", line 33, in log_message\n    return "User: %s" % (name, user_id)\nTypeError: not all arguments converted during string formatting',
        "context": "Tuple length exceeds percent-formatting specifiers",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: 'float' object cannot be interpreted as an integer",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/models/matrix.py", line 47, in reshape\n    for idx in range(num_rows / 2):\nTypeError: \'float\' object cannot be interpreted as an integer',
        "context": "Floating point division result passed into range() instead of integer division",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: write() argument must be str, not bytes",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/io/writer.py", line 21, in dump_text\n    with open("out.txt", "w") as f: f.write(payload_bytes)\nTypeError: write() argument must be str, not bytes',
        "context": "Writing raw byte stream to text-mode file handle",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: An asyncio.Future, a coroutine or an awaitable is required but got int",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/async_tools/gather.py", line 12, in run_all\n    await asyncio.gather(42, fetch_worker())\nTypeError: An asyncio.Future, a coroutine or an awaitable is required',
        "context": "Passing primitive number to asyncio.gather",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: string indices must be integers, not 'str'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/api/client.py", line 38, in parse_response\n    token = response["auth"]["token"]\nTypeError: string indices must be integers, not \'str\'',
        "context": "String indexing using dictionary string key instead of deserializing JSON",
    },
    {
        "category": BugCategory.TYPE_ERROR.value,
        "error_message": "TypeError: slice indices must be integers or None or have an __index__ method",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/data/slicer.py", line 17, in slice_data\n    return data[start:end_val]\nTypeError: slice indices must be integers or None or have an __index__ method',
        "context": "Non-integer slice boundary index",
    },

    # -------------------------------------------------------------------------
    # 4. attribute_null_reference_error
    # -------------------------------------------------------------------------
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'id'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/project_service.py", line 78, in get_details\n    return {"id": project.id, "name": project.name}\nAttributeError: \'NoneType\' object has no attribute \'id\'',
        "context": "Query returned None and subsequent property access crashed",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'strip'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/utils/sanitizer.py", line 19, in clean_input\n    return text.strip().lower()\nAttributeError: \'NoneType\' object has no attribute \'strip\'',
        "context": "Calling string strip method on None variable",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'get'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/api/middleware.py", line 45, in authenticate\n    token = headers.get("Authorization")\nAttributeError: \'NoneType\' object has no attribute \'get\'',
        "context": "Optional request headers dictionary was None",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'Repository' object has no attribute 'primary_language'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/repo.py", line 61, in summarize\n    lang = repo.primary_language\nAttributeError: \'Repository\' object has no attribute \'primary_language\'',
        "context": "Misnamed ORM attribute or accessed unmapped column",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'commit'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/unit_of_work.py", line 33, in save_changes\n    await self.session.commit()\nAttributeError: \'NoneType\' object has no attribute \'commit\'',
        "context": "Uninitialized database session dereference",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'dict' object has no attribute 'username'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/service.py", line 52, in verify_user\n    print(user_data.username)\nAttributeError: \'dict\' object has no attribute \'username\'',
        "context": "Accessed dictionary key using dot notation attribute lookup",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'startswith'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/utils/path.py", line 12, in is_absolute\n    return file_path.startswith("/")\nAttributeError: \'NoneType\' object has no attribute \'startswith\'',
        "context": "Passing None to path validation method",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'read'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/io/reader.py", line 28, in read_file\n    content = handle.read()\nAttributeError: \'NoneType\' object has no attribute \'read\'',
        "context": "File descriptor handle opened as None",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'Task' object has no attribute 'execution_logs'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/views/tasks.py", line 104, in render\n    logs = task.execution_logs\nAttributeError: \'Task\' object has no attribute \'execution_logs\'',
        "context": "Non-existent relationship or deprecated attribute name",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'items'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/pipelines/parser.py", line 71, in extract\n    for k, v in config_dict.items():\nAttributeError: \'NoneType\' object has no attribute \'items\'',
        "context": "Iterating over missing optional configuration object",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'split'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/search/query.py", line 15, in tokenize\n    terms = raw_query.split()\nAttributeError: \'NoneType\' object has no attribute \'split\'',
        "context": "Missing query parameter defaulting to None instead of empty string",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'User' object has no attribute 'hashed_password'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/hasher.py", line 22, in check\n    return bcrypt.verify(password, user.hashed_password)\nAttributeError: \'User\' object has no attribute \'hashed_password\'',
        "context": "Schema attribute mismatch on user authentication model",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'scalars'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/repositories.py", line 40, in get_all\n    return result.scalars().all()\nAttributeError: \'NoneType\' object has no attribute \'scalars\'',
        "context": "Database query execute returned None on mocked session",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'group'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/ml/preprocessor.py", line 92, in extract\n    return match.group(1)\nAttributeError: \'NoneType\' object has no attribute \'group\'',
        "context": "Regex pattern failed to match and returned None before group() access",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'find'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/scraper/parse.py", line 55, in find_element\n    return soup.find("div", class_="content")\nAttributeError: \'NoneType\' object has no attribute \'find\'',
        "context": "Null document object dereference",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: module 'asyncio' has no attribute 'coroutine'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/legacy/async.py", line 8, in <module>\n    @asyncio.coroutine\nAttributeError: module \'asyncio\' has no attribute \'coroutine\'',
        "context": "Removed Python 3.11+ decorator attribute access",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'send'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/events/queue.py", line 49, in emit\n    self.producer.send(topic, payload)\nAttributeError: \'NoneType\' object has no attribute \'send\'',
        "context": "Disconnected message broker client handle",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'status_code'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/http/client.py", line 66, in verify_status\n    if resp.status_code == 200:\nAttributeError: \'NoneType\' object has no attribute \'status_code\'',
        "context": "HTTP client returned None on network error before status check",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'lower'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/filters/case.py", line 12, in to_case\n    return value.lower()\nAttributeError: \'NoneType\' object has no attribute \'lower\'',
        "context": "Calling lower() on missing nullable database column value",
    },
    {
        "category": BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'values'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/stats/aggregator.py", line 88, in sum_all\n    return sum(mapping.values())\nAttributeError: \'NoneType\' object has no attribute \'values\'',
        "context": "None passed to dictionary aggregator function",
    },

    # -------------------------------------------------------------------------
    # 5. index_key_error
    # -------------------------------------------------------------------------
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "IndexError: list index out of range",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/parsers/csv.py", line 41, in get_first_token\n    token = row[0]\nIndexError: list index out of range',
        "context": "Empty list indexed with zero or out-of-bounds offset",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "KeyError: 'user_id'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/jwt.py", line 29, in decode_token\n    return payload["user_id"]\nKeyError: \'user_id\'',
        "context": "Accessing missing required key from dictionary without .get()",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "IndexError: pop from empty list",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/structures/stack.py", line 18, in pop\n    return self.elements.pop()\nIndexError: pop from empty list',
        "context": "Calling pop() on empty sequence list",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "KeyError: 'api_key'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/config.py", line 55, in load_secrets\n    secret = os.environ["GEMINI_API_KEY"]\nKeyError: \'GEMINI_API_KEY\'',
        "context": "Missing required environment variable key in os.environ",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "IndexError: tuple index out of range",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/raw.py", line 67, in fetch_coords\n    lat, lon, alt = row[0], row[1], row[2]\nIndexError: tuple index out of range',
        "context": "Tuple had only 2 elements when 3 were requested",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "KeyError: 'status'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/workflow/state.py", line 83, in check_status\n    if task_dict["status"] == "COMPLETED":\nKeyError: \'status\'',
        "context": "Dictionary missing status field",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "IndexError: deque index out of range",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/queues/buffer.py", line 32, in peek\n    return self.window[5]\nIndexError: deque index out of range',
        "context": "Out-of-range index into collections.deque",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "KeyError: 'repository_id'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/api/v1/tasks.py", line 50, in create_task\n    repo_id = payload["repository_id"]\nKeyError: \'repository_id\'',
        "context": "Missing expected key in API body payload",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "IndexError: string index out of range",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/utils/initials.py", line 8, in get_initial\n    return name[0]\nIndexError: string index out of range',
        "context": "Indexing empty string at position 0",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "KeyError: 'default'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/models/registry.py", line 42, in get_model\n    return registry["default"]\nKeyError: \'default\'',
        "context": "Default profile not registered in lookup dict",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "IndexError: list assignment index out of range",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/matrices/grid.py", line 19, in set_cell\n    grid[row_idx][col_idx] = val\nIndexError: list assignment index out of range',
        "context": "Mutating element at non-existent list index",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "KeyError: 404",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/http/dispatcher.py", line 77, in dispatch_error\n    handler = handlers[response.status_code]\nKeyError: 404',
        "context": "Unregistered HTTP status code in error handler map",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "KeyError: 'Authorization'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/middleware.py", line 18, in parse_header\n    token = request.headers["Authorization"]\nKeyError: \'Authorization\'',
        "context": "Missing header key without exception handling",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "IndexError: single positional indexer is out-of-bounds",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/analytics/table.py", line 44, in get_row\n    return df.iloc[100]\nIndexError: single positional indexer is out-of-bounds',
        "context": "Pandas DataFrame row index out of bounds",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "KeyError: 'Content-Type'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/http.py", line 59, in get_media_type\n    return resp.headers["Content-Type"]\nKeyError: \'Content-Type\'',
        "context": "Missing Content-Type header in response dictionary",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "IndexError: index 10 is out of bounds for axis 0 with size 5",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/ml/vectors.py", line 26, in get_vector\n    return array[10]\nIndexError: index 10 is out of bounds for axis 0 with size 5',
        "context": "NumPy 1D array slice index exceeded array dimension",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "KeyError: 'embedding'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/agents/memory.py", line 37, in parse_memory\n    vec = memory_dict["embedding"]\nKeyError: \'embedding\'',
        "context": "Missing embedding vector attribute in JSON payload",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "KeyError: 'file_path'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/diff.py", line 15, in parse_diff\n    path = change["file_path"]\nKeyError: \'file_path\'',
        "context": "Missing file_path field in change event",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "IndexError: list index -1 out of range",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/utils/stack.py", line 11, in last_item\n    return items[-1]\nIndexError: list index -1 out of range',
        "context": "Indexing -1 on empty collection",
    },
    {
        "category": BugCategory.INDEX_KEY_ERROR.value,
        "error_message": "KeyError: 'refresh_token'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/tokens.py", line 82, in refresh_session\n    token = cookie_jar["refresh_token"]\nKeyError: \'refresh_token\'',
        "context": "Missing refresh token cookie entry",
    },

    # -------------------------------------------------------------------------
    # 6. runtime_logic_error
    # -------------------------------------------------------------------------
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "ZeroDivisionError: division by zero",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/analytics/metrics.py", line 63, in compute_rate\n    return success_count / total_runs\nZeroDivisionError: division by zero',
        "context": "Denominator variable total_runs evaluated to zero",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "RecursionError: maximum recursion depth exceeded while calling a Python object",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/structures/tree.py", line 92, in traverse\n    return self.traverse(node.child)\nRecursionError: maximum recursion depth exceeded while calling a Python object',
        "context": "Infinite cyclic recursion without base termination condition",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "AssertionError: Expected 200 OK but got 500 Internal Server Error",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/tests/test_api.py", line 48, in test_login\n    assert response.status_code == 200, f"Expected 200 OK but got {response.status_code}"\nAssertionError: Expected 200 OK but got 500 Internal Server Error',
        "context": "Unit test assertion failed due to unexpected response code",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "ValueError: invalid literal for int() with base 10: 'abc'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/parsers/int_parser.py", line 12, in to_int\n    return int(raw_string)\nValueError: invalid literal for int() with base 10: \'abc\'',
        "context": "Attempting to cast non-numeric alphanumeric string to integer",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "ZeroDivisionError: float division by zero",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/finance/margin.py", line 33, in profit_margin\n    return (revenue - cost) / revenue\nZeroDivisionError: float division by zero',
        "context": "Revenue zero condition unhandled in financial formula",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "AssertionError: assert False where False = is_verified(task)",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/tests/unit/test_task.py", line 89, in test_workflow\n    assert is_verified(task)\nAssertionError: assert False where False = is_verified(task)',
        "context": "Logical assertion check failed in business validation",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "ValueError: math domain error",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/math/calc.py", line 15, in compute_log\n    return math.log(negative_val)\nValueError: math domain error',
        "context": "Logarithm computed on non-positive input parameter",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "RuntimeError: Set changed size during iteration",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/session_cleaner.py", line 41, in purge\n    for session in active_sessions:\nRuntimeError: Set changed size during iteration',
        "context": "Mutating collection while actively iterating over it",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "ValueError: not enough values to unpack (expected 3, got 2)",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/parsers/csv.py", line 25, in parse_line\n    a, b, c = line.split(",")\nValueError: not enough values to unpack (expected 3, got 2)',
        "context": "Split produced fewer tokens than destructuring variables",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "RecursionError: maximum recursion depth exceeded in comparison",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/models/node.py", line 18, in __eq__\n    return self.parent == other.parent\nRecursionError: maximum recursion depth exceeded in comparison',
        "context": "Infinite recursion in __eq__ method comparing cyclic graph nodes",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "AssertionError: expected array length 10 but got 0",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/tests/test_search.py", line 102, in test_results\n    assert len(results) == 10, f"expected array length 10 but got {len(results)}"\nAssertionError: expected array length 10 but got 0',
        "context": "Empty results returned when test expected 10 items",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "RuntimeError: Event loop is closed",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/async_tools/loop.py", line 33, in execute\n    asyncio.run(cleanup())\nRuntimeError: Event loop is closed',
        "context": "Attempted async task invocation on terminated event loop",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "ValueError: too many values to unpack (expected 2)",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/utils/split.py", line 19, in split_kv\n    k, v = item.split("=")\nValueError: too many values to unpack (expected 2)',
        "context": "String contained multiple delimiter occurrences",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "ZeroDivisionError: integer division or modulo by zero",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/math/hash.py", line 7, in get_bucket\n    return key % num_buckets\nZeroDivisionError: integer division or modulo by zero',
        "context": "Modulo hash operation with zero bucket count",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "AssertionError: diff check failed: applied patch did not match target file",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/patcher.py", line 88, in apply\n    assert content == expected, "diff check failed: applied patch did not match target file"\nAssertionError: diff check failed: applied patch did not match target file',
        "context": "Patch application checksum validation mismatch",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "RuntimeError: maximum iteration limit 1000 reached without convergence",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/algorithms/solver.py", line 62, in solve\n    raise RuntimeError("maximum iteration limit 1000 reached without convergence")\nRuntimeError: maximum iteration limit 1000 reached without convergence',
        "context": "Numerical solver failed to converge within bounded iterations",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "ValueError: Unknown task type: 'invalid_type'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/agents/orchestrator.py", line 95, in route\n    raise ValueError(f"Unknown task type: {task_type}")\nValueError: Unknown task type: \'invalid_type\'',
        "context": "Enum validation check encountered unsupported string input",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "AssertionError: Test failed: expected exit code 0 but got 1",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/tests/integration/test_runner.py", line 37, in test_exec\n    assert exit_code == 0\nAssertionError: assert 1 == 0',
        "context": "Process execution exited with non-zero status code",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "ValueError: unconverted data remains: ' 12:00:00'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/utils/date.py", line 14, in parse_iso\n    return datetime.strptime(val, "%Y-%m-%d")\nValueError: unconverted data remains: \' 12:00:00\'',
        "context": "Date format string missing time component specifiers",
    },
    {
        "category": BugCategory.RUNTIME_LOGIC_ERROR.value,
        "error_message": "OverflowError: int too large to convert to float",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/math/huge.py", line 29, in to_float\n    return float(2 ** 2048)\nOverflowError: int too large to convert to float',
        "context": "Arithmetic exponent overflow beyond double precision limit",
    },

    # -------------------------------------------------------------------------
    # 7. database_network_error
    # -------------------------------------------------------------------------
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "asyncpg.exceptions.CannotConnectNowError: connection to server on socket failed: Connection refused",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/session.py", line 55, in get_session\n    conn = await asyncpg.connect("postgresql://postgres:secret@localhost:5432/devora")\nasyncpg.exceptions.CannotConnectNowError: connection to server on socket "/tmp/.s.PGSQL.5432" failed: Connection refused',
        "context": "PostgreSQL service daemon is not running or listening on target port",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "sqlalchemy.exc.IntegrityError: (sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) duplicate key value violates unique constraint 'uq_users_email'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/user_service.py", line 42, in register\n    await db.commit()\nsqlalchemy.exc.IntegrityError: (sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) duplicate key value violates unique constraint \'uq_users_email\'\nDETAIL: Key (email)=(test@example.com) already exists.',
        "context": "Unique database column constraint violation on user registration",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "httpx.ConnectError: [Errno 61] Connection refused",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/github.py", line 73, in fetch_repo\n    resp = await client.get("https://api.github.com/repos/org/repo")\nhttpx.ConnectError: [Errno 61] Connection refused',
        "context": "Outbound HTTP request failed due to offline host or firewall block",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "sqlalchemy.exc.OperationalError: (asyncpg.exceptions.DeadlockDetectedError) deadlock detected",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/transaction.py", line 112, in execute_transfer\n    await db.execute(update_stmt)\nsqlalchemy.exc.OperationalError: (asyncpg.exceptions.DeadlockDetectedError) deadlock detected\nDETAIL: Process 1849 waits for ExclusiveLock on relation; blocked by process 1850.',
        "context": "Concurrent conflicting transactions blocked in database deadlock",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "httpx.ReadTimeout: The read operation timed out",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/agents/gateway.py", line 88, in call_api\n    response = await client.post("https://generativelanguage.googleapis.com", timeout=30.0)\nhttpx.ReadTimeout: The read operation timed out',
        "context": "Upstream LLM API server did not return response within timeout window",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "sqlalchemy.exc.ProgrammingError: (asyncpg.exceptions.UndefinedTableError) relation 'repository_memories' does not exist",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/memory_service.py", line 67, in search_memories\n    res = await db.execute(stmt)\nsqlalchemy.exc.ProgrammingError: (asyncpg.exceptions.UndefinedTableError) relation \'repository_memories\' does not exist',
        "context": "Alembic migration has not been applied to database instance",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "asyncpg.exceptions.TooManyConnectionsError: sorry, too many clients already",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/pool.py", line 39, in acquire\n    conn = await pool.acquire()\nasyncpg.exceptions.TooManyConnectionsError: sorry, too many clients already',
        "context": "PostgreSQL connection pool exhausted by unreleased client connections",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "socket.gaierror: [Errno 8] nodename nor servname provided, or not known",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/clients/dns.py", line 14, in resolve\n    addr = socket.gethostbyname("api.nonexistent-service.internal")\nsocket.gaierror: [Errno 8] nodename nor servname provided, or not known',
        "context": "DNS hostname resolution failure for backend internal service",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "sqlalchemy.exc.DataError: (asyncpg.exceptions.DataError) different vector dimensions 768 and 1536",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/vector.py", line 45, in insert_vector\n    await db.execute(insert_stmt)\nsqlalchemy.exc.DataError: (asyncpg.exceptions.DataError) different vector dimensions 768 and 1536',
        "context": "Pgvector dimension mismatch between model embedding and table column definition",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "httpx.ConnectTimeout: timed out while connecting to host",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/webhook/notifier.py", line 22, in notify\n    await client.post("https://hooks.slack.com/services/xxx", timeout=5.0)\nhttpx.ConnectTimeout: timed out while connecting to host',
        "context": "Network connection handshake timed out",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "sqlalchemy.exc.IntegrityError: insert or update on table 'tasks' violates foreign key constraint 'fk_tasks_repository_id'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/task_service.py", line 58, in create_task\n    await db.commit()\nsqlalchemy.exc.IntegrityError: insert or update on table \'tasks\' violates foreign key constraint \'fk_tasks_repository_id\'\nDETAIL: Key (repository_id)=(99999) is not present in table \'repositories\'.',
        "context": "Referenced repository row does not exist in parent table",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "asyncpg.exceptions.InvalidPasswordError: password authentication failed for user 'devora'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/auth.py", line 19, in connect\n    conn = await asyncpg.connect(user="devora", password="bad")\nasyncpg.exceptions.InvalidPasswordError: password authentication failed for user \'devora\'',
        "context": "Incorrect database credential provided in connection string",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "httpx.RemoteProtocolError: Server disconnected without sending a response",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/api/stream.py", line 33, in stream_response\n    async for chunk in resp.aiter_bytes():\nhttpx.RemoteProtocolError: Server disconnected without sending a response',
        "context": "Upstream server terminated TCP connection mid-stream",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "sqlalchemy.exc.DBAPIError: connection closed abruptly by server",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/query.py", line 82, in run_query\n    await db.execute(select(User))\nsqlalchemy.exc.DBAPIError: connection closed abruptly by server',
        "context": "Database server restart or severed connection during query execution",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "redis.exceptions.ConnectionError: Error 61 connecting to localhost:6379. Connection refused.",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/cache/redis.py", line 24, in ping\n    await r.ping()\nredis.exceptions.ConnectionError: Error 61 connecting to localhost:6379. Connection refused.',
        "context": "Redis cache server is offline or unreachable",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "sqlalchemy.exc.InternalError: current transaction is aborted, commands ignored until end of transaction block",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/flow.py", line 91, in next_step\n    await db.execute(stmt)\nsqlalchemy.exc.InternalError: current transaction is aborted, commands ignored until end of transaction block',
        "context": "Query executed on dirty aborted transaction before rollback",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "asyncpg.exceptions.QueryCanceledError: canceling statement due to statement timeout",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/reports/analytics.py", line 120, in run_heavy_report\n    res = await db.execute(long_query)\nasyncpg.exceptions.QueryCanceledError: canceling statement due to statement timeout',
        "context": "Long-running analytical query killed by PostgreSQL statement timeout",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "httpx.HTTPStatusError: Server error '502 Bad Gateway' for url 'https://gateway.internal/v1/inference'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/proxy.py", line 47, in call_proxy\n    resp.raise_for_status()\nhttpx.HTTPStatusError: Server error \'502 Bad Gateway\' for url \'https://gateway.internal/v1/inference\'',
        "context": "Reverse proxy failed to receive valid response from upstream container",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "sqlalchemy.exc.OperationalError: server closed the connection unexpectedly",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/db/alive.py", line 14, in check_health\n    await db.execute(text("SELECT 1"))\nsqlalchemy.exc.OperationalError: server closed the connection unexpectedly',
        "context": "PostgreSQL engine killed or severed client socket",
    },
    {
        "category": BugCategory.DATABASE_NETWORK_ERROR.value,
        "error_message": "urllib3.exceptions.MaxRetryError: HTTPSConnectionPool(host='api.github.com', port=443): Max retries exceeded with url: /user",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/github.py", line 38, in verify_token\n    res = requests.get("https://api.github.com/user")\nurllib3.exceptions.MaxRetryError: HTTPSConnectionPool(host=\'api.github.com\', port=443): Max retries exceeded with url: /user',
        "context": "Exceeded maximum retry attempts connecting to remote GitHub API",
    },

    # -------------------------------------------------------------------------
    # 8. permission_security_error
    # -------------------------------------------------------------------------
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "PermissionError: [Errno 13] Permission denied: '/var/log/devora/app.log'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/core/logging.py", line 45, in configure_file_handler\n    with open("/var/log/devora/app.log", "a") as f:\nPermissionError: [Errno 13] Permission denied: \'/var/log/devora/app.log\'',
        "context": "Non-root process lacks write permission to root-owned directory",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "jwt.exceptions.ExpiredSignatureError: Signature has expired",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/tokens.py", line 55, in verify_jwt\n    payload = jwt.decode(token, secret, algorithms=["HS256"])\njwt.exceptions.ExpiredSignatureError: Signature has expired',
        "context": "Bearer JWT token expiration timestamp is in the past",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "fastapi.HTTPException: 403: Forbidden - user does not have write access to this repository",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/api/v1/projects.py", line 98, in update_repo\n    raise HTTPException(status_code=403, detail="Forbidden - user does not have write access to this repository")\nfastapi.HTTPException: 403: Forbidden - user does not have write access to this repository',
        "context": "User role lacks required RBAC permission for mutating repository",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "jwt.exceptions.InvalidSignatureError: Signature verification failed",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/tokens.py", line 61, in verify_jwt\n    payload = jwt.decode(token, secret, algorithms=["HS256"])\njwt.exceptions.InvalidSignatureError: Signature verification failed',
        "context": "Tampered token or mismatched cryptographic secret key",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "fastapi.HTTPException: 401: Unauthorized - invalid or missing credentials",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/core/auth_middleware.py", line 33, in check_auth\n    raise HTTPException(status_code=401, detail="Unauthorized - invalid or missing credentials")\nfastapi.HTTPException: 401: Unauthorized - invalid or missing credentials',
        "context": "Missing Authorization Bearer token header in API request",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "PermissionError: [Errno 1] Operation not permitted",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/sandbox/runner.py", line 87, in isolate_namespace\n    os.chroot("/isolated/jail")\nPermissionError: [Errno 1] Operation not permitted',
        "context": "Sandboxed process attempted privileged chroot operation",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "jwt.exceptions.DecodeError: Not enough segments",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/tokens.py", line 49, in decode_token\n    payload = jwt.decode(token_str, "secret", algorithms=["HS256"])\njwt.exceptions.DecodeError: Not enough segments',
        "context": "Malformed JWT missing header, payload, or signature segments",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "PermissionError: Read-only file system: '/app/secrets/master.key'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/crypto/keys.py", line 22, in rotate_key\n    with open("/app/secrets/master.key", "w") as f: f.write(new_key)\nPermissionError: Read-only file system: \'/app/secrets/master.key\'',
        "context": "Attempting write modification to read-only mounted container volume",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "SecurityException: Attempted directory traversal attack via '../etc/passwd'",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/services/sandbox.py", line 40, in safe_path\n    raise SecurityException("Attempted directory traversal attack via \'../etc/passwd\'")\nSecurityException: Attempted directory traversal attack via \'../etc/passwd\'',
        "context": "Path sanitizer caught attempted escape outside workspace sandbox root",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "fastapi.HTTPException: 403: Tenant mismatch - resource belongs to another organization",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/api/guards.py", line 51, in verify_tenant\n    raise HTTPException(status_code=403, detail="Tenant mismatch - resource belongs to another organization")\nfastapi.HTTPException: 403: Tenant mismatch - resource belongs to another organization',
        "context": "Cross-tenant resource access blocked by authorization guard",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "PermissionError: [Errno 13] Permission denied to bind to port 80",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/server.py", line 18, in run\n    sock.bind(("0.0.0.0", 80))\nPermissionError: [Errno 13] Permission denied',
        "context": "Binding privileged port (< 1024) without root privileges",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "jwt.exceptions.InvalidTokenError: Invalid token algorithm",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/verifier.py", line 37, in verify\n    jwt.decode(token, key, algorithms=["RS256"])\njwt.exceptions.InvalidTokenError: The specified alg value is not allowed',
        "context": "Mismatched signature algorithm or 'none' algorithm bypass attempt",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "PermissionError: access denied by security sandbox policy",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/sandbox/policy.py", line 72, in execute_command\n    raise PermissionError("access denied by security sandbox policy")\nPermissionError: access denied by security sandbox policy',
        "context": "Command execution prohibited by Devora sandbox security whitelist",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "fastapi.HTTPException: 401: Invalid session or session revoked",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/api/v1/auth.py", line 110, in me\n    raise HTTPException(status_code=401, detail="Invalid session or session revoked")\nfastapi.HTTPException: 401: Invalid session or session revoked',
        "context": "User session token invalidated or revoked in backend store",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "PermissionError: write access to protected branch 'main' requires pull request approval",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/git/push.py", line 44, in push_branch\n    raise PermissionError("write access to protected branch \'main\' requires pull request approval")\nPermissionError: write access to protected branch \'main\' requires pull request approval',
        "context": "Branch protection rule prevented direct branch push",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "SecurityException: API token contains unauthorized scopes for target resource",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/scopes.py", line 29, in enforce\n    raise SecurityException("API token contains unauthorized scopes for target resource")\nSecurityException: API token contains unauthorized scopes for target resource',
        "context": "OAuth token lacks repo:admin scope",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "PermissionError: [Errno 13] cannot execute binary file: Permission denied",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/sandbox/exec.py", line 50, in run_binary\n    subprocess.run(["/bin/custom_tool"])\nPermissionError: [Errno 13] Permission denied',
        "context": "Target binary lacks executable bit permissions (+x)",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "fastapi.HTTPException: 403: Forbidden - IP address not in allowlist",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/security/ip_filter.py", line 25, in filter_ip\n    raise HTTPException(status_code=403, detail="Forbidden - IP address not in allowlist")\nfastapi.HTTPException: 403: Forbidden - IP address not in allowlist',
        "context": "Client IP rejected by network security firewall",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "jwt.exceptions.InvalidAudienceError: Invalid audience",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/auth/oauth.py", line 63, in check_aud\n    jwt.decode(token, secret, audience="https://devora.ai")\njwt.exceptions.InvalidAudienceError: Invalid audience',
        "context": "JWT aud claim mismatch against target audience identifier",
    },
    {
        "category": BugCategory.PERMISSION_SECURITY_ERROR.value,
        "error_message": "PermissionError: cannot open socket on restricted loopback interface",
        "traceback": 'Traceback (most recent call last):\n  File "/workspace/app/net/socket.py", line 33, in open_raw\n    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)\nPermissionError: [Errno 1] Operation not permitted',
        "context": "Creating raw network socket requires elevated root capability",
    },
]


class DatasetManager:
    """Manages the lifecycle of curated bug classification datasets."""

    def __init__(self, data_path: Optional[Path] = None):
        self.data_dir = data_path or DATA_DIR
        self.jsonl_path = self.data_dir / "bug_tracebacks.jsonl"
        self.csv_path = self.data_dir / "bug_tracebacks.csv"

    def ensure_seed_dataset(self) -> None:
        """Initialize JSONL and CSV files with seed corpus if they do not exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.jsonl_path.exists():
            with open(self.jsonl_path, "w", encoding="utf-8") as f:
                for item in SEED_DATA:
                    f.write(json.dumps(item) + "\n")

        if not self.csv_path.exists():
            with open(self.csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["category", "error_message", "traceback", "context"]
                )
                writer.writeheader()
                for item in SEED_DATA:
                    writer.writerow(item)

    def load_dataset(self) -> List[Dict[str, str]]:
        """Load and return all validated examples from JSONL."""
        self.ensure_seed_dataset()
        items: List[Dict[str, str]] = []
        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    if BugCategory.is_valid(item.get("category", "")):
                        items.append(item)
        return items

    def add_sample(
        self,
        category: str,
        error_message: str,
        traceback: str,
        context: str = "",
    ) -> bool:
        """Add a new validated sample to the candidate dataset with duplicate checking."""
        if not BugCategory.is_valid(category):
            return False

        existing = self.load_dataset()
        # Check duplicate by error_message + traceback prefix
        for item in existing:
            if (
                item["category"] == category
                and item["error_message"].strip() == error_message.strip()
                and item["traceback"][:100] == traceback[:100]
            ):
                return False  # Duplicate

        new_item = {
            "category": category,
            "error_message": error_message,
            "traceback": traceback,
            "context": context,
        }

        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(new_item) + "\n")

        with open(self.csv_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["category", "error_message", "traceback", "context"]
            )
            writer.writerow(new_item)

        return True

    def get_class_distribution(self) -> Dict[str, int]:
        """Return counts per canonical bug category."""
        items = self.load_dataset()
        dist = {c.value: 0 for c in BugCategory}
        for item in items:
            cat = item.get("category")
            if cat in dist:
                dist[cat] += 1
        return dist
