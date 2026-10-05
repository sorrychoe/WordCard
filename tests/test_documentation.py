"""새 함수나 클래스에 docstring을 빠뜨리지 않도록 검사합니다."""
import ast
from pathlib import Path
import unittest


class DocumentationTests(unittest.TestCase):
    """실행 코드와 테스트 전체의 함수·클래스 문서화를 검증한다."""

    def test_all_definitions_have_docstrings(self):
        """모든 명명된 함수와 클래스에 비어 있지 않은 docstring이 있는지 검사한다."""
        root = Path(__file__).resolve().parents[1]
        missing = []
        for folder in ['src', 'tests', 'packaging']:
            for path in (root / folder).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not ast.get_docstring(node):
                        missing.append(f'{path.relative_to(root)}:{node.lineno} {node.name}')
        self.assertEqual(missing, [], '\n'.join(missing))


if __name__ == '__main__':
    unittest.main()
