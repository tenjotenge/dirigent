"""
Quick test for tool parser to verify it handles all input types correctly.
"""
import sys
sys.path.insert(0, 'backend')

from core.tool_parser import ToolCallParser, parse_tool_calls
from core.tool_protocol import ToolCallBatch

# Test cases
test_cases = [
    # 1. Pure JSON single tool call
    ('{"tool_name": "read_file", "args": {"file_path": "README.md"}}', "strict_json_single", True),
    
    # 2. Pure JSON batch
    ('{"calls": [{"tool_name": "read_file", "args": {"file_path": "README.md"}}]}', "strict_json_batch", True),
    
    # 3. JSON list
    ('[{"tool_name": "git_status", "args": {}}]', "strict_json_list", True),
    
    # 4. JSON in code block
    ('```json\n{"tool_name": "write_file", "args": {"file_path": "test.txt", "content": "hello"}}\n```', "regex_extraction", True),
    
    # 5. Natural language (no tool calls)
    ('I will help you read that file for you.', "no_tool_calls", False),
    
    # 6. Empty string
    ('', "empty_input", False),
    
    # 7. Malformed JSON
    ('{"tool_name": "read_file", "args": {', "no_tool_calls", False),
    
    # 8. Unknown tool (should be rejected)
    ('{"tool_name": "unknown_tool", "args": {}}', None, False),
]

registered_tools = ["read_file", "write_file", "git_status", "git_add", "git_commit", "git_push"]
parser = ToolCallParser(registered_tools)

print("Testing ToolCallParser...")
print("=" * 80)

all_passed = True
for i, (input_text, expected_method, should_have_calls) in enumerate(test_cases, 1):
    result = parser.parse(input_text)
    
    has_calls = result.tool_calls is not None and len(result.tool_calls) > 0
    
    # Check expectations
    method_match = result.parse_method == expected_method if expected_method else True
    calls_match = has_calls == should_have_calls
    
    passed = method_match and calls_match
    all_passed = all_passed and passed
    
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"Test {i}: {status}")
    print(f"  Input: {input_text[:60]}...")
    print(f"  Method: {result.parse_method} (expected: {expected_method})")
    print(f"  Has calls: {has_calls} (expected: {should_have_calls})")
    if result.tool_calls:
        print(f"  Calls found: {len(result.tool_calls.calls)}")
        for call in result.tool_calls.calls:
            print(f"    - {call.tool_name} (confidence: {call.confidence})")
    if result.error:
        print(f"  Error: {result.error}")
    print()

print("=" * 80)
if all_passed:
    print("All tests passed!")
else:
    print("Some tests failed!")
    sys.exit(1)