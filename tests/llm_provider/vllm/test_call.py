# python -m pytest -s .\tests/llm_provider/vllm/test_call.py
import pytest

from src.llm_provider.vllm import VLLMProvider


@pytest.mark.asyncio
async def test_example(auth_client):
    """

    """

    data = {'messages': [{'role': 'system',
                          'content': '<important_rules>\n  You are in agent mode.\n\n  If you need to use multiple tools, you can call multiple read-only tools simultaneously.\n\n  Always include the language and file name in the info string when you write code blocks.\n  If you are editing "src/main.py" for example, your code block should start with \'```python src/main.py\'\n\n\nFor larger codeblocks (>20 lines), use brief language-appropriate placeholders for unmodified sections, e.g. \'// ... existing code ...\'\n\nHowever, only output codeblocks for suggestion and demonstration purposes, for example, when enumerating multiple hypothetical options. For implementing changes, use the edit tools.\n\n</important_rules>'},
                         {'role': 'user', 'content': '안녕하세요 현재 미국 대통령이 누군가요?'}], 'model': 'openai/gpt-oss-120b', 'max_tokens': 4096,
            'tools': [{'type': 'function', 'function': {'name': 'read_file',
                                                        'description': 'Use this tool if you need to view the contents of an existing file.',
                                                        'parameters': {'type': 'object',
                                                                       'required': ['filepath'],
                                                                       'properties': {'filepath': {
                                                                           'type': 'string',
                                                                           'description': 'The path of the file to read. Can be a relative path (from workspace root), absolute path, tilde path (~/...), or file:// URI'}}}}},
                      {'type': 'function', 'function': {'name': 'create_new_file',
                                                        'description': "Create a new file. Only use this when a file doesn't exist and should be created",
                                                        'parameters': {'type': 'object',
                                                                       'required': ['filepath',
                                                                                    'contents'],
                                                                       'properties': {'filepath': {
                                                                           'type': 'string',
                                                                           'description': 'The path where the new file should be created. Can be a relative path (from workspace root), absolute path, tilde path (~/...), or file:// URI.'},
                                                                           'contents': {
                                                                               'type': 'string',
                                                                               'description': 'The contents to write to the new file'}}}}},
                      {'type': 'function', 'function': {'name': 'file_glob_search',
                                                        'description': 'Search for files recursively in the project using glob patterns. Supports ** for recursive directory search. Will not show many build, cache, secrets dirs/files (can use ls tool instead). Output may be truncated; use targeted patterns',
                                                        'parameters': {'type': 'object',
                                                                       'required': ['pattern'],
                                                                       'properties': {
                                                                           'pattern': {'type': 'string',
                                                                                       'description': 'Glob pattern for file path matching'}}}}},
                      {'type': 'function', 'function': {'name': 'view_diff',
                                                        'description': 'View the current diff of working changes',
                                                        'parameters': {'type': 'object',
                                                                       'properties': {}}}},
                      {'type': 'function', 'function': {'name': 'read_currently_open_file',
                                                        'description': "Read the currently open file in the IDE. If the user seems to be referring to a file that you can't see, or is requesting an action on content that seems missing, try using this tool.",
                                                        'parameters': {'type': 'object',
                                                                       'properties': {}}}},
                      {'type': 'function', 'function': {'name': 'create_rule_block',
                                                        'description': 'Creates a "rule" that can be referenced in future conversations. This should be used whenever you want to establish code standards / preferences that should be applied consistently, or when you want to avoid making a mistake again. To modify existing rules, use the edit tool instead.\n\nRule Types:\n- Always: Include only "rule" (always included in model context)\n- Auto Attached: Include "rule", "globs", and/or "regex" (included when files match patterns)\n- Agent Requested: Include "rule" and "description" (AI decides when to apply based on description)\n- Manual: Include only "rule" (only included when explicitly mentioned using @ruleName)',
                                                        'parameters': {'type': 'object',
                                                                       'required': ['name', 'rule'],
                                                                       'properties': {
                                                                           'name': {'type': 'string',
                                                                                    'description': "Short, descriptive name summarizing the rule's purpose (e.g. 'React Standards', 'Type Hints')"},
                                                                           'rule': {'type': 'string',
                                                                                    'description': "Clear, imperative instruction for future code generation (e.g. 'Use named exports', 'Add Python type hints'). Each rule should focus on one specific standard."},
                                                                           'description': {
                                                                               'type': 'string',
                                                                               'description': 'Description of when this rule should be applied. Required for Agent Requested rules (AI decides when to apply). Optional for other types.'},
                                                                           'globs': {'type': 'string',
                                                                                     'description': "Optional file patterns to which this rule applies (e.g. ['**/*.{ts,tsx}'] or ['src/**/*.ts', 'tests/**/*.ts'])"},
                                                                           'regex': {'type': 'string',
                                                                                     'description': "Optional regex patterns to match against file content. Rule applies only to files whose content matches the pattern (e.g. 'useEffect' for React hooks or '\\bclass\\b' for class definitions)"},
                                                                           'alwaysApply': {
                                                                               'type': 'boolean',
                                                                               'description': 'Whether this rule should always be applied. Set to false for Agent Requested and Manual rules. Omit or set to true for Always and Auto Attached rules.'}}}}},
                      {'type': 'function', 'function': {'name': 'fetch_url_content',
                                                        'description': 'Can be used to view the contents of a website using a URL. Do NOT use this for files.',
                                                        'parameters': {'type': 'object',
                                                                       'required': ['url'],
                                                                       'properties': {
                                                                           'url': {'type': 'string',
                                                                                   'description': 'The URL to read'}}}}},
                      {'type': 'function', 'function': {'name': 'edit_existing_file',
                                                        'description': 'Use this tool to edit an existing file. If you don\'t know the contents of the file, read it first.\n  When addressing code modification requests, present a concise code snippet that\n  emphasizes only the necessary changes and uses abbreviated placeholders for\n  unmodified sections. For example:\n\n  ```language /path/to/file\n  // ... existing code ...\n\n  {{ modified code here }}\n\n  // ... existing code ...\n\n  {{ another modification }}\n\n  // ... rest of code ...\n  ```\n\n  In existing files, you should always restate the function or class that the snippet belongs to:\n\n  ```language /path/to/file\n  // ... existing code ...\n\n  function exampleFunction() {\n    // ... existing code ...\n\n    {{ modified code here }}\n\n    // ... rest of function ...\n  }\n\n  // ... rest of code ...\n  ```\n\n  Since users have access to their complete file, they prefer reading only the\n  relevant modifications. It\'s perfectly acceptable to omit unmodified portions\n  at the beginning, middle, or end of files using these "lazy" comments. Only\n  provide the complete file when explicitly requested. Include a concise explanation\n  of changes unless the user specifically asks for code only.\n\nThis tool CANNOT be called in parallel with other tools.',
                                                        'parameters': {'type': 'object',
                                                                       'required': ['filepath',
                                                                                    'changes'],
                                                                       'properties': {'filepath': {
                                                                           'type': 'string',
                                                                           'description': 'The path of the file to edit, relative to the root of the workspace.'},
                                                                           'changes': {
                                                                               'type': 'string',
                                                                               'description': "Any modifications to the file, showing only needed changes. Do NOT wrap this in a codeblock or write anything besides the code changes. In larger files, use brief language-appropriate placeholders for large unmodified sections, e.g. '// ... existing code ...'"}}}}},
                      {'type': 'function', 'function': {'name': 'single_find_and_replace',
                                                        'description': "Performs exact string replacements in a file.\n\nIMPORTANT:\n- ALWAYS use the `read_file` tool just before making edits, to understand the file's up-to-date contents and context. The user can also edit the file while you are working with it.\n- This tool CANNOT be called in parallel with other tools.\n- When editing text from `read_file` tool output, ensure you preserve exact whitespace/indentation.\n- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.\n- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable, for instance.\n\nWARNINGS:\n- When not using `replace_all`, the edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`.\n- The edit will likely fail if you have not recently used the `read_file` tool to view up-to-date file contents.",
                                                        'parameters': {'type': 'object',
                                                                       'required': ['filepath',
                                                                                    'old_string',
                                                                                    'new_string'],
                                                                       'properties': {'filepath': {
                                                                           'type': 'string',
                                                                           'description': 'The path to the file to modify, relative to the root of the workspace'},
                                                                           'old_string': {
                                                                               'type': 'string',
                                                                               'description': 'The text to replace - must be exact including whitespace/indentation'},
                                                                           'new_string': {
                                                                               'type': 'string',
                                                                               'description': 'The text to replace it with (MUST be different from old_string)'},
                                                                           'replace_all': {
                                                                               'type': 'boolean',
                                                                               'description': 'Replace all occurrences of old_string (default false)'}}}}},
                      {'type': 'function', 'function': {'name': 'grep_search',
                                                        'description': 'Performs a regex search over the repository using ripgrep. Will not include results for many build, cache, secrets dirs/files. Output may be truncated, so use targeted queries',
                                                        'parameters': {'type': 'object',
                                                                       'required': ['query'],
                                                                       'properties': {
                                                                           'query': {'type': 'string',
                                                                                     'description': "The search query to use. Must be the exact string to be searched or a valid ripgrep expression. Use regex with alternation (e.g., 'word1|word2|word3) or character classes to find multiple potential words in a single search."}}}}}],
            'requestId': 'd7eeb5a1-644d-45c9-af99-07c1f862db3d'}

    await VLLMProvider.complete(data['messages'], data)

    assert True
